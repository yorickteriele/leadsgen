from datetime import date
import zipfile
from io import BytesIO

from app.domains_monitor import (
    DomainsMonitorError,
    default_download_date,
    download_nl_daily_domains,
    extract_domains_monitor_domains,
    to_domains_monitor_date,
)


def test_default_download_date_is_yesterday() -> None:
    assert default_download_date(date(2026, 6, 17)) == "2026-06-16"


def test_formats_historical_date() -> None:
    assert to_domains_monitor_date("2026-06-16") == "16.06.2026"


def test_extracts_nl_domains_from_json_payload() -> None:
    payload = b'{"domains":["alpha.nl","beta.com"],"items":[{"domain":"www.gamma.nl"}]}'

    assert extract_domains_monitor_domains(payload, "application/json") == [
        "alpha.nl",
        "gamma.nl",
    ]


def test_extracts_nl_domains_from_zip_payload() -> None:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("daily.csv", "domain\nalpha.nl\nwww.beta.nl\nother.com\n")

    assert extract_domains_monitor_domains(buffer.getvalue(), "application/zip") == [
        "alpha.nl",
        "beta.nl",
    ]


def test_error_message_does_not_include_token(respx_mock, tmp_path) -> None:
    token = "secret-token"
    respx_mock.get(
        "https://domains-monitor.com/api/v1/secret-token/historical/dailyupdate/16.06.2026/"
    ).mock(return_value=__import__("httpx").Response(403))

    try:
        download_nl_daily_domains(token, "2026-06-16", tmp_path / "domains.txt")
    except DomainsMonitorError as exc:
        assert token not in str(exc)
    else:
        raise AssertionError("Expected DomainsMonitorError")


def test_can_fallback_to_current_daily_when_explicitly_enabled(respx_mock, tmp_path) -> None:
    token = "secret-token"
    respx_mock.get(
        "https://domains-monitor.com/api/v1/secret-token/historical/dailyupdate/16.06.2026/"
    ).mock(return_value=__import__("httpx").Response(403))
    respx_mock.get(
        "https://domains-monitor.com/api/v1/secret-token/get/dailyupdate/list/text/"
    ).mock(return_value=__import__("httpx").Response(200, text="alpha.nl\nbeta.com\n"))

    domains = download_nl_daily_domains(
        token,
        "2026-06-16",
        tmp_path / "domains.txt",
        allow_current_fallback=True,
    )

    assert domains == ["alpha.nl"]
