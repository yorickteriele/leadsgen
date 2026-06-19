from datetime import date

from app.models import ContactMethod, DomainStatus, KvkProfile, LeadCategory, LeadProfile, WebsiteProfile


class ScoringAgent:
    def score(
        self,
        domain_status: DomainStatus,
        has_mx: bool,
        website: WebsiteProfile,
        kvk: KvkProfile,
        sector: str | None,
        why_relevant: list[str],
        why_not_relevant: list[str],
    ) -> LeadProfile:
        score = 0

        # KvK is the primary signal — confirms the business exists and what it does
        if kvk.kvk_match_status == "matched" and kvk.match_confidence >= 70:
            score += 30
        elif kvk.kvk_match_status == "matched":
            score += 15
        else:
            score -= 20
            why_not_relevant.append("No KvK match — cannot verify business type or sector")

        # Sector relevance — sector detection already uses KvK SBI codes
        if sector and sector != "software_provider":
            score += 20
        elif sector == "software_provider":
            score -= 50
            why_not_relevant.append("Company sells software or SaaS — not a field-service operator")
        else:
            score -= 25
            why_not_relevant.append("No field service sector identified from KvK SBI codes")

        # Operational signals — bonuses, not requirements
        if has_mx:
            score += 10
        if self._appears_new(kvk):
            score += 10
        if domain_status == "active_business_website":
            score += 10
        if website.detected_pain_points:
            score += 10
        if website.public_business_emails or website.public_phone_numbers or website.contact_page_url:
            score += 10

        # Disqualifying signals
        if domain_status in {"personal_site", "webshop"}:
            score -= 25
        if domain_status == "parked":
            score -= 5
        if kvk.kvk_match_status == "ambiguous":
            score -= 10
        if kvk.aantal_vestigingen is not None and kvk.aantal_vestigingen > 10:
            score -= 15
            why_not_relevant.append("Company appears larger than the practical SMB target")
        if not (website.public_business_emails or website.public_phone_numbers or website.contact_page_url):
            score -= 5
        if kvk.ind_non_mailing is True:
            score -= 10

        score = max(0, min(100, score))
        recommended_contact_method = self._contact_method(domain_status, website, kvk)
        if score < 40:
            recommended_contact_method = "do_not_contact"

        return LeadProfile(
            likely_business=score >= 40 and kvk.kvk_match_status in {"matched", "ambiguous"},
            sector=sector,
            company_size_estimate=self._size(kvk),
            fit_score=score,
            lead_category=self._category(score),
            why_relevant=why_relevant,
            why_not_relevant=why_not_relevant,
            recommended_contact_method=recommended_contact_method,
            outreach_angle=self._outreach_angle(website, sector, score),
            suggested_personalized_opener=self._opener(website, sector, score),
        )

    def _appears_new(self, kvk: KvkProfile) -> bool:
        if not kvk.formele_registratiedatum:
            return False
        try:
            year = int(kvk.formele_registratiedatum[:4])
        except ValueError:
            return False
        return date.today().year - year <= 2

    def _category(self, score: int) -> LeadCategory:
        if score >= 80:
            return "high_priority"
        if score >= 60:
            return "medium_priority"
        if score >= 40:
            return "low_priority"
        return "reject"

    def _contact_method(
        self, domain_status: DomainStatus, website: WebsiteProfile, kvk: KvkProfile
    ) -> ContactMethod:
        if domain_status in {"personal_site", "webshop", "unknown"}:
            return "do_not_contact"
        if domain_status in {"parked", "no_website"}:
            if kvk.kvk_match_status == "matched" and kvk.addresses:
                return "manual_review_required"
            return "do_not_contact"
        if kvk.ind_non_mailing is True:
            return "manual_review_required"
        if website.contact_page_url:
            return "contact_form"
        if website.public_business_emails:
            return "public_business_email"
        if website.public_phone_numbers:
            return "phone"
        if any("linkedin.com/company" in link for link in website.social_links):
            return "linkedin_company_page"
        return "manual_review_required"

    def _outreach_angle(self, website: WebsiteProfile, sector: str | None, score: int) -> str | None:
        if score < 40:
            return None
        if website.detected_pain_points:
            return "Help streamline requests, appointments, planning, documents, and recurring service workflows."
        if sector:
            return f"Explore workflow automation for a {sector.replace('_', ' ')} business."
        return None

    def _opener(self, website: WebsiteProfile, sector: str | None, score: int) -> str | None:
        if score < 40:
            return None
        name = website.detected_company_names[0] if website.detected_company_names else "jullie bedrijf"
        if website.detected_pain_points:
            return (
                f"Ik zag dat {name} online verwijst naar "
                f"{', '.join(website.detected_pain_points[:3])}; Aresis helpt zulke processen centraler af te handelen."
            )
        if sector:
            return f"Ik zag dat {name} actief is in {sector.replace('_', ' ')}; Aresis helpt servicebedrijven hun klantprocessen te automatiseren."
        return None

    def _size(self, kvk: KvkProfile) -> str | None:
        if kvk.aantal_vestigingen is None:
            return None
        if kvk.aantal_vestigingen <= 1:
            return "small"
        if kvk.aantal_vestigingen <= 5:
            return "small_medium"
        return "larger_multi_branch"
