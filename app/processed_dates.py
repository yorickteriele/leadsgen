import sqlite3
from pathlib import Path


class ProcessedDates:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def is_processed(self, process_date: str) -> bool:
        if not self.database_path.exists():
            return False
        with sqlite3.connect(self.database_path) as conn:
            self._init(conn)
            row = conn.execute(
                "select 1 from processed_dates where process_date = ?", (process_date,)
            ).fetchone()
            return row is not None

    def mark_processed(self, process_date: str, domain_count: int) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as conn:
            self._init(conn)
            conn.execute(
                "insert or replace into processed_dates(process_date, domain_count) values (?, ?)",
                (process_date, domain_count),
            )
            conn.commit()

    def _init(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            create table if not exists processed_dates (
                process_date text primary key,
                processed_at text not null default current_timestamp,
                domain_count integer not null
            )
            """
        )
