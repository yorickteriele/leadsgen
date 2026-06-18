#!/usr/bin/env python
"""Download the daily .nl snapshot, enrich new domains, and post results to Discord."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from app.agents.llm_scorer import LlmScoringAgent, LlmLeadScore
from app.config import get_settings
from app.discord_notifier import DiscordNotifier
from app.domain_feed import write_registered_domains_txt
from app.domains_monitor import DomainsMonitorError, download_full_nl_snapshot
from app.models import EnrichDomainRequest, LeadEnrichmentResponse
from app.pipeline import LeadEnrichmentPipeline
from app.snapshot_store import SnapshotStore


async def enrich_domains(
    domains: list[str],
    pipeline: LeadEnrichmentPipeline,
    concurrency: int = 10,
    source: str = "domains-monitor-daily",
) -> list[LeadEnrichmentResponse]:
    sem = asyncio.Semaphore(concurrency)
    now = datetime.now(timezone.utc).isoformat()

    async def _enrich(domain: str) -> LeadEnrichmentResponse | None:
        async with sem:
            try:
                return await pipeline.enrich(
                    EnrichDomainRequest(domain=domain, first_seen_at=now, source=source)
                )
            except Exception as exc:
                print(f"  [warn] enrichment failed for {domain}: {exc}")
                return None

    results = await asyncio.gather(*(_enrich(d) for d in domains))
    return [r for r in results if r is not None]


async def llm_score_leads(
    leads: list[LeadEnrichmentResponse],
    scorer: LlmScoringAgent,
    min_score: int,
    concurrency: int = 5,
) -> dict[str, LlmLeadScore]:
    sem = asyncio.Semaphore(concurrency)
    eligible = [lead for lead in leads if lead.lead.fit_score >= min_score]

    async def _score(lead: LeadEnrichmentResponse) -> tuple[str, LlmLeadScore] | None:
        async with sem:
            try:
                result = await scorer.score(lead)
                return lead.domain, result
            except Exception as exc:
                print(f"  [warn] LLM scoring failed for {lead.domain}: {exc}")
                return None

    results = await asyncio.gather(*(_score(lead) for lead in eligible))
    return {domain: score for domain, score in results if results is not None and domain is not None}


async def main() -> None:
    load_dotenv()
    settings = get_settings()

    parser = argparse.ArgumentParser(
        description="Snapshot .nl domains, enrich new ones, notify Discord."
    )
    parser.add_argument("--database", default=settings.snapshot_database_path)
    parser.add_argument("--output-dir", default=settings.snapshot_output_dir)
    parser.add_argument(
        "--max-domains",
        type=int,
        default=settings.max_domains_per_run,
        help="Cap on new domains to enrich per run.",
    )
    args = parser.parse_args()

    # Unique key per run so repeated/manual runs always diff vs the previous actual run.
    run_id = datetime.now(timezone.utc).isoformat()
    display_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if not settings.domains_monitor_api_token:
        raise SystemExit("Set DOMAINS_MONITOR_API_TOKEN first.")

    print(f"[1/5] Downloading full .nl snapshot (run {run_id}) ...")
    try:
        domains = download_full_nl_snapshot(
            settings.domains_monitor_api_token,
            run_id,
            Path(args.output_dir) / ".last-download-check.txt",
        )
    except DomainsMonitorError as exc:
        raise SystemExit(str(exc)) from None

    check_file = Path(args.output_dir) / ".last-download-check.txt"
    if check_file.exists():
        check_file.unlink()

    print(f"[2/5] Diffing against SQLite snapshot store ...")
    result = SnapshotStore(Path(args.database)).save_snapshot_and_diff(run_id, domains)
    output_path = Path(args.output_dir) / f"domains_registered_{display_date}.txt"
    write_registered_domains_txt(
        result.added_domains,
        output_path,
        display_date,
        "domains-monitor.com-full-nl-snapshot-diff-sqlite",
    )

    total_new = len(result.added_domains)
    print(f"    Stored {result.total_domains} total .nl domains. {total_new} new vs {result.previous_snapshot_date or 'no baseline'}.")

    if result.previous_snapshot_date is None:
        print("    No previous snapshot; this run established the baseline. Nothing to notify.")
        return

    if total_new == 0:
        print("    No new domains detected today.")
        if settings.discord_webhook_url:
            notifier = DiscordNotifier(settings.discord_webhook_url)
            await notifier.send_summary(display_date, 0, 0, False)
        return

    to_enrich = result.added_domains[: args.max_domains]
    print(f"[3/5] Enriching {len(to_enrich)} domains (capped at {args.max_domains}) ...")
    pipeline = LeadEnrichmentPipeline(settings)
    enriched = await enrich_domains(to_enrich, pipeline)
    enriched.sort(key=lambda r: r.lead.fit_score, reverse=True)
    print(f"    Enriched {len(enriched)} domains successfully.")

    llm_scores: dict[str, LlmLeadScore] = {}
    llm_enabled = bool(settings.anthropic_api_key)
    if llm_enabled:
        print(f"[4/5] LLM scoring leads with score >= {settings.min_score_for_llm} ...")
        scorer = LlmScoringAgent(settings.anthropic_api_key, settings.llm_model)  # type: ignore[arg-type]
        llm_scores = await llm_score_leads(enriched, scorer, settings.min_score_for_llm)
        print(f"    LLM scored {len(llm_scores)} leads.")
    else:
        print("[4/5] Skipping LLM scoring (ANTHROPIC_API_KEY not set).")

    high = sum(1 for r in enriched if (llm_scores.get(r.domain) or r.lead).fit_score >= 80)
    medium = sum(1 for r in enriched if 60 <= (llm_scores.get(r.domain) or r.lead).fit_score < 80)
    low = sum(1 for r in enriched if 40 <= (llm_scores.get(r.domain) or r.lead).fit_score < 60)
    reject = sum(1 for r in enriched if (llm_scores.get(r.domain) or r.lead).fit_score < 40)

    print(f"    Distribution: {high} high | {medium} medium | {low} low | {reject} reject")

    if settings.discord_webhook_url:
        print(f"[5/5] Sending results to Discord ...")
        notifier = DiscordNotifier(settings.discord_webhook_url)

        await notifier.send_summary(display_date, total_new, len(enriched), llm_enabled)
        await asyncio.sleep(0.5)

        pairs = [(r, llm_scores.get(r.domain)) for r in enriched]
        await notifier.send_leads(pairs)
        await asyncio.sleep(0.5)

        await notifier.send_score_summary(high, medium, low, reject)
        print("    Discord notifications sent.")
    else:
        print("[5/5] Skipping Discord notification (DISCORD_WEBHOOK_URL not set).")

    print("\nDone.")
    print(f"  New .nl domains:    {total_new}")
    print(f"  Enriched:           {len(enriched)}")
    print(f"  LLM scored:         {len(llm_scores)}")
    print(f"  High priority:      {high}")
    print(f"  Medium priority:    {medium}")
    print(f"  Low priority:       {low}")
    print(f"  Rejected:           {reject}")


if __name__ == "__main__":
    asyncio.run(main())
