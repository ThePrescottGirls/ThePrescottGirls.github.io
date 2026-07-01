#!/usr/bin/env python3
"""
database.py

Shared Oracle database layer.

Responsible for:
    - Opening the SQLite database
    - Creating and migrating the schema
    - Registering sites, discovery runs, pages, queries, and inspections

This file is intentionally plain and reusable. It should not know anything
about Google APIs, command-line arguments, dashboards, or presentation code.
"""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SCHEMA_VERSION = 2


class Database:
    """Small SQLite wrapper shared by Oracle tools."""

    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row

        # Keep SQLite behavior predictable as the database grows.
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")

    # ------------------------------------------------------------------
    # Database initialization / migration
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Create or migrate tables and record the current schema version."""
        cursor = self.connection.cursor()

        # Sites existed in the first version with property_url instead of
        # site_url.  If that older table is present, migrate it in place.
        if self.table_exists("sites"):
            site_columns = self.column_names("sites")

            if "site_url" not in site_columns and "property_url" in site_columns:
                cursor.execute("ALTER TABLE sites RENAME COLUMN property_url TO site_url")
                site_columns = self.column_names("sites")

            if "updated_at" not in site_columns:
                cursor.execute("ALTER TABLE sites ADD COLUMN updated_at TEXT")
                cursor.execute("""
                    UPDATE sites
                       SET updated_at = COALESCE(created_at, ?)
                     WHERE updated_at IS NULL
                """, (utc_now(),))
        else:
            cursor.execute("""
                CREATE TABLE sites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_url TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id INTEGER NOT NULL,
                run_type TEXT NOT NULL DEFAULT 'discovery',
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                message TEXT,
                FOREIGN KEY(site_id) REFERENCES sites(id)
            )
        """)

        if "run_type" not in self.column_names("runs"):
            cursor.execute("ALTER TABLE runs ADD COLUMN run_type TEXT NOT NULL DEFAULT 'discovery'")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                last_inspected_at TEXT,
                UNIQUE(site_id, url),
                FOREIGN KEY(site_id) REFERENCES sites(id)
            )
        """)

        if "last_inspected_at" not in self.column_names("pages"):
            cursor.execute("ALTER TABLE pages ADD COLUMN last_inspected_at TEXT")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id INTEGER NOT NULL,
                query_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                UNIQUE(site_id, query_text),
                FOREIGN KEY(site_id) REFERENCES sites(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inspections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                page_id INTEGER NOT NULL,
                inspected_at TEXT NOT NULL,
                verdict TEXT,
                coverage_state TEXT,
                indexing_state TEXT,
                robots_txt_state TEXT,
                page_fetch_state TEXT,
                google_canonical TEXT,
                user_canonical TEXT,
                raw_json TEXT,
                FOREIGN KEY(run_id) REFERENCES runs(id),
                FOREIGN KEY(page_id) REFERENCES pages(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS query_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                query_id INTEGER NOT NULL,
                page_id INTEGER,
                checked_at TEXT NOT NULL,
                position INTEGER,
                result_url TEXT,
                title TEXT,
                snippet TEXT,
                raw_json TEXT,
                FOREIGN KEY(run_id) REFERENCES runs(id),
                FOREIGN KEY(query_id) REFERENCES queries(id),
                FOREIGN KEY(page_id) REFERENCES pages(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        cursor.execute("""
            INSERT INTO metadata (key, value)
            VALUES ('schema_version', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (str(SCHEMA_VERSION),))

        self.connection.commit()

    # ------------------------------------------------------------------
    # Sites
    # ------------------------------------------------------------------

    def get_or_create_site(self, site_url: str) -> int:
        """Return the site id, creating it if necessary."""
        now = utc_now()
        cursor = self.connection.cursor()

        cursor.execute(
            "SELECT id FROM sites WHERE site_url = ?",
            (site_url,),
        )
        row = cursor.fetchone()

        if row:
            cursor.execute(
                "UPDATE sites SET updated_at = ? WHERE id = ?",
                (now, row["id"]),
            )
            self.connection.commit()
            return row["id"]

        cursor.execute("""
            INSERT INTO sites (site_url, created_at, updated_at)
            VALUES (?, ?, ?)
        """, (site_url, now, now))

        self.connection.commit()
        return cursor.lastrowid

    def get_site(self, site_id: int) -> sqlite3.Row | None:
        return self.fetchone("SELECT * FROM sites WHERE id = ?", (site_id,))

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def start_run(self, site_id: int, run_type: str = "discovery") -> int:
        cursor = self.connection.cursor()

        cursor.execute("""
            INSERT INTO runs (site_id, run_type, started_at, status)
            VALUES (?, ?, ?, ?)
        """, (site_id, run_type, utc_now(), "running"))

        self.connection.commit()
        return cursor.lastrowid

    def finish_run(self, run_id: int, status: str = "complete", message: str | None = None) -> None:
        self.execute("""
            UPDATE runs
               SET finished_at = ?,
                   status = ?,
                   message = ?
             WHERE id = ?
        """, (utc_now(), status, message, run_id))

    def get_run(self, run_id: int) -> sqlite3.Row | None:
        return self.fetchone("SELECT * FROM runs WHERE id = ?", (run_id,))

    def latest_run(self, site_id: int, run_type: str | None = None) -> sqlite3.Row | None:
        if run_type:
            return self.fetchone("""
                SELECT *
                  FROM runs
                 WHERE site_id = ?
                   AND run_type = ?
                 ORDER BY started_at DESC
                 LIMIT 1
            """, (site_id, run_type))

        return self.fetchone("""
            SELECT *
              FROM runs
             WHERE site_id = ?
             ORDER BY started_at DESC
             LIMIT 1
        """, (site_id,))

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------

    def register_page(self, site_id: int, url: str) -> tuple[int, bool]:
        """Register a page and return (page_id, is_new)."""
        now = utc_now()
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT id
              FROM pages
             WHERE site_id = ?
               AND url = ?
        """, (site_id, url))

        row = cursor.fetchone()

        if row:
            cursor.execute("""
                UPDATE pages
                   SET last_seen_at = ?
                 WHERE id = ?
            """, (now, row["id"]))
            self.connection.commit()
            return row["id"], False

        cursor.execute("""
            INSERT INTO pages (site_id, url, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?)
        """, (site_id, url, now, now))

        self.connection.commit()
        return cursor.lastrowid, True

    def get_page(self, page_id: int) -> sqlite3.Row | None:
        return self.fetchone("SELECT * FROM pages WHERE id = ?", (page_id,))

    def get_page_by_url(self, site_id: int, url: str) -> sqlite3.Row | None:
        return self.fetchone("""
            SELECT *
              FROM pages
             WHERE site_id = ?
               AND url = ?
        """, (site_id, url))

    def page_count(self, site_id: int) -> int:
        row = self.fetchone("SELECT COUNT(*) AS count FROM pages WHERE site_id = ?", (site_id,))
        return row["count"]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_or_create_query(self, site_id: int, query_text: str) -> int:
        """Register a search query that Oracle should track over time."""
        now = utc_now()
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT id
              FROM queries
             WHERE site_id = ?
               AND query_text = ?
        """, (site_id, query_text))

        row = cursor.fetchone()

        if row:
            cursor.execute("""
                UPDATE queries
                   SET updated_at = ?,
                       is_active = 1
                 WHERE id = ?
            """, (now, row["id"]))
            self.connection.commit()
            return row["id"]

        cursor.execute("""
            INSERT INTO queries (site_id, query_text, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, (site_id, query_text, now, now))

        self.connection.commit()
        return cursor.lastrowid

    def active_queries(self, site_id: int) -> list[sqlite3.Row]:
        return self.fetchall("""
            SELECT *
              FROM queries
             WHERE site_id = ?
               AND is_active = 1
             ORDER BY query_text
        """, (site_id,))

    # ------------------------------------------------------------------
    # Inspections
    # ------------------------------------------------------------------

    def register_inspection(
        self,
        run_id: int,
        page_id: int,
        verdict: str | None,
        coverage_state: str | None,
        indexing_state: str | None,
        robots_txt_state: str | None,
        page_fetch_state: str | None,
        google_canonical: str | None,
        user_canonical: str | None,
        raw_json: str | dict[str, Any] | None,
    ) -> int:
        cursor = self.connection.cursor()
        inspected_at = utc_now()

        cursor.execute("""
            INSERT INTO inspections (
                run_id,
                page_id,
                inspected_at,
                verdict,
                coverage_state,
                indexing_state,
                robots_txt_state,
                page_fetch_state,
                google_canonical,
                user_canonical,
                raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            page_id,
            inspected_at,
            verdict,
            coverage_state,
            indexing_state,
            robots_txt_state,
            page_fetch_state,
            google_canonical,
            user_canonical,
            encode_json(raw_json),
        ))

        cursor.execute("""
            UPDATE pages
               SET last_inspected_at = ?
             WHERE id = ?
        """, (inspected_at, page_id))

        self.connection.commit()
        return cursor.lastrowid

    def latest_inspections(self, site_id: int) -> list[sqlite3.Row]:
        """Return each page with its most recent inspection, if any."""
        return self.fetchall("""
            SELECT
                pages.url,
                pages.first_seen_at,
                pages.last_seen_at,
                inspections.inspected_at,
                inspections.verdict,
                inspections.coverage_state,
                inspections.indexing_state,
                inspections.page_fetch_state,
                inspections.google_canonical,
                inspections.user_canonical
              FROM pages
              LEFT JOIN inspections
                ON inspections.id = (
                    SELECT id
                      FROM inspections latest
                     WHERE latest.page_id = pages.id
                     ORDER BY latest.inspected_at DESC
                     LIMIT 1
                )
             WHERE pages.site_id = ?
             ORDER BY pages.url
        """, (site_id,))

    # ------------------------------------------------------------------
    # Query results
    # ------------------------------------------------------------------

    def register_query_result(
        self,
        run_id: int,
        query_id: int,
        page_id: int | None = None,
        position: int | None = None,
        result_url: str | None = None,
        title: str | None = None,
        snippet: str | None = None,
        raw_json: str | dict[str, Any] | None = None,
    ) -> int:
        cursor = self.connection.cursor()

        cursor.execute("""
            INSERT INTO query_results (
                run_id,
                query_id,
                page_id,
                checked_at,
                position,
                result_url,
                title,
                snippet,
                raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            query_id,
            page_id,
            utc_now(),
            position,
            result_url,
            title,
            snippet,
            encode_json(raw_json),
        ))

        self.connection.commit()
        return cursor.lastrowid

    # ------------------------------------------------------------------
    # Small SQL helpers
    # ------------------------------------------------------------------

    def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        cursor = self.connection.cursor()
        cursor.execute(sql, parameters)
        self.connection.commit()
        return cursor

    def fetchone(self, sql: str, parameters: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        cursor = self.connection.cursor()
        cursor.execute(sql, parameters)
        return cursor.fetchone()

    def fetchall(self, sql: str, parameters: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        cursor = self.connection.cursor()
        cursor.execute(sql, parameters)
        return cursor.fetchall()


    def table_exists(self, table_name: str) -> bool:
        row = self.fetchone("""
            SELECT name
              FROM sqlite_master
             WHERE type = 'table'
               AND name = ?
        """, (table_name,))
        return row is not None

    def column_names(self, table_name: str) -> set[str]:
        cursor = self.connection.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        return {row["name"] for row in cursor.fetchall()}

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def close(self) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


# Temporary compatibility alias for older imports while the rest of Oracle
# is being renamed from models.py to database.py.
OracleDatabase = Database



def database_path_for_site(site_url: str) -> Path:
    """Return the SQLite database path for a website URL."""
    parsed = urlparse(site_url)
    host = parsed.netloc.lower().strip()
    if host.startswith("www."):
        host = host[4:]
    safe_name = host.replace(".", "_")
    return Path("database") / f"{safe_name}.db"

def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def encode_json(value: str | dict[str, Any] | None) -> str | None:
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value, indent=2, sort_keys=True)
