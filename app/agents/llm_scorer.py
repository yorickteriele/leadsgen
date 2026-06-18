from __future__ import annotations

from dataclasses import dataclass

import anthropic

from app.models import LeadEnrichmentResponse


@dataclass
class LlmLeadScore:
    fit_score: int
    analysis: str
    outreach_hook: str | None = None


_SCORE_TOOL = {
    "name": "score_lead",
    "description": (
        "Score a Dutch B2B lead for Aresis, which sells workflow/field-service "
        "automation to Dutch SME service businesses (installers, cleaners, landscapers, "
        "care providers, logistics, and similar). Return a fit_score (0-100), a concise "
        "1-2 sentence analysis in English, and an optional Dutch personalized outreach "
        "sentence for high-scoring leads."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "fit_score": {
                "type": "integer",
                "description": (
                    "Lead quality score 0-100. "
                    "80-100: clear Dutch SME service business, operational pain points visible, contactable. "
                    "60-79: likely B2B service, some signals present. "
                    "40-59: possible fit, needs more research. "
                    "0-39: poor fit (consumer, webshop, parked, too large, non-Dutch)."
                ),
            },
            "analysis": {
                "type": "string",
                "description": (
                    "1-2 sentences in English: what the business does, why it is or is not "
                    "a good fit for Aresis workflow automation."
                ),
            },
            "outreach_hook": {
                "type": "string",
                "description": (
                    "One personalized Dutch outreach sentence addressed to the company, "
                    "referencing something specific from their website. "
                    "Omit (null) for fit_score < 40."
                ),
            },
        },
        "required": ["fit_score", "analysis"],
    },
}

_SYSTEM = (
    "You are a Dutch B2B sales intelligence tool scoring leads for Aresis. "
    "Aresis sells workflow and field-service automation to Dutch SME service businesses: "
    "think installers, landscapers, cleaning companies, care providers, repair services, "
    "logistics operators. "
    "Good leads: Dutch, service-oriented, SME (2-50 employees), visible operational workflows. "
    "Poor leads: consumer shops, webshops, holding companies, government, large enterprises, "
    "parked domains, personal sites, non-Dutch businesses. "
    "Be commercially pragmatic and concise."
)


class LlmScoringAgent:
    def __init__(self, api_key: str, model: str = "claude-haiku-4-5") -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def score(self, lead: LeadEnrichmentResponse) -> LlmLeadScore:
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=512,
                system=_SYSTEM,
                tools=[_SCORE_TOOL],  # type: ignore[list-item]
                tool_choice={"type": "tool", "name": "score_lead"},
                messages=[{"role": "user", "content": self._prompt(lead)}],
            )
            for block in response.content:
                if block.type == "tool_use" and block.name == "score_lead":
                    data = block.input
                    return LlmLeadScore(
                        fit_score=max(0, min(100, int(data.get("fit_score", lead.lead.fit_score)))),
                        analysis=str(data.get("analysis", "")),
                        outreach_hook=data.get("outreach_hook") or None,
                    )
        except Exception:
            pass
        return LlmLeadScore(fit_score=lead.lead.fit_score, analysis="")

    def _prompt(self, lead: LeadEnrichmentResponse) -> str:
        w = lead.website
        l = lead.lead

        parts: list[str] = [f"Domain: {lead.domain}"]
        parts.append(f"Status: {lead.domain_status}")
        parts.append(f"Has website: {lead.has_website} | Has MX: {lead.has_mx}")
        if lead.mail_provider:
            parts.append(f"Mail provider: {lead.mail_provider}")
        if w.title:
            parts.append(f"Title: {w.title}")
        if w.meta_description:
            parts.append(f"Meta description: {w.meta_description}")
        if w.summary:
            parts.append(f"Page summary: {w.summary}")
        if w.detected_sector or l.sector:
            parts.append(f"Detected sector: {w.detected_sector or l.sector}")
        if w.detected_company_names:
            parts.append(f"Company names: {', '.join(w.detected_company_names[:3])}")
        if w.detected_services:
            parts.append(f"Services: {', '.join(w.detected_services[:6])}")
        if w.detected_pain_points:
            parts.append(f"Operational pain points: {', '.join(w.detected_pain_points[:6])}")
        if w.digital_maturity_notes:
            parts.append(f"Digital maturity: {', '.join(w.digital_maturity_notes[:4])}")
        if w.public_business_emails:
            parts.append(f"Email: {w.public_business_emails[0]}")
        if w.public_phone_numbers:
            parts.append(f"Phone: {w.public_phone_numbers[0]}")
        if l.why_relevant:
            parts.append(f"Positive signals: {'; '.join(l.why_relevant[:5])}")
        if l.why_not_relevant:
            parts.append(f"Negative signals: {'; '.join(l.why_not_relevant[:5])}")
        parts.append(f"Rule-based score: {l.fit_score}/100 ({l.lead_category})")

        return "\n".join(parts)
