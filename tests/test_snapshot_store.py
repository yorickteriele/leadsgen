from pathlib import Path

from app.snapshot_store import SnapshotStore


def test_snapshot_store_establishes_baseline(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots.db")

    result = store.save_snapshot_and_diff("2026-06-16", ["beta.nl", "alpha.nl"])

    assert result.total_domains == 2
    assert result.previous_snapshot_date is None
    assert result.added_domains == []


def test_snapshot_store_diffs_against_previous_snapshot(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots.db")
    store.save_snapshot_and_diff("2026-06-16", ["alpha.nl", "beta.nl"])

    result = store.save_snapshot_and_diff("2026-06-17", ["alpha.nl", "beta.nl", "gamma.nl"])

    assert result.previous_snapshot_date == "2026-06-16"
    assert result.added_domains == ["gamma.nl"]


def test_snapshot_store_replaces_same_day_snapshot(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots.db")
    store.save_snapshot_and_diff("2026-06-16", ["alpha.nl"])
    store.save_snapshot_and_diff("2026-06-17", ["alpha.nl", "beta.nl"])

    result = store.save_snapshot_and_diff("2026-06-17", ["alpha.nl", "gamma.nl"])

    assert result.previous_snapshot_date == "2026-06-16"
    assert result.added_domains == ["gamma.nl"]

