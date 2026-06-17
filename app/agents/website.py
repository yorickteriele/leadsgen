from dataclasses import dataclass, field
import json
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import Settings
from app.models import WebsiteProfile


EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
PHONE_RE = re.compile(r"(?:\+31|0031|0)\s?(?:\d[\s().-]?){8,12}\d")
KVK_RE = re.compile(r"\b(?:kvk(?:-nummer)?\s*[:#]?\s*)?(\d{8})\b", re.I)
VAT_RE = re.compile(r"\bNL[0-9A-Z]{9,14}\b", re.I)

PAGE_KEYWORDS = {
    "contact": ["contact", "contacteer", "bereikbaarheid"],
    "about": ["over-ons", "over ons", "about", "wie-zijn-wij"],
    "services": ["diensten", "services", "werkzaamheden", "service"],
    "pricing": ["prijzen", "tarieven", "pricing"],
    "legal": ["privacy", "voorwaarden", "disclaimer", "legal"],
}


@dataclass
class PageFetch:
    url: str
    final_url: str
    status_code: int
    text: str
    html: str


@dataclass
class WebsiteResult:
    has_website: bool = False
    redirect_target: str | None = None
    profile: WebsiteProfile = field(default_factory=WebsiteProfile)
    fetched_pages: list[str] = field(default_factory=list)
    parked_signals: list[str] = field(default_factory=list)
    under_construction_signals: list[str] = field(default_factory=list)
    webshop_signals: list[str] = field(default_factory=list)
    form_present: bool = False
    customer_login_present: bool = False
    source_urls: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class WebsiteAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def collect(self, candidates: list[str]) -> WebsiteResult:
        headers = {"User-Agent": self.settings.user_agent}
        timeout = httpx.Timeout(self.settings.http_timeout_seconds)
        async with httpx.AsyncClient(
            headers=headers, timeout=timeout, follow_redirects=True
        ) as client:
            homepage = await self._fetch_first_homepage(client, candidates)
            if homepage is None:
                result = WebsiteResult()
                result.errors.append("No HTTP(S) website responded successfully")
                return result

            result = WebsiteResult(has_website=True)
            result.redirect_target = homepage.final_url if homepage.final_url != homepage.url else None
            profile = self._extract_page(homepage.final_url, homepage.html, homepage.text)
            profile.final_url = homepage.final_url
            result.profile = profile
            result.fetched_pages.append(homepage.final_url)
            result.source_urls.append(homepage.final_url)

            soup = BeautifulSoup(homepage.html, "lxml")
            extra_links = self._select_extra_links(homepage.final_url, soup)
            for kind, url in extra_links[: max(0, self.settings.max_pages_per_domain - 1)]:
                page = await self._fetch(client, url)
                if page is None:
                    continue
                extra_profile = self._extract_page(page.final_url, page.html, page.text)
                self._merge_profiles(profile, extra_profile)
                result.fetched_pages.append(page.final_url)
                result.source_urls.append(page.final_url)
                if kind == "contact" and profile.contact_page_url is None:
                    profile.contact_page_url = page.final_url
                if kind == "about" and profile.about_page_url is None:
                    profile.about_page_url = page.final_url
                if kind == "services" and profile.services_page_url is None:
                    profile.services_page_url = page.final_url

            all_text = self._visible_text(BeautifulSoup(homepage.html, "lxml"))
            result.parked_signals = self._detect_terms(
                all_text,
                [
                    "domein is gereserveerd",
                    "domain for sale",
                    "te koop",
                    "parked",
                    "sedo",
                    "dan.com",
                    "transip reserved",
                ],
            )
            result.under_construction_signals = self._detect_terms(
                all_text,
                ["under construction", "in aanbouw", "binnenkort online", "coming soon"],
            )
            result.webshop_signals = self._detect_terms(
                all_text,
                ["winkelwagen", "checkout", "afrekenen", "toevoegen aan winkelwagen"],
            )
            result.form_present = bool(soup.find("form"))
            result.customer_login_present = bool(
                soup.find(string=re.compile(r"(inloggen|login|klantenportaal)", re.I))
            )
            profile.digital_maturity_notes = self._digital_maturity_notes(result)
            profile.summary = self._summarize(profile.summary)
            return result

    async def _fetch_first_homepage(
        self, client: httpx.AsyncClient, candidates: list[str]
    ) -> PageFetch | None:
        urls: list[str] = []
        for candidate in candidates:
            urls.extend([f"https://{candidate}", f"http://{candidate}"])
        for url in urls:
            page = await self._fetch(client, url)
            if page is not None:
                return page
        return None

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> PageFetch | None:
        try:
            response = await client.get(url)
            content_type = response.headers.get("content-type", "")
            if response.status_code >= 400 or "html" not in content_type.lower():
                return None
            soup = BeautifulSoup(response.text, "lxml")
            return PageFetch(
                url=url,
                final_url=str(response.url),
                status_code=response.status_code,
                text=self._visible_text(soup),
                html=response.text,
            )
        except httpx.HTTPError:
            return None

    def _extract_page(self, url: str, html: str, text: str) -> WebsiteProfile:
        soup = BeautifulSoup(html, "lxml")
        title = self._clean(soup.title.string if soup.title else None)
        meta_description = self._meta(soup, "description")
        headings = [self._clean(h.get_text(" ")) for h in soup.find_all(["h1", "h2"])]
        headings = [heading for heading in headings if heading]
        organization_names = self._extract_jsonld_names(soup)
        profile = WebsiteProfile(
            final_url=url,
            title=title,
            meta_description=meta_description,
            summary=self._summarize(" ".join([title or "", meta_description or "", text])),
            language=soup.html.get("lang") if soup.html else None,
            detected_company_names=self._unique(
                organization_names
                + self._names_from_title(title)
                + self._names_from_footer(soup)
                + headings[:2]
            ),
            detected_services=self._detect_services(text),
            detected_pain_points=self._detect_pain_points(text),
            public_business_emails=self._filter_business_emails(EMAIL_RE.findall(text)),
            public_phone_numbers=self._unique(PHONE_RE.findall(text)),
            public_addresses=self._extract_addresses(text),
            social_links=self._extract_social_links(url, soup),
            visible_kvk_numbers=self._unique(KVK_RE.findall(text)),
            visible_vat_numbers=self._unique([m.upper() for m in VAT_RE.findall(text)]),
        )
        self._set_page_urls(profile, url, soup)
        return profile

    def _merge_profiles(self, target: WebsiteProfile, source: WebsiteProfile) -> None:
        for attr in [
            "detected_company_names",
            "detected_services",
            "detected_pain_points",
            "public_business_emails",
            "public_phone_numbers",
            "public_addresses",
            "social_links",
            "visible_kvk_numbers",
            "visible_vat_numbers",
        ]:
            setattr(target, attr, self._unique(getattr(target, attr) + getattr(source, attr)))
        if target.meta_description is None:
            target.meta_description = source.meta_description
        if target.summary is None:
            target.summary = source.summary

    def _visible_text(self, soup: BeautifulSoup) -> str:
        for element in soup(["script", "style", "noscript", "svg"]):
            element.decompose()
        return self._clean(soup.get_text(" "))

    def _meta(self, soup: BeautifulSoup, name: str) -> str | None:
        tag = soup.find("meta", attrs={"name": name}) or soup.find(
            "meta", attrs={"property": f"og:{name}"}
        )
        return self._clean(tag.get("content")) if tag else None

    def _set_page_urls(self, profile: WebsiteProfile, base_url: str, soup: BeautifulSoup) -> None:
        for kind, url in self._select_extra_links(base_url, soup):
            if kind == "contact" and profile.contact_page_url is None:
                profile.contact_page_url = url
            elif kind == "about" and profile.about_page_url is None:
                profile.about_page_url = url
            elif kind == "services" and profile.services_page_url is None:
                profile.services_page_url = url

    def _select_extra_links(self, base_url: str, soup: BeautifulSoup) -> list[tuple[str, str]]:
        base_host = urlparse(base_url).hostname
        found: list[tuple[str, str]] = []
        for anchor in soup.find_all("a", href=True):
            label = self._clean(anchor.get_text(" ") + " " + anchor["href"]).lower()
            url = urljoin(base_url, anchor["href"])
            if urlparse(url).hostname != base_host:
                continue
            for kind, keywords in PAGE_KEYWORDS.items():
                if any(keyword in label for keyword in keywords):
                    found.append((kind, url))
                    break
        deduped: list[tuple[str, str]] = []
        seen: set[str] = set()
        priority = {"contact": 0, "about": 1, "services": 2, "pricing": 3, "legal": 4}
        for item in sorted(found, key=lambda pair: priority.get(pair[0], 99)):
            if item[1] not in seen:
                deduped.append(item)
                seen.add(item[1])
        return deduped

    def _extract_jsonld_names(self, soup: BeautifulSoup) -> list[str]:
        names: list[str] = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except json.JSONDecodeError:
                continue
            nodes = data if isinstance(data, list) else [data]
            for node in nodes:
                if isinstance(node, dict):
                    if node.get("@type") in {"Organization", "LocalBusiness"} and node.get("name"):
                        names.append(str(node["name"]))
                    graph = node.get("@graph")
                    if isinstance(graph, list):
                        for graph_node in graph:
                            if isinstance(graph_node, dict) and graph_node.get("name"):
                                names.append(str(graph_node["name"]))
        return names

    def _names_from_title(self, title: str | None) -> list[str]:
        if not title:
            return []
        parts = re.split(r"\s[-|]\s", title)
        return [part.strip() for part in parts[:2] if 2 < len(part.strip()) < 80]

    def _names_from_footer(self, soup: BeautifulSoup) -> list[str]:
        footer = soup.find("footer")
        if footer is None:
            return []
        text = self._clean(footer.get_text(" "))
        matches = re.findall(r"(?:copyright|©|\(c\))\s*(?:\d{4})?\s*([^|.\n]{3,80})", text, re.I)
        return [self._clean(match) for match in matches]

    def _detect_services(self, text: str) -> list[str]:
        terms = [
            "installatie",
            "onderhoud",
            "reparatie",
            "schoonmaak",
            "advies",
            "inspectie",
            "keuring",
            "verhuur",
            "planning",
            "service",
            "montage",
            "projecten",
        ]
        return self._detect_terms(text, terms)

    def _detect_pain_points(self, text: str) -> list[str]:
        return self._detect_terms(
            text,
            [
                "offerte aanvragen",
                "maak een afspraak",
                "service melden",
                "storingen",
                "onderhoud",
                "planning",
                "factuur",
                "contract",
                "klantenportaal",
                "formulier",
                "werkbon",
                "inspectie",
                "abonnement",
                "periodiek onderhoud",
                "monteurs",
                "op locatie",
                "aanvragen",
                "reserveren",
                "projecten",
                "documenten",
            ],
        )

    def _detect_terms(self, text: str, terms: list[str]) -> list[str]:
        lower = text.lower()
        return [term for term in terms if term in lower]

    def _filter_business_emails(self, emails: list[str]) -> list[str]:
        blocked = {"example.com", "domain.com"}
        public = []
        for email in emails:
            domain = email.split("@", 1)[1].lower()
            if domain not in blocked:
                public.append(email.lower())
        return self._unique(public)

    def _extract_addresses(self, text: str) -> list[str]:
        matches = re.findall(
            r"\b[A-ZÀ-ÿ][A-Za-zÀ-ÿ' .-]{2,50}\s+\d{1,5}[A-Za-z]?,?\s+[1-9][0-9]{3}\s?[A-Z]{2}\s+[A-ZÀ-ÿ][A-Za-zÀ-ÿ' .-]{2,40}",
            text,
        )
        return self._unique([self._clean(match) for match in matches])[:5]

    def _extract_social_links(self, base_url: str, soup: BeautifulSoup) -> list[str]:
        socials = []
        for anchor in soup.find_all("a", href=True):
            url = urljoin(base_url, anchor["href"])
            host = urlparse(url).hostname or ""
            if any(site in host for site in ["linkedin.com", "facebook.com", "instagram.com", "x.com", "twitter.com"]):
                socials.append(url)
        return self._unique(socials)

    def _digital_maturity_notes(self, result: WebsiteResult) -> list[str]:
        notes = []
        if result.form_present:
            notes.append("Website contains a contact/request form")
        if not result.customer_login_present:
            notes.append("No visible customer login or portal detected")
        if result.profile.public_business_emails and not result.profile.contact_page_url:
            notes.append("Contact path appears email-led")
        if result.under_construction_signals:
            notes.append("Website appears under construction")
        return notes

    def _summarize(self, text: str | None) -> str | None:
        cleaned = self._clean(text)
        if not cleaned:
            return None
        return cleaned[:500]

    def _clean(self, value: str | None) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

    def _unique(self, values: list[str]) -> list[str]:
        seen = set()
        output = []
        for value in values:
            cleaned = self._clean(value)
            key = cleaned.lower()
            if cleaned and key not in seen:
                output.append(cleaned)
                seen.add(key)
        return output

