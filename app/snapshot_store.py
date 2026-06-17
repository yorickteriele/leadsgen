import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SnapshotResult:
    snapshot_date: str
    total_domains: int
    added_domains: list[str]
    previous_snapshot_date: str | None


class SnapshotStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def save_snapshot_and_diff(
        self, snapshot_date: str, domains: list[str]
    ) -> SnapshotResult:
        unique_domains = sorted(dict.fromkeys(domains))
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            self._init(connection)
            previous_date = self._latest_snapshot_before(connection, snapshot_date)
            self._replace_snapshot(connection, snapshot_date, unique_domains)
            added = self._added_domains(connection, snapshot_date, previous_date)
            connection.commit()
        return SnapshotResult(
            snapshot_date=snapshot_date,
            total_domains=len(unique_domains),
            added_domains=added,
            previous_snapshot_date=previous_date,
        )

    def _init(self, connection: sqlite3.Connection) -> None:
        connection.execute("pragma journal_mode=wal")
        connection.execute("pragma synchronous=normal")
        connection.execute(
            """
            create table if not exists snapshots (
                snapshot_date text primary key,
                created_at text not null default current_timestamp,
                total_domains integer not null
            )
            """
        )
        connection.execute(
            """
            create table if not exists snapshot_domains (
                snapshot_date text not null,
                domain text not null,
                primary key (snapshot_date, domain)
            )
            """
        )
        connection.execute(
            "create index if not exists idx_snapshot_domains_domain on snapshot_domains(domain)"
        )

    def _latest_snapshot_before(
        self, connection: sqlite3.Connection, snapshot_date: str
    ) -> str | None:
        row = connection.execute(
            """
            select snapshot_date
            from snapshots
            where snapshot_date < ?
            order by snapshot_date desc
            limit 1
            """,
            (snapshot_date,),
        ).fetchone()
        return str(row[0]) if row else None

    def _replace_snapshot(
        self, connection: sqlite3.Connection, snapshot_date: str, domains: list[str]
    ) -> None:
        connection.execute("delete from snapshot_domains where snapshot_date = ?", (snapshot_date,))
        connection.executemany(
            "insert into snapshot_domains(snapshot_date, domain) values (?, ?)",
            ((snapshot_date, domain) for domain in domains),
        )
        connection.execute(
            """
            insert into snapshots(snapshot_date, total_domains)
            values (?, ?)
            on conflict(snapshot_date) do update set
                total_domains = excluded.total_domains,
                created_at = current_timestamp
            """,
            (snapshot_date, len(domains)),
        )

    def _added_domains(
        self,
        connection: sqlite3.Connection,
        snapshot_date: str,
        previous_date: str | None,
    ) -> list[str]:
        if previous_date is None:
            return []
        rows = connection.execute(
            """
            select current.domain
            from snapshot_domains current
            left join snapshot_domains previous
                on previous.snapshot_date = ?
                and previous.domain = current.domain
            where current.snapshot_date = ?
                and previous.domain is null
            order by current.domain
            """,
            (previous_date, snapshot_date),
        ).fetchall()
        return [str(row[0]) for row in rows]

