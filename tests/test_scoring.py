from app.agents.scoring import ScoringAgent
from app.models import KvkProfile, WebsiteProfile


def test_scores_relevant_active_service_business() -> None:
    website = WebsiteProfile(
        contact_page_url="https://example.nl/contact",
        detected_pain_points=["offerte aanvragen", "planning"],
        public_business_emails=["info@example.nl"],
    )
    kvk = KvkProfile(kvk_match_status="matched", match_confidence=90)

    lead = ScoringAgent().score(
        domain_status="active_business_website",
        has_mx=True,
        website=website,
        kvk=kvk,
        sector="maintenance_service",
        why_relevant=[],
        why_not_relevant=[],
    )

    assert lead.fit_score == 90
    assert lead.lead_category == "high_priority"
    assert lead.recommended_contact_method == "contact_form"


def test_ind_non_mailing_forces_manual_review() -> None:
    website = WebsiteProfile(contact_page_url="https://example.nl/contact")
    kvk = KvkProfile(ind_non_mailing=True, match_confidence=90)

    lead = ScoringAgent().score(
        domain_status="active_business_website",
        has_mx=True,
        website=website,
        kvk=kvk,
        sector="maintenance_service",
        why_relevant=[],
        why_not_relevant=[],
    )

    assert lead.recommended_contact_method == "manual_review_required"


def test_parked_domain_is_rejected() -> None:
    lead = ScoringAgent().score(
        domain_status="parked",
        has_mx=False,
        website=WebsiteProfile(),
        kvk=KvkProfile(),
        sector=None,
        why_relevant=[],
        why_not_relevant=[],
    )

    assert lead.fit_score == 0
    assert lead.lead_category == "reject"
    assert lead.recommended_contact_method == "do_not_contact"

