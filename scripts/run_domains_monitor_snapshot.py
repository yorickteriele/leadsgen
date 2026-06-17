#!/usr/bin/env python
import argparse
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from app.config import get_settings
from app.domain_feed import write_registered_domains_txt
from app.domains_monitor import DomainsMonitorError, download_full_nl_snapshot
from app.snapshot_store import SnapshotStore


def main() -> None:
    load_dotenv()
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description="Download the full .nl list, store it in SQLite, and export newly added domains."
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Snapshot date, YYYY-MM-DD. Defaults to today.",
    )
    parser.add_argument(
        "--database",
        default=settings.snapshot_database_path,
        help="SQLite database path. Defaults to SNAPSHOT_DATABASE_PATH.",
    )
    parser.add_argument(
        "--output-dir",
        default=settings.snapshot_output_dir,
        help="Directory for daily added-domain TXT exports.",
    )
    args = parser.parse_args()

    if not settings.domains_monitor_api_token:
        raise SystemExit("Set DOMAINS_MONITOR_API_TOKEN first.")

    try:
        domains = download_full_nl_snapshot(
            settings.domains_monitor_api_token,
            args.date,
            Path(args.output_dir) / ".last-download-check.txt",
        )
    except DomainsMonitorError as exc:
        raise SystemExit(str(exc)) from None

    # The download helper writes plain lines for inspection; SQLite is the canonical state.
    check_file = Path(args.output_dir) / ".last-download-check.txt"
    if check_file.exists():
        check_file.unlink()

    result = SnapshotStore(Path(args.database)).save_snapshot_and_diff(args.date, domains)
    output_path = Path(args.output_dir) / f"domains_registered_{args.date}.txt"
    write_registered_domains_txt(
        result.added_domains,
        output_path,
        args.date,
        "domains-monitor.com-full-nl-snapshot-diff-sqlite",
    )

    print(f"Stored {result.total_domains} .nl domains for {args.date} in {args.database}")
    if result.previous_snapshot_date is None:
        print("No previous snapshot in SQLite; this run established the baseline.")
    else:
        print(
            f"Compared with {result.previous_snapshot_date}; "
            f"wrote {len(result.added_domains)} new domains to {output_path}"
        )


if __name__ == "__main__":
    main()

