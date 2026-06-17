import json
import zipfile
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx

from app.domain_feed import extract_nl_domains, write_registered_domains_txt


API_BASE_URL = "https://domains-monitor.com/api/v1"


class DomainsMonitorError(RuntimeError):
    pass


def default_download_date(today: date | None = None) -> str:
    current = today or date.today()
    return (current - timedelta(days=1)).isoformat()


def to_domains_monitor_date(value: str) -> str:
    year, month, day = value.split("-")
    return f"{day}.{month}.{year}"


def extract_domains_monitor_domains(content: bytes, content_type: str = "") -> list[str]:
    if _looks_like_zip(content, content_type):
        return _extract_from_zip(content)

    text = content.decode("utf-8", errors="replace")
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            strings = list(_json_strings(json.loads(text)))
            return extract_nl_domains("\n".join(strings)).domains
        except json.JSONDecodeError:
            pass
    return extract_nl_domains(text).domains


def download_nl_daily_domains(
    token: str,
    target_date: str,
    output_path: Path,
    base_url: str = API_BASE_URL,
    allow_current_fallback: bool = False,
) -> list[str]:
    domains = _fetch_historical_daily(token, target_date, base_url, allow_current_fallback)
    if domains is None and allow_current_fallback:
        domains = _fetch_current_daily(token, base_url)
    if domains is None:
        raise DomainsMonitorError(
            f"Domains Monitor historical dailyupdate for {target_date} is not accessible with this account. "
            "The API returned an access error for the dated historical dataset."
        )
    write_registered_domains_txt(
        domains,
        output_path,
        target_date,
        "domains-monitor.com",
    )
    return domains


def download_full_nl_snapshot(
    token: str,
    snapshot_date: str,
    snapshot_path: Path,
    base_url: str = API_BASE_URL,
) -> list[str]:
    domains = _fetch_full_nl_list(token, base_url)
    write_domain_lines(domains, snapshot_path)
    return domains


def diff_snapshot_files(previous_path: Path, current_path: Path) -> list[str]:
    previous = set(read_domain_lines(previous_path))
    current = set(read_domain_lines(current_path))
    return sorted(current - previous)


def write_snapshot_diff(
    previous_path: Path,
    current_path: Path,
    output_path: Path,
    target_date: str,
) -> list[str]:
    added = diff_snapshot_files(previous_path, current_path)
    write_registered_domains_txt(
        added,
        output_path,
        target_date,
        "domains-monitor.com-full-nl-snapshot-diff",
    )
    return added


def read_domain_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return extract_nl_domains(path.read_text(encoding="utf-8")).domains


def write_domain_lines(domains: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(sorted(dict.fromkeys(domains))) + "\n", encoding="utf-8")


def _fetch_historical_daily(
    token: str,
    target_date: str,
    base_url: str,
    allow_current_fallback: bool,
) -> list[str] | None:
    url = f"{base_url}/{token}/historical/dailyupdate/{to_domains_monitor_date(target_date)}/"
    response = _get(url, allow_status={403, 404} if allow_current_fallback else set())
    if response.status_code in {403, 404} and allow_current_fallback:
        return None
    return extract_domains_monitor_domains(
        response.content, response.headers.get("content-type", "")
    )


def _fetch_current_daily(token: str, base_url: str) -> list[str]:
    url = f"{base_url}/{token}/get/dailyupdate/list/text/"
    response = _get(url)
    return extract_domains_monitor_domains(
        response.content, response.headers.get("content-type", "")
    )


def _fetch_full_nl_list(token: str, base_url: str) -> list[str]:
    url = f"{base_url}/{token}/get/nl/list/text/"
    response = _get(url)
    return extract_domains_monitor_domains(
        response.content, response.headers.get("content-type", "")
    )


def _get(url: str, allow_status: set[int] | None = None) -> httpx.Response:
    allow_status = allow_status or set()
    try:
        response = httpx.get(url, follow_redirects=True, timeout=120.0)
        if response.status_code in allow_status:
            return response
        response.raise_for_status()
        return response
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        raise DomainsMonitorError(
            f"Domains Monitor request failed with HTTP {status}; check token, plan access, and endpoint availability."
        ) from None
    except httpx.HTTPError as exc:
        raise DomainsMonitorError(
            "Domains Monitor request failed; check network connectivity and API availability."
        ) from None


def _extract_from_zip(content: bytes) -> list[str]:
    text_parts: list[str] = []
    with zipfile.ZipFile(BytesIO(content)) as archive:
        for name in archive.namelist():
            if name.lower().endswith((".csv", ".txt", ".json")):
                with archive.open(name) as handle:
                    text_parts.append(handle.read().decode("utf-8", errors="replace"))
    return extract_nl_domains("\n".join(text_parts)).domains


def _json_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        strings: list[str] = []
        for item in value:
            strings.extend(_json_strings(item))
        return strings
    if isinstance(value, dict):
        strings = []
        for item in value.values():
            strings.extend(_json_strings(item))
        return strings
    return []


def _looks_like_zip(content: bytes, content_type: str) -> bool:
    return content.startswith(b"PK") or "zip" in content_type.lower()
