"""Storage for the expense ledger.

Two backends share one small interface:

* SqliteStore    - a local file. Fine on your own computer. On Streamlit
                   Community Cloud the file is wiped whenever the app restarts,
                   so do not rely on it there.
* PostgresStore  - any hosted Postgres (Supabase, Neon, ...). Data survives
                   restarts. Used when a `database_url` setting is provided.

This module does not import Streamlit.
"""
from __future__ import annotations

import sqlite3
import time

# Entries from the original spreadsheet, listed top to bottom as they appeared.
# (date, source, who, item, amount, tag)
SEED_ROWS = [
    ("2026-11-04", "upi", "sru", "Chai times", 70, "Snacks"),
    ("2026-11-04", "upi", "aaku", "Rapido", 92, "Other"),
    ("2026-11-04", "upi", "aaku", "Rapido", 80, "Other"),
    ("2026-11-03", "upi", "aaku", "Groceries", 125, "Grocery"),
    ("2026-11-03", "upi", "aaku", "Pani Poori", 70, "Snacks"),
    ("2026-11-01", "upi", "aaku", "Stand (650 + 1300)", 1950, "Other"),
    ("2026-10-31", "upi", "aaku", "Food", 60, "Food"),
    ("2026-10-31", "upi", "aaku", "Food", 285, "Food"),
    ("2026-10-31", "upi", "aaku", "Bed Delivery", 1500, "Other"),
]

_COLUMNS = "id, spent_on, source, who, item, amount, tag, created_at"


class _SqlStore:
    kind = "sql"
    placeholder = "?"
    id_ddl = "INTEGER PRIMARY KEY AUTOINCREMENT"
    real_type = "REAL"

    def __init__(self, seed: bool = True):
        self._create_schema()
        if seed:
            self._seed_once()

    # -- connection plumbing -------------------------------------------------
    def _connect(self):
        raise NotImplementedError

    def _run(self, sql: str, params: tuple = (), fetch: bool = False):
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(sql.replace("?", self.placeholder), params)
            rows = None
            if fetch:
                cols = [c[0] for c in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            conn.commit()
            return rows
        finally:
            conn.close()

    # -- schema --------------------------------------------------------------
    def _create_schema(self):
        self._run(
            f"CREATE TABLE IF NOT EXISTS expenses ("
            f"id {self.id_ddl}, spent_on TEXT NOT NULL, source TEXT NOT NULL, who TEXT NOT NULL, "
            f"item TEXT NOT NULL, amount {self.real_type} NOT NULL, tag TEXT NOT NULL, "
            f"created_at {self.real_type} NOT NULL)"
        )
        self._run(
            f"CREATE TABLE IF NOT EXISTS tags (name TEXT PRIMARY KEY, created_at {self.real_type} NOT NULL)"
        )
        self._run("CREATE TABLE IF NOT EXISTS app_meta (k TEXT PRIMARY KEY, v TEXT NOT NULL)")

    def _seed_once(self):
        """Load the spreadsheet entries into a brand-new, empty ledger. Runs once."""
        if self._run("SELECT v FROM app_meta WHERE k = ?", ("seeded",), fetch=True):
            return
        count = self._run("SELECT COUNT(*) AS n FROM expenses", fetch=True)[0]["n"]
        if count == 0:
            base = time.time()
            for i, (spent_on, source, who, item, amount, tag) in enumerate(SEED_ROWS):
                self._run(
                    "INSERT INTO expenses (spent_on, source, who, item, amount, tag, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (spent_on, source, who, item, float(amount), tag, base - i),
                )
        self._run("INSERT INTO app_meta (k, v) VALUES (?, ?)", ("seeded", "1"))

    # -- expenses ------------------------------------------------------------
    def list_expenses(self) -> list[dict]:
        rows = self._run(
            f"SELECT {_COLUMNS} FROM expenses ORDER BY spent_on DESC, created_at DESC, id DESC", fetch=True
        )
        for r in rows:
            r["amount"] = float(r["amount"])
            r["created_at"] = float(r["created_at"])
        return rows

    def add_expense(self, rec: dict) -> None:
        self._run(
            "INSERT INTO expenses (spent_on, source, who, item, amount, tag, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (rec["spent_on"], rec["source"], rec["who"], rec["item"], float(rec["amount"]), rec["tag"], time.time()),
        )

    def update_expense(self, expense_id: int, rec: dict) -> None:
        self._run(
            "UPDATE expenses SET spent_on = ?, source = ?, who = ?, item = ?, amount = ?, tag = ? WHERE id = ?",
            (rec["spent_on"], rec["source"], rec["who"], rec["item"], float(rec["amount"]), rec["tag"], int(expense_id)),
        )

    def delete_expense(self, expense_id: int) -> None:
        self._run("DELETE FROM expenses WHERE id = ?", (int(expense_id),))

    # -- custom tags ---------------------------------------------------------
    def list_tags(self) -> list[str]:
        rows = self._run("SELECT name FROM tags ORDER BY created_at, name", fetch=True)
        return [r["name"] for r in rows]

    def add_tag(self, name: str) -> None:
        self._run(
            "INSERT INTO tags (name, created_at) VALUES (?, ?) ON CONFLICT (name) DO NOTHING",
            (name, time.time()),
        )


class SqliteStore(_SqlStore):
    kind = "sqlite"

    def __init__(self, path: str = "expenses.db", seed: bool = True):
        self.path = path
        super().__init__(seed=seed)

    def _connect(self):
        return sqlite3.connect(self.path, timeout=10)


class PostgresStore(_SqlStore):
    kind = "postgres"
    placeholder = "%s"
    id_ddl = "SERIAL PRIMARY KEY"
    real_type = "DOUBLE PRECISION"

    def __init__(self, url: str, seed: bool = True):
        self.url = url
        super().__init__(seed=seed)

    def _connect(self):
        import psycopg2  # imported here so SQLite-only setups do not need it

        return psycopg2.connect(self.url, connect_timeout=10)


def build_store(database_url: str | None = None, sqlite_path: str = "expenses.db", seed: bool = True):
    if database_url:
        return PostgresStore(database_url, seed=seed)
    return SqliteStore(sqlite_path, seed=seed)
