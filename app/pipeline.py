from app.agents.classification import ClassificationAgent
from app.agents.dns_agent import DnsAgent
from app.agents.domain import DomainNormalizerAgent
from app.agents.kvk import KvkAgent, KvkLookupContext
from app.agents.scoring import ScoringAgent
from app.agents.website import WebsiteAgent
from app.config import Settings
from app.models import EnrichDomainRequest, Evidence, LeadEnrichmentResponse


class LeadEnrichmentPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.normalizer = DomainNormalizerAgent()
        self.dns = DnsAgent()
        self.website = WebsiteAgent(settings)
        self.kvk = KvkAgent(settings)
        self.classifier = ClassificationAgent()
        self.scoring = ScoringAgent()

    async def enrich(self, request: EnrichDomainRequest) -> LeadEnrichmentResponse:
        normalized = self.normalizer.normalize(request.domain)
        dns_result = self.dns.collect(normalized.domain)
        website_result = await self.website.collect(normalized.candidates)
        kvk_profile, kvk_uncertainties = await self.kvk.enrich(
            KvkLookupContext(domain=normalized.domain, website=website_result.profile)
        )
        domain_status = self.classifier.classify_domain_status(
            dns_result.has_dns, website_result
        )
        sector = self.classifier.detect_sector(website_result.profile, kvk_profile)
        website_result.profile.detected_sector = sector
        why_relevant, why_not_relevant = self.classifier.relevance_signals(
            domain_status, website_result.profile, kvk_profile
        )
        lead = self.scoring.score(
            domain_status=domain_status,
            has_mx=dns_result.has_mx,
            website=website_result.profile,
            kvk=kvk_profile,
            sector=sector,
            why_relevant=why_relevant,
            why_not_relevant=why_not_relevant,
        )
        evidence = self._evidence(
            dns_result=dns_result,
            website_result=website_result,
            kvk_uncertainties=kvk_uncertainties,
            domain_status=domain_status,
            lead_score=lead.fit_score,
        )
        return LeadEnrichmentResponse(
            domain=normalized.domain,
            first_seen_at=request.first_seen_at,
            source=request.source,
            domain_status=domain_status,
            has_dns=dns_result.has_dns,
            has_website=website_result.has_website,
            has_mx=dns_result.has_mx,
            redirect_target=website_result.redirect_target,
            nameservers=dns_result.nameservers,
            mail_provider=dns_result.mail_provider,
            website=website_result.profile,
            kvk=kvk_profile,
            lead=lead,
            evidence=evidence,
            next_action=self._next_action(lead.recommended_contact_method, lead.fit_score),
        )

    def _evidence(
        self,
        dns_result,
        website_result,
        kvk_uncertainties: list[str],
        domain_status: str,
        lead_score: int,
    ) -> Evidence:
        positive = []
        negative = []
        uncertainties = list(kvk_uncertainties)
        if dns_result.has_dns:
            positive.append("DNS records were found")
        else:
            negative.append("No DNS records were found")
        if dns_result.has_mx:
            positive.append("MX records indicate operational email")
        if website_result.has_website:
            positive.append("Website responded with HTML content")
        else:
            negative.append("Website fetch failed or did not return HTML")
        if website_result.profile.public_business_emails:
            positive.append("Public business email address found on website")
        if website_result.profile.public_phone_numbers:
            positive.append("Public phone number found on website")
        if website_result.profile.detected_pain_points:
            positive.append(
                "Operational workflow terms found: "
                + ", ".join(website_result.profile.detected_pain_points[:8])
            )
        if website_result.parked_signals:
            negative.append("Parked-domain signals found: " + ", ".join(website_result.parked_signals))
        if website_result.under_construction_signals:
            uncertainties.append(
                "Under-construction signals found: "
                + ", ".join(website_result.under_construction_signals)
            )
        if domain_status in {"unknown", "landing_page", "redirect_only"}:
            uncertainties.append(f"Domain status classified as {domain_status}")
        positive.append(f"Fit score calculated as {lead_score}")
        uncertainties.extend(website_result.errors)
        return Evidence(
            positive_signals=positive,
            negative_signals=negative,
            uncertainties=uncertainties,
            source_urls=list(dict.fromkeys(website_result.source_urls)),
        )

    def _next_action(self, method: str, score: int) -> str:
        if score < 40 or method == "do_not_contact":
            return "Reject or keep only for passive monitoring."
        if method == "manual_review_required":
            return "Review compliance and match confidence before any outreach."
        return f"Prepare compliant outreach using recommended method: {method}."

