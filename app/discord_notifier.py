from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx

from app.agents.llm_scorer import LlmLeadScore
from app.models import LeadEnrichmentResponse


def _score_color(score: int) -> int:
    if score >= 80:
        return 0x2ECC71  # green
    if score >= 60:
        return 0xF39C12  # orange
    if score >= 40:
        return 0xF1C40F  # yellow
    return 0x95A5A6  # gray


def _category_emoji(category: str) -> str:
    return {
        "high_priority": "🟢",
        "medium_priority": "🟡",
        "low_priority": "🟠",
        "reject": "⚫",
    }.get(category, "⚪")


def _build_embed(lead: LeadEnrichmentResponse, llm: LlmLeadScore | None) -> dict:
    score = llm.fit_score if llm else lead.lead.fit_score
    category = lead.lead.lead_category
    emoji = _category_emoji(category)
    w = lead.website

    company = w.detected_company_names[0] if w.detected_company_names else None
    title = f"{emoji} {company} ({lead.domain})" if company else f"{emoji} {lead.domain}"

    description_parts: list[str] = []
    if llm and llm.analysis:
        description_parts.append(llm.analysis)
    elif lead.lead.outreach_angle:
        description_parts.append(lead.lead.outreach_angle)
    if llm and llm.outreach_hook:
        description_parts.append(f"**Outreach:** {llm.outreach_hook}")

    fields: list[dict] = []

    fields.append({
        "name": "Score",
        "value": f"{score}/100 · {category.replace('_', ' ').title()}",
        "inline": True,
    })
    fields.append({
        "name": "Status",
        "value": lead.domain_status.replace("_", " ").title(),
        "inline": True,
    })

    sector = w.detected_sector or lead.lead.sector
    if sector:
        fields.append({"name": "Sector", "value": sector.replace("_", " ").title(), "inline": True})

    contact_parts: list[str] = []
    if w.public_business_emails:
        contact_parts.append(w.public_business_emails[0])
    if w.public_phone_numbers:
        contact_parts.append(w.public_phone_numbers[0])
    if contact_parts:
        fields.append({"name": "Contact", "value": "\n".join(contact_parts), "inline": True})

    if w.detected_services:
        fields.append({
            "name": "Services",
            "value": ", ".join(w.detected_services[:4]),
            "inline": False,
        })

    if w.detected_pain_points:
        fields.append({
            "name": "Pain Points",
            "value": ", ".join(w.detected_pain_points[:4]),
            "inline": False,
        })

    if lead.mail_provider:
        fields.append({"name": "Mail", "value": lead.mail_provider, "inline": True})

    contact_method = lead.lead.recommended_contact_method.replace("_", " ").title()
    fields.append({"name": "Outreach via", "value": contact_method, "inline": True})

    embed: dict = {
        "title": title,
        "url": f"https://{lead.domain}",
        "color": _score_color(score),
        "fields": fields,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "Aresis Lead Enrichment · aresis.nl"},
    }
    if description_parts:
        embed["description"] = "\n\n".join(description_parts)

    return embed


class DiscordNotifier:
    BATCH_SIZE = 10

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    async def send_summary(
        self, date: str, total_new: int, processed: int, llm_enabled: bool
    ) -> None:
        llm_note = " · LLM scoring enabled" if llm_enabled else ""
        await self._post({
            "embeds": [{
                "title": f"📡 .nl Domain Snapshot — {date}",
                "description": (
                    f"**{total_new}** new domains detected · "
                    f"**{processed}** enriched{llm_note}"
                ),
                "color": 0x3498DB,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "footer": {"text": "Aresis Lead Enrichment"},
            }]
        })

    async def send_score_summary(
        self, high: int, medium: int, low: int, reject: int
    ) -> None:
        total = high + medium + low + reject
        await self._post({
            "embeds": [{
                "title": "📊 Score Distribution",
                "color": 0x3498DB,
                "fields": [
                    {"name": "🟢 High priority (≥80)", "value": str(high), "inline": True},
                    {"name": "🟡 Medium (60-79)", "value": str(medium), "inline": True},
                    {"name": "🟠 Low (40-59)", "value": str(low), "inline": True},
                    {"name": "⚫ Reject (<40)", "value": str(reject), "inline": True},
                    {"name": "Total enriched", "value": str(total), "inline": True},
                ],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }]
        })

    async def send_leads(
        self, leads: list[tuple[LeadEnrichmentResponse, LlmLeadScore | None]]
    ) -> None:
        embeds = [_build_embed(lead, llm) for lead, llm in leads]
        for i in range(0, len(embeds), self.BATCH_SIZE):
            batch = embeds[i : i + self.BATCH_SIZE]
            await self._post({"embeds": batch})
            if i + self.BATCH_SIZE < len(embeds):
                await asyncio.sleep(0.5)

    async def _post(self, payload: dict) -> None:
        async with httpx.AsyncClient(timeout=15.0) as client:
            for attempt in range(3):
                response = await client.post(self.webhook_url, json=payload)
                if response.status_code == 429:
                    retry_after = float(
                        response.json().get("retry_after", 1.0)
                        if response.headers.get("content-type", "").startswith("application/json")
                        else 1.0
                    )
                    await asyncio.sleep(retry_after)
                    continue
                response.raise_for_status()
                return
