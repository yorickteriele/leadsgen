#!/usr/bin/env python
import argparse
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

from app.config import get_settings
from app.domains_monitor import (
    DomainsMonitorError,
    download_full_nl_snapshot,
    write_snapshot_diff,
)


def previous_date(value: str) -> str:
    parsed = date.fromisoformat(value)
    return (parsed - timedelta(days=1)).isoformat()


def main() -> None:
    load_dotenv()
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description=(
            "Download the full .nl list from Domains Monitor and diff it against "
            "the previous snapshot to derive newly added .nl domains."
        )
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Snapshot date, YYYY-MM-DD. Defaults to today.",
    )
    parser.add_argument(
        "--snapshot-dir",
        default="data/snapshots",
        help="Directory where full .nl snapshots are stored.",
    )
    parser.add_argument(
        "--previous-snapshot",
        default=None,
        help="Optional explicit previous snapshot path.",
    )
    parser.add_argument(
        "--new-output",
        default=None,
        help="Output TXT for new domains. Defaults to data/domains_registered_<date>.txt.",
    )
    args = parser.parse_args()

    if not settings.domains_monitor_api_token:
        raise SystemExit("Set DOMAINS_MONITOR_API_TOKEN in .env first.")

    snapshot_dir = Path(args.snapshot_dir)
    current_snapshot = snapshot_dir / f"nl_domains_{args.date}.txt"
    previous_snapshot = Path(args.previous_snapshot) if args.previous_snapshot else (
        snapshot_dir / f"nl_domains_{previous_date(args.date)}.txt"
    )
    output_path = Path(args.new_output or f"data/domains_registered_{args.date}.txt")

    try:
        domains = download_full_nl_snapshot(
            settings.domains_monitor_api_token,
            args.date,
            current_snapshot,
        )
    except DomainsMonitorError as exc:
        raise SystemExit(str(exc)) from None

    print(f"Wrote full .nl snapshot with {len(domains)} domains to {current_snapshot}")

    if not previous_snapshot.exists():
        print(f"No previous snapshot found at {previous_snapshot}; run again tomorrow to produce a diff.")
        return

    added = write_snapshot_diff(previous_snapshot, current_snapshot, output_path, args.date)
    print(f"Wrote {len(added)} newly added .nl domains to {output_path}")


if __name__ == "__main__":
    main()

