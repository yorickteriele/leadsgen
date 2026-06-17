from app.ct_feed import extract_domains_from_crtsh_rows, extract_registered_nl_domain


def test_extract_registered_nl_domain_from_subdomain() -> None:
    assert extract_registered_nl_domain("www.example.nl") == "example.nl"
    assert extract_registered_nl_domain("*.sub.example.nl") == "example.nl"
    assert extract_registered_nl_domain("example.com") is None


def test_extract_domains_from_crtsh_rows_filters_by_date() -> None:
    rows = [
        {
            "entry_timestamp": "2026-06-17T10:00:00.000",
            "common_name": "www.alpha.nl",
            "name_value": "www.alpha.nl\nbeta.nl",
        },
        {
            "entry_timestamp": "2026-06-16T10:00:00.000",
            "common_name": "old.nl",
            "name_value": "old.nl",
        },
    ]

    domains = extract_domains_from_crtsh_rows(rows, "2026-06-17")

    assert domains == ["alpha.nl", "beta.nl"]


def test_extract_domains_from_crtsh_rows_can_collect_without_date() -> None:
    rows = [
        {
            "entry_timestamp": "2026-06-16T10:00:00.000",
            "common_name": "old.nl",
            "name_value": "old.nl\nwww.new.nl",
        }
    ]

    domains = extract_domains_from_crtsh_rows(rows)

    assert domains == ["new.nl", "old.nl"]
