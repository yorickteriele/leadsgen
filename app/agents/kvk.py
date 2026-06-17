from dataclasses import dataclass
import re
from urllib.parse import urlparse

import httpx

from app.config import Settings
from app.models import KvkProfile, WebsiteProfile


LEGAL_SUFFIX_RE = re.compile(
    r"\b(b\.?v\.?|v\.?o\.?f\.?|eenmanszaak|holding|groep|nederland|nl)\b",
    re.I,
)


@dataclass
class KvkLookupContext:
    domain: str
    website: WebsiteProfile


class KvkAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def enrich(self, context: KvkLookupContext) -> tuple[KvkProfile, list[str]]:
        if not self.settings.kvk_api_key:
            return (
                KvkProfile(
                    match_reasoning="KvK API key not configured; KvK enrichment skipped"
                ),
                ["KvK API key not configured; KvK enrichment skipped"],
            )

        headers = {"apikey": self.settings.kvk_api_key, "User-Agent": self.settings.user_agent}
        async with httpx.AsyncClient(
            base_url=self.settings.kvk_api_base_url,
            headers=headers,
            timeout=self.settings.http_timeout_seconds,
        ) as client:
            if context.website.visible_kvk_numbers:
                kvk_number = context.website.visible_kvk_numbers[0]
                profile = await self._basisprofiel(client, kvk_number)
                if profile:
                    profile.kvk_match_status = "matched"
                    profile.match_confidence = 100
                    profile.match_reasoning = "Exact KvK number was visible on the website"
                    return profile, []
                return (
                    KvkProfile(
                        raw_candidate_count=0,
                        match_reasoning="Visible KvK number was found, but Basisprofiel lookup failed",
                    ),
                    ["Visible KvK number could not be verified through KvK Basisprofiel"],
                )

            candidates = await self._search_candidates(client, context)
            if not candidates:
                return KvkProfile(match_reasoning="No KvK candidates found"), []

            scored = [
                (self._score_candidate(candidate, context), candidate) for candidate in candidates
            ]
            scored.sort(key=lambda item: item[0], reverse=True)
            best_score, best_candidate = scored[0]
            if best_score >= 70:
                kvk_number = str(best_candidate.get("kvkNummer") or best_candidate.get("kvk_number") or "")
                profile = await self._basisprofiel(client, kvk_number) if kvk_number else None
                profile = profile or self._candidate_to_profile(best_candidate)
                profile.kvk_match_status = "matched"
                profile.match_confidence = best_score
                profile.raw_candidate_count = len(candidates)
                profile.match_reasoning = "KvK candidate matched by name/domain/address signals"
                return profile, []
            if best_score >= 50:
                return (
                    KvkProfile(
                        kvk_match_status="ambiguous",
                        match_confidence=best_score,
                        raw_candidate_count=len(candidates),
                        match_reasoning="Best KvK candidate is name-only or lacks enough corroborating website/location evidence",
                    ),
                    ["KvK candidates found, but match is ambiguous"],
                )
            return (
                KvkProfile(
                    raw_candidate_count=len(candidates),
                    match_reasoning="KvK candidates were weak or contradictory",
                ),
                ["KvK lookup returned only weak matches"],
            )

    async def _basisprofiel(
        self, client: httpx.AsyncClient, kvk_number: str
    ) -> KvkProfile | None:
        for path in [f"/basisprofielen/{kvk_number}", f"/basisprofiel/{kvk_number}"]:
            try:
                response = await client.get(path)
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                return self._basis_to_profile(response.json())
            except httpx.HTTPError:
                continue
        return None

    async def _search_candidates(
        self, client: httpx.AsyncClient, context: KvkLookupContext
    ) -> list[dict]:
        queries = self._candidate_queries(context)
        candidates: list[dict] = []
        seen: set[str] = set()
        for query in queries[:8]:
            try:
                response = await client.get("/zoeken", params={"handelsnaam": query})
                if response.status_code == 400:
                    response = await client.get("/zoeken", params={"q": query})
                response.raise_for_status()
            except httpx.HTTPError:
                continue
            data = response.json()
            items = data.get("resultaten") or data.get("items") or data.get("data") or []
            if isinstance(items, dict):
                items = [items]
            for item in items:
                key = str(item.get("kvkNummer") or item.get("kvk_number") or item)
                if key not in seen and isinstance(item, dict):
                    candidates.append(item)
                    seen.add(key)
        return candidates

    def _candidate_queries(self, context: KvkLookupContext) -> list[str]:
        names = context.website.detected_company_names[:]
        domain_name = context.domain.rsplit(".", 1)[0].replace("-", " ")
        names.append(domain_name)
        normalized = []
        for name in names:
            cleaned = LEGAL_SUFFIX_RE.sub("", name)
            cleaned = re.sub(r"[^a-zA-Z0-9À-ÿ ]+", " ", cleaned)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if cleaned:
                normalized.append(cleaned)
        return list(dict.fromkeys([name for name in names + normalized if name]))

    def _score_candidate(self, candidate: dict, context: KvkLookupContext) -> int:
        score = 0
        candidate_text = " ".join(str(value) for value in candidate.values()).lower()
        domain = context.domain.lower()
        detected_names = [name.lower() for name in context.website.detected_company_names]
        if domain in candidate_text:
            score += 35
        for name in detected_names:
            normalized = LEGAL_SUFFIX_RE.sub("", name).strip()
            if name and name in candidate_text:
                score += 35
                break
            if normalized and normalized in candidate_text:
                score += 25
                break
        for address in context.website.public_addresses:
            city_or_postcode = self._postcode_or_city(address)
            if city_or_postcode and city_or_postcode.lower() in candidate_text:
                score += 20
                break
        if any(term in candidate_text for term in ["actief", "active"]):
            score += 5
        return min(score, 94)

    def _candidate_to_profile(self, candidate: dict) -> KvkProfile:
        return KvkProfile(
            kvk_number=self._string(candidate.get("kvkNummer") or candidate.get("kvk_number")),
            statutaire_naam=self._string(candidate.get("naam") or candidate.get("statutaireNaam")),
            handelsnamen=self._as_list(candidate.get("handelsnamen") or candidate.get("handelsnaam")),
            websites=self._extract_websites(candidate),
            addresses=self._extract_addresses(candidate),
        )

    def _basis_to_profile(self, data: dict) -> KvkProfile:
        handelsnamen = self._as_list(data.get("handelsnamen"))
        if data.get("naam"):
            handelsnamen.append(str(data["naam"]))
        activiteiten = data.get("sbiActiviteiten") or data.get("sbi_activiteiten") or []
        sbi = []
        hoofdactiviteit = None
        for activiteit in activiteiten if isinstance(activiteiten, list) else []:
            if isinstance(activiteit, dict):
                omschrijving = activiteit.get("sbiOmschrijving") or activiteit.get("omschrijving")
                if omschrijving:
                    sbi.append(str(omschrijving))
                if activiteit.get("indHoofdactiviteit") and omschrijving:
                    hoofdactiviteit = str(omschrijving)
        return KvkProfile(
            kvk_number=self._string(data.get("kvkNummer") or data.get("kvk_number")),
            vestigingsnummer=self._string(data.get("vestigingsnummer")),
            statutaire_naam=self._string(data.get("statutaireNaam") or data.get("naam")),
            handelsnamen=list(dict.fromkeys(handelsnamen)),
            rechtsvorm=self._string(data.get("rechtsvorm")),
            formele_registratiedatum=self._string(data.get("formeleRegistratiedatum")),
            addresses=self._extract_addresses(data),
            websites=self._extract_websites(data),
            sbi_activiteiten=sbi,
            hoofdactiviteit=hoofdactiviteit,
            aantal_vestigingen=self._int(data.get("aantalVestigingen")),
            ind_non_mailing=data.get("indNonMailing"),
        )

    def _extract_websites(self, data: dict) -> list[str]:
        websites = []
        for key in ["websites", "website", "domein"]:
            value = data.get(key)
            websites.extend(self._as_list(value))
        return list(dict.fromkeys([site for site in websites if site]))

    def _extract_addresses(self, data: dict) -> list[str]:
        addresses = []
        raw_addresses = data.get("adressen") or data.get("addresses") or []
        if isinstance(raw_addresses, dict):
            raw_addresses = [raw_addresses]
        for address in raw_addresses if isinstance(raw_addresses, list) else []:
            if not isinstance(address, dict):
                continue
            parts = [
                address.get("straatnaam"),
                address.get("huisnummer"),
                address.get("postcode"),
                address.get("plaats"),
            ]
            line = " ".join(str(part) for part in parts if part)
            if line:
                addresses.append(line)
        return list(dict.fromkeys(addresses))

    def _postcode_or_city(self, address: str) -> str | None:
        postcode = re.search(r"\b[1-9][0-9]{3}\s?[A-Z]{2}\b", address)
        if postcode:
            return postcode.group(0)
        parts = address.split()
        return parts[-1] if parts else None

    def _string(self, value: object) -> str | None:
        return str(value) if value not in (None, "") else None

    def _int(self, value: object) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _as_list(self, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item]
        if isinstance(value, dict):
            return [str(v) for v in value.values() if isinstance(v, str)]
        return [str(value)]

