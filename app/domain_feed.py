import csv
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


DOMAIN_RE = re.compile(r"\b(?:https?://)?(?:www\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)*\.nl)\b", re.I)


@dataclass(frozen=True)
class DomainFeedResult:
    domains: list[str]
    ignored_count: int


def extract_nl_domains(text: str) -> DomainFeedResult:
    found: list[str] = []
    ignored = 0
    for match in DOMAIN_RE.finditer(text):
        domain = normalize_domain(match.group(1))
        if domain:
            found.append(domain)
        else:
            ignored += 1
    unique = sorted(dict.fromkeys(found))
    return DomainFeedResult(domains=unique, ignored_count=ignored)


def extract_nl_domains_from_file(path: Path) -> DomainFeedResult:
    if path.suffix.lower() == ".csv":
        return _extract_from_csv(path)
    return extract_nl_domains(path.read_text(encoding="utf-8"))


def write_registered_domains_txt(
    domains: list[str], output_path: Path, registered_date: str, source: str
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# .nl domains registered today - {registered_date}",
        f"# source: {source}",
        f"# count: {len(domains)}",
        "",
    ]
    lines.extend(domains)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def normalize_domain(value: str) -> str | None:
    raw = value.strip().lower().strip(".,;()[]{}<>\"'")
    if not raw:
        return None
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or raw).strip(".")
    if host.startswith("www."):
        host = host[4:]
    if not host.endswith(".nl"):
        return None
    labels = host.split(".")
    if any(not label for label in labels):
        return None
    return host


def _extract_from_csv(path: Path) -> DomainFeedResult:
    text_domains: list[str] = []
    with path.open(newline="", encoding="utf-8") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        dialect = csv.Sniffer().sniff(sample) if sample else csv.excel
        reader = csv.DictReader(handle, dialect=dialect)
        if reader.fieldnames:
            preferred = [
                field
                for field in reader.fieldnames
                if field.lower() in {"domain", "domein", "name", "fqdn", "hostname"}
            ]
            fields = preferred or reader.fieldnames
            for row in reader:
                for field in fields:
                    value = row.get(field)
                    if value:
                        text_domains.append(value)
        else:
            handle.seek(0)
            text_domains.append(handle.read())
    return extract_nl_domains("\n".join(text_domains))

