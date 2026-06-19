from app.agents.website import WebsiteResult
from app.models import DomainStatus, KvkProfile, LeadProfile, WebsiteProfile


RELEVANT_TERMS = {
    "installatie",
    "onderhoud",
    "reparatie",
    "schoonmaak",
    "field service",
    "contractor",
    "aannemer",
    "advies",
    "consultancy",
    "verhuur",
    "inspectie",
    "keuring",
    "certificering",
    "planning",
    "service",
    "monteurs",
    "op locatie",
}

IRRELEVANT_TERMS = {
    "restaurant",
    "cafe",
    "café",
    "blog",
    "portfolio",
    "holding",
    "webshop",
    "winkelwagen",
    "checkout",
    "onderwijs",
    "gemeente",
    "stichting",
}

SOFTWARE_PROVIDER_TERMS = {
    "software",
    "saas",
    "gratis demo",
    "demo aanvragen",
    "probeer gratis",
    "free trial",
    "integraties",
    "planningssoftware",
    "field service software",
    "field service management",
    "werkorder software",
    "workforce management",
}


class ClassificationAgent:
    def classify_domain_status(self, has_dns: bool, website: WebsiteResult) -> DomainStatus:
        if website.parked_signals:
            return "parked"
        if not website.has_website:
            return "no_website" if has_dns else "unknown"
        if website.under_construction_signals:
            return "under_construction"
        text = " ".join(
            [
                website.profile.title or "",
                website.profile.meta_description or "",
                website.profile.summary or "",
                " ".join(website.profile.detected_services),
            ]
        ).lower()
        if "example domain name" in text or "registered by sidn" in text:
            return "landing_page"
        if website.webshop_signals:
            return "webshop"
        if any(term in text for term in ["blog", "portfolio", "persoonlijk"]):
            return "personal_site"
        if website.redirect_target and not website.profile.detected_company_names:
            return "redirect_only"
        if (
            website.profile.public_business_emails
            or website.profile.public_phone_numbers
            or website.profile.contact_page_url
            or website.profile.detected_services
            or website.profile.detected_pain_points
        ):
            return "active_business_website"
        return "landing_page"

    def detect_sector(self, website: WebsiteProfile, kvk: KvkProfile) -> str | None:
        text = " ".join(
            [
                website.title or "",
                website.meta_description or "",
                website.summary or "",
                " ".join(website.detected_services),
                " ".join(kvk.sbi_activiteiten),
            ]
        ).lower()
        if any(term in text for term in SOFTWARE_PROVIDER_TERMS):
            return "software_provider"
        if any(term in text for term in ["installatie", "monteur", "montage"]):
            return "installation"
        if "schoonmaak" in text:
            return "cleaning"
        if any(term in text for term in ["inspectie", "keuring", "certificering"]):
            return "inspection_certification"
        if any(term in text for term in ["onderhoud", "reparatie", "service"]):
            return "maintenance_service"
        if any(term in text for term in ["advies", "consultancy", "consultant"]):
            return "b2b_consulting"
        if any(term in text for term in ["verhuur", "rental"]):
            return "rental_service"
        return None

    def relevance_signals(
        self, domain_status: DomainStatus, website: WebsiteProfile, kvk: KvkProfile
    ) -> tuple[list[str], list[str]]:
        text = " ".join(
            [
                website.title or "",
                website.meta_description or "",
                website.summary or "",
                " ".join(website.detected_services),
                " ".join(website.detected_pain_points),
                " ".join(kvk.sbi_activiteiten),
            ]
        ).lower()
        relevant = []
        not_relevant = []
        matched_relevant = sorted(term for term in RELEVANT_TERMS if term in text)
        if matched_relevant:
            relevant.append("Relevant service/workflow terms detected: " + ", ".join(matched_relevant[:8]))
        if website.detected_pain_points:
            relevant.append("Operational pain-point terms detected: " + ", ".join(website.detected_pain_points[:8]))
        if website.public_business_emails or website.contact_page_url or website.public_phone_numbers:
            relevant.append("Public business contact path is available")
        matched_software = sorted(term for term in SOFTWARE_PROVIDER_TERMS if term in text)
        if matched_software:
            not_relevant.append("Software/SaaS provider signals detected: " + ", ".join(matched_software[:5]))
        matched_irrelevant = sorted(term for term in IRRELEVANT_TERMS if term in text)
        if matched_irrelevant:
            not_relevant.append("Less relevant terms detected: " + ", ".join(matched_irrelevant[:8]))
        if domain_status in {"parked", "no_website", "personal_site", "webshop"}:
            not_relevant.append(f"Domain status is {domain_status}")
        if kvk.ind_non_mailing is True:
            not_relevant.append("KvK indNonMailing is true")
        return relevant, not_relevant

    def estimate_company_size(self, kvk: KvkProfile) -> str | None:
        if kvk.aantal_vestigingen is None:
            return None
        if kvk.aantal_vestigingen <= 1:
            return "small"
        if kvk.aantal_vestigingen <= 5:
            return "small_medium"
        return "larger_multi_branch"
