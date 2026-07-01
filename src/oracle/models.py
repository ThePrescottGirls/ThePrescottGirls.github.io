#!/usr/bin/env python3
"""
models.py

Oracle database layer.

Responsible for:
    - Opening oracle.db
    - Creating the schema (first run)
    - Basic CRUD operations

Nothing in this file should know anything about Google APIs.
"""

import sqlite3
from datetime import datetime, UTC
from pathlib import Path


class OracleDatabase:
    def __init__(self, db_path):
        self.db_path = Path(db_path)

        # Make sure the database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    # ------------------------------------------------------------------
    # Database initialization
    # ------------------------------------------------------------------

    def initialize(self):
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_url TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                message TEXT,
                FOREIGN KEY(site_id) REFERENCES sites(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                UNIQUE(site_id, url),
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

        self.conn.commit()

    # ------------------------------------------------------------------
    # Sites
    # ------------------------------------------------------------------

    def get_or_create_site(self, property_url):
        cursor = self.conn.cursor()

        cursor.execute(
            "SELECT id FROM sites WHERE property_url = ?",
            (property_url,)
        )

        row = cursor.fetchone()

        if row:
            return row["id"]

        now = datetime.now(UTC).isoformat(timespec="seconds")

        cursor.execute("""
            INSERT INTO sites (
                property_url,
                created_at
            )
            VALUES (?, ?)
        """, (
            property_url,
            now
        ))

        self.conn.commit()

        return cursor.lastrowid

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def start_run(self, site_id):
        cursor = self.conn.cursor()

        now = datetime.now(UTC).isoformat(timespec="seconds")

        cursor.execute("""
            INSERT INTO runs (
                site_id,
                started_at,
                status
            )
            VALUES (?, ?, ?)
        """, (
            site_id,
            now,
            "running"
        ))

        self.conn.commit()

        return cursor.lastrowid

    def finish_run(self, run_id, status="complete", message=None):
        cursor = self.conn.cursor()

        now = datetime.now(UTC).isoformat(timespec="seconds")

        cursor.execute("""
            UPDATE runs
               SET finished_at = ?,
                   status      = ?,
                   message     = ?
             WHERE id = ?
        """, (
            now,
            status,
            message,
            run_id
        ))

        self.conn.commit()

    def get_run(self, run_id):
        cursor = self.conn.cursor()

        cursor.execute(
            "SELECT * FROM runs WHERE id = ?",
            (run_id,)
        )

        return cursor.fetchone()

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------

    def register_page(self, site_id, url):
        cursor = self.conn.cursor()

        now = datetime.now(UTC).isoformat(timespec="seconds")

        cursor.execute("""
            SELECT id
              FROM pages
             WHERE site_id = ?
               AND url = ?
        """, (
            site_id,
            url
        ))

        row = cursor.fetchone()

        if row:
            cursor.execute("""
                UPDATE pages
                   SET last_seen_at = ?
                 WHERE id = ?
            """, (
                now,
                row["id"]
            ))

            self.conn.commit()

            return row["id"], False

        cursor.execute("""
            INSERT INTO pages (
                site_id,
                url,
                first_seen_at,
                last_seen_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            site_id,
            url,
            now,
            now
        ))

        self.conn.commit()

        return cursor.lastrowid, True

    def page_count(self, site_id):
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT COUNT(*)
              FROM pages
             WHERE site_id = ?
        """, (
            site_id,
        ))

        return cursor.fetchone()[0]

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def close(self):
        if self.conn:
            self.conn.close()

    def __del__(self):
        self.close()
