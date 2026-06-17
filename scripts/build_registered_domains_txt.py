#!/usr/bin/env python
import argparse
from datetime import date
from pathlib import Path

from app.domain_feed import extract_nl_domains_from_file, write_registered_domains_txt


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a dated TXT list of newly registered .nl domains from an input feed."
    )
    parser.add_argument("--input", required=True, help="Path to newline text or CSV feed export.")
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Registration date to write in the output header.",
    )
    parser.add_argument(
        "--source",
        default="external-feed",
        help="Human-readable source name for the output header.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output TXT path. Defaults to data/domains_registered_<date>.txt.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output or f"data/domains_registered_{args.date}.txt")
    result = extract_nl_domains_from_file(input_path)
    write_registered_domains_txt(result.domains, output_path, args.date, args.source)
    print(f"Wrote {len(result.domains)} .nl domains to {output_path}")


if __name__ == "__main__":
    main()

