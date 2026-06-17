from typing import Literal
from pydantic import BaseModel, Field


DomainStatus = Literal[
    "active_business_website",
    "landing_page",
    "under_construction",
    "parked",
    "redirect_only",
    "no_website",
    "personal_site",
    "webshop",
    "unknown",
]

LeadCategory = Literal["reject", "low_priority", "medium_priority", "high_priority"]
ContactMethod = Literal[
    "do_not_contact",
    "manual_review_required",
    "contact_form",
    "public_business_email",
    "phone",
    "linkedin_company_page",
]
KvkMatchStatus = Literal["not_found", "ambiguous", "matched"]


class EnrichDomainRequest(BaseModel):
    domain: str = Field(
        examples=["example.nl"],
        description="Newly observed .nl domain. Protocols, paths, and query strings are accepted and normalized.",
    )
    first_seen_at: str = Field(
        default="",
        examples=["2026-06-17T12:00:00Z"],
        description="Timestamp when the domain was first observed by the upstream source.",
    )
    source: str = Field(
        default="",
        examples=["daily-domain-feed"],
        description="Name of the upstream observation source.",
    )


class WebsiteProfile(BaseModel):
    final_url: str | None = None
    title: str | None = None
    meta_description: str | None = None
    summary: str | None = None
    language: str | None = None
    detected_company_names: list[str] = Field(default_factory=list)
    detected_sector: str | None = None
    detected_services: list[str] = Field(default_factory=list)
    detected_pain_points: list[str] = Field(default_factory=list)
    digital_maturity_notes: list[str] = Field(default_factory=list)
    contact_page_url: str | None = None
    about_page_url: str | None = None
    services_page_url: str | None = None
    public_business_emails: list[str] = Field(default_factory=list)
    public_phone_numbers: list[str] = Field(default_factory=list)
    public_addresses: list[str] = Field(default_factory=list)
    social_links: list[str] = Field(default_factory=list)
    visible_kvk_numbers: list[str] = Field(default_factory=list)
    visible_vat_numbers: list[str] = Field(default_factory=list)


class KvkProfile(BaseModel):
    kvk_match_status: KvkMatchStatus = "not_found"
    match_confidence: int = 0
    kvk_number: str | None = None
    vestigingsnummer: str | None = None
    statutaire_naam: str | None = None
    handelsnamen: list[str] = Field(default_factory=list)
    rechtsvorm: str | None = None
    formele_registratiedatum: str | None = None
    addresses: list[str] = Field(default_factory=list)
    websites: list[str] = Field(default_factory=list)
    sbi_activiteiten: list[str] = Field(default_factory=list)
    hoofdactiviteit: str | None = None
    aantal_vestigingen: int | None = None
    ind_non_mailing: bool | None = None
    raw_candidate_count: int = 0
    match_reasoning: str = ""


class LeadProfile(BaseModel):
    likely_business: bool = False
    sector: str | None = None
    company_size_estimate: str | None = None
    fit_score: int = 0
    lead_category: LeadCategory = "reject"
    why_relevant: list[str] = Field(default_factory=list)
    why_not_relevant: list[str] = Field(default_factory=list)
    recommended_contact_method: ContactMethod = "do_not_contact"
    outreach_angle: str | None = None
    suggested_personalized_opener: str | None = None


class Evidence(BaseModel):
    positive_signals: list[str] = Field(default_factory=list)
    negative_signals: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)


class LeadEnrichmentResponse(BaseModel):
    domain: str
    first_seen_at: str = ""
    source: str = ""
    domain_status: DomainStatus = "unknown"
    has_dns: bool = False
    has_website: bool = False
    has_mx: bool = False
    redirect_target: str | None = None
    nameservers: list[str] = Field(default_factory=list)
    mail_provider: str | None = None
    website: WebsiteProfile = Field(default_factory=WebsiteProfile)
    kvk: KvkProfile = Field(default_factory=KvkProfile)
    lead: LeadProfile = Field(default_factory=LeadProfile)
    evidence: Evidence = Field(default_factory=Evidence)
    next_action: str = ""
