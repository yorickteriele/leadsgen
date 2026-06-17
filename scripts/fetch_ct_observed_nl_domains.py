#!/usr/bin/env python
import argparse
import asyncio
from datetime import date
from pathlib import Path

from app.ct_feed import fetch_crtsh_observed_nl_domains
from app.domain_feed import write_registered_domains_txt


async def run() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch .nl domains newly observed in public Certificate Transparency logs via crt.sh. "
            "This is not a complete newly registered domain feed."
        )
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Optional CT entry date to filter on, YYYY-MM-DD. Omit to collect a broad public sample.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output TXT path. Defaults to data/ct_observed_nl_domains_<date>.txt.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="HTTP timeout in seconds for crt.sh.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Maximum domains to write. Use 0 for no limit.",
    )
    args = parser.parse_args()

    label_date = args.date or date.today().isoformat()
    output_path = Path(args.output or f"data/ct_observed_nl_domains_{label_date}.txt")
    limit = args.limit if args.limit > 0 else None
    domains = await fetch_crtsh_observed_nl_domains(args.date, args.timeout, limit)
    write_registered_domains_txt(
        domains,
        output_path,
        label_date,
        "certificate-transparency-crtsh-partial",
    )
    print(f"Wrote {len(domains)} CT-observed .nl domains to {output_path}")
    print("Warning: Certificate Transparency is a partial signal, not all newly registered .nl domains.")


if __name__ == "__main__":
    asyncio.run(run())
