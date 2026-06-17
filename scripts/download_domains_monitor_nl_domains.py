#!/usr/bin/env python
import argparse
from pathlib import Path

from dotenv import load_dotenv

from app.config import get_settings
from app.domains_monitor import (
    DomainsMonitorError,
    default_download_date,
    download_nl_daily_domains,
)


def main() -> None:
    load_dotenv()
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description="Download yesterday's newly registered .nl domains from Domains Monitor."
    )
    parser.add_argument(
        "--date",
        default=default_download_date(),
        help="Date to download, YYYY-MM-DD. Defaults to yesterday.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output TXT path. Defaults to data/domains_registered_<date>.txt.",
    )
    parser.add_argument(
        "--allow-current-fallback",
        action="store_true",
        help="If the historical date is inaccessible, fall back to the current global dailyupdate feed.",
    )
    args = parser.parse_args()

    if not settings.domains_monitor_api_token:
        raise SystemExit("Set DOMAINS_MONITOR_API_TOKEN in .env first.")

    output_path = Path(args.output or f"data/domains_registered_{args.date}.txt")
    try:
        domains = download_nl_daily_domains(
            settings.domains_monitor_api_token,
            args.date,
            output_path,
            allow_current_fallback=args.allow_current_fallback,
        )
    except DomainsMonitorError as exc:
        raise SystemExit(str(exc)) from None
    print(f"Wrote {len(domains)} .nl domains to {output_path}")


if __name__ == "__main__":
    main()
