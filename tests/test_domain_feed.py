from pathlib import Path

from app.domain_feed import (
    extract_nl_domains,
    extract_nl_domains_from_file,
    write_registered_domains_txt,
)


def test_extracts_normalizes_and_dedupes_nl_domains() -> None:
    result = extract_nl_domains(
        "https://www.Example.nl/path example.nl other.com sub.company.nl,"
    )

    assert result.domains == ["example.nl", "sub.company.nl"]


def test_extracts_domains_from_csv(tmp_path: Path) -> None:
    feed = tmp_path / "feed.csv"
    feed.write_text(
        "domain,created_at\nwww.alpha.nl,2026-06-17\nhttps://beta.nl/path,2026-06-17\n",
        encoding="utf-8",
    )

    result = extract_nl_domains_from_file(feed)

    assert result.domains == ["alpha.nl", "beta.nl"]


def test_writes_registered_domains_txt(tmp_path: Path) -> None:
    output = tmp_path / "domains.txt"

    write_registered_domains_txt(["alpha.nl", "beta.nl"], output, "2026-06-17", "test-feed")

    assert output.read_text(encoding="utf-8").splitlines() == [
        "# .nl domains registered today - 2026-06-17",
        "# source: test-feed",
        "# count: 2",
        "",
        "alpha.nl",
        "beta.nl",
    ]

