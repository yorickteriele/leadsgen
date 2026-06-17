from pathlib import Path

from app.domains_monitor import diff_snapshot_files, write_domain_lines, write_snapshot_diff
from scripts.snapshot_domains_monitor_nl import previous_date


def test_previous_date() -> None:
    assert previous_date("2026-06-17") == "2026-06-16"


def test_diff_snapshot_files(tmp_path: Path) -> None:
    previous = tmp_path / "prev.txt"
    current = tmp_path / "current.txt"
    write_domain_lines(["alpha.nl", "beta.nl"], previous)
    write_domain_lines(["alpha.nl", "beta.nl", "gamma.nl"], current)

    assert diff_snapshot_files(previous, current) == ["gamma.nl"]


def test_write_snapshot_diff(tmp_path: Path) -> None:
    previous = tmp_path / "prev.txt"
    current = tmp_path / "current.txt"
    output = tmp_path / "new.txt"
    write_domain_lines(["alpha.nl"], previous)
    write_domain_lines(["alpha.nl", "beta.nl"], current)

    added = write_snapshot_diff(previous, current, output, "2026-06-17")

    assert added == ["beta.nl"]
    assert "beta.nl" in output.read_text(encoding="utf-8")

