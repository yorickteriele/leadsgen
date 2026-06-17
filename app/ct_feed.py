from datetime import date
import re

import httpx


CRT_SH_URL = "https://crt.sh/"
HOST_RE = re.compile(r"^(?:\*\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)*\.nl)$", re.I)


def extract_registered_nl_domain(hostname: str) -> str | None:
    candidate = hostname.strip().lower().strip(".")
    match = HOST_RE.match(candidate)
    if not match:
        return None
    labels = match.group(1).split(".")
    if len(labels) < 2:
        return None
    return ".".join(labels[-2:])


def extract_domains_from_crtsh_rows(
    rows: list[dict], observed_date: str | None = None, limit: int | None = None
) -> list[str]:
    domains: set[str] = set()
    for row in rows:
        entry_timestamp = str(row.get("entry_timestamp") or "")
        if observed_date and not entry_timestamp.startswith(observed_date):
            continue
        names = []
        for key in ["common_name", "name_value"]:
            value = row.get(key)
            if isinstance(value, str):
                names.extend(value.splitlines())
        for name in names:
            domain = extract_registered_nl_domain(name)
            if domain:
                domains.add(domain)
                if limit and len(domains) >= limit:
                    return sorted(domains)
    return sorted(domains)


async def fetch_crtsh_observed_nl_domains(
    observed_date: str | None = None,
    timeout_seconds: float = 60.0,
    limit: int | None = None,
) -> list[str]:
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.get(CRT_SH_URL, params={"q": "%.nl", "output": "json"})
        response.raise_for_status()
        rows = response.json()
    if not isinstance(rows, list):
        return []
    return extract_domains_from_crtsh_rows(rows, observed_date, limit)
