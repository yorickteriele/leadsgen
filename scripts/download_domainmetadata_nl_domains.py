#!/usr/bin/env python
import argparse
import os
import zipfile
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

import httpx

from app.domain_feed import extract_nl_domains, write_registered_domains_txt


DEFAULT_URL_TEMPLATE = "https://domainmetadata.com/download/nl/nl-domains-{date}.zip"


def default_download_date(today: date | None = None) -> str:
    current = today or date.today()
    return (current - timedelta(days=1)).isoformat()


def domains_from_zip(content: bytes) -> list[str]:
    text_parts: list[str] = []
    with zipfile.ZipFile(BytesIO(content)) as archive:
        for name in archive.namelist():
            if name.lower().endswith((".csv", ".txt")):
                with archive.open(name) as handle:
                    text_parts.append(handle.read().decode("utf-8", errors="replace"))
    return extract_nl_domains("\n".join(text_parts)).domains


def main() -> None:
    default_date = default_download_date()
    parser = argparse.ArgumentParser(
        description="Download a DomainMetaData .nl ZIP export and write a plain TXT domain list."
    )
    parser.add_argument(
        "--date",
        default=default_date,
        help="Date for the daily DomainMetaData file, YYYY-MM-DD. Defaults to yesterday.",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Full DomainMetaData ZIP URL. Defaults to the .nl daily file URL for --date.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output TXT path. Defaults to data/domains_registered_<date>.txt.",
    )
    parser.add_argument(
        "--cookie",
        default=os.getenv("DOMAINMETADATA_COOKIE"),
        help="Optional authenticated Cookie header. Can also be set as DOMAINMETADATA_COOKIE.",
    )
    args = parser.parse_args()

    url = args.url or DEFAULT_URL_TEMPLATE.format(date=args.date)
    output_path = Path(args.output or f"data/domains_registered_{args.date}.txt")
    headers = {}
    if args.cookie:
        headers["Cookie"] = args.cookie

    response = httpx.get(url, headers=headers, follow_redirects=True, timeout=60.0)
    if "text/html" in response.headers.get("content-type", "").lower():
        raise SystemExit(
            "DomainMetaData returned HTML instead of a ZIP file. "
            "Log in/sign up and provide an authenticated cookie via DOMAINMETADATA_COOKIE."
        )
    response.raise_for_status()

    domains = domains_from_zip(response.content)
    write_registered_domains_txt(
        domains,
        output_path,
        args.date,
        "domainmetadata.com",
    )
    print(f"Wrote {len(domains)} .nl domains to {output_path}")


if __name__ == "__main__":
    main()
