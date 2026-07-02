#!/usr/bin/env python3
"""
dashboard.py

Rudimentary Oracle dashboard.

Reads Oracle's SQLite database and prints a simple status report.

Dashboard is intentionally read-only. It should not discover pages,
run searches, call Google APIs, or modify the database.
"""

from __future__ import annotations

import argparse
import sqlite3

from config import load_config
from database import database_path_for_site
from pathlib import Path
from typing import Iterable, Any
from urllib.parse import unquote


DEFAULT_RUN_LIMIT = 10


def connect_database(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)

    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}")

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def fetchone(connection: sqlite3.Connection, sql: str, parameters: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    cursor = connection.cursor()
    cursor.execute(sql, parameters)
    return cursor.fetchone()


def fetchall(connection: sqlite3.Connection, sql: str, parameters: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    cursor = connection.cursor()
    cursor.execute(sql, parameters)
    return cursor.fetchall()


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = fetchone(
        connection,
        """
        SELECT name
          FROM sqlite_master
         WHERE type = 'table'
           AND name = ?
        """,
        (table_name,),
    )
    return row is not None


def count_rows(connection: sqlite3.Connection, table_name: str) -> int:
    if not table_exists(connection, table_name):
        return 0

    row = fetchone(connection, f"SELECT COUNT(*) AS count FROM {table_name}")
    return int(row["count"])


def print_heading(title: str, underline: str = "=") -> None:
    print(title)
    print(underline * len(title))
    print()


def print_key_value(label: str, value) -> None:
    print(f"{label:<18}: {value}")


def print_rows(rows: Iterable[sqlite3.Row | dict[str, Any]], columns: list[tuple[str, str]], empty_message: str) -> None:
    rows = list(rows)

    if not rows:
        print(empty_message)
        return

    widths: list[int] = []
    for key, heading in columns:
        max_value_width = max(len(str(row[key] if row[key] is not None else "")) for row in rows)
        widths.append(max(len(heading), max_value_width))

    header = "  ".join(heading.ljust(width) for (_, heading), width in zip(columns, widths))
    rule = "  ".join("-" * width for width in widths)

    print(header)
    print(rule)

    for row in rows:
        values = []
        for index, (key, _) in enumerate(columns):
            value = row[key]
            values.append(str(value if value is not None else "").ljust(widths[index]))
        print("  ".join(values))


def show_overview(connection: sqlite3.Connection) -> None:
    print_heading("Oracle Dashboard")

    print_key_value("Sites", count_rows(connection, "sites"))
    print_key_value("Pages", count_rows(connection, "pages"))
    print_key_value("Runs", count_rows(connection, "runs"))
    print_key_value("Queries", count_rows(connection, "queries"))
    print_key_value("Query Results", count_rows(connection, "query_results"))
    print()


def show_sites(connection: sqlite3.Connection) -> None:
    print_heading("Sites", "-")

    if not table_exists(connection, "sites"):
        print("No sites table found.")
        print()
        return

    rows = fetchall(
        connection,
        """
        SELECT
            sites.id,
            sites.site_url,
            COUNT(pages.id) AS pages,
            sites.created_at,
            sites.updated_at
          FROM sites
          LEFT JOIN pages
            ON pages.site_id = sites.id
         GROUP BY sites.id
         ORDER BY sites.id
        """,
    )

    print_rows(
        rows,
        [
            ("id", "ID"),
            ("site_url", "Site"),
            ("pages", "Pages"),
            ("created_at", "Created"),
            ("updated_at", "Updated"),
        ],
        "No sites found.",
    )
    print()


def show_recent_runs(connection: sqlite3.Connection, limit: int = DEFAULT_RUN_LIMIT) -> None:
    print_heading("Recent Runs", "-")

    if not table_exists(connection, "runs"):
        print("No runs table found.")
        print()
        return

    rows = fetchall(
        connection,
        """
        SELECT
            runs.id,
            sites.site_url,
            runs.run_type,
            runs.started_at,
            runs.finished_at,
            runs.status,
            COALESCE(runs.message, '') AS message
          FROM runs
          JOIN sites
            ON sites.id = runs.site_id
         ORDER BY runs.started_at DESC,
                  runs.id DESC
         LIMIT ?
        """,
        (limit,),
    )

    print_rows(
        rows,
        [
            ("id", "Run"),
            ("run_type", "Type"),
            ("status", "Status"),
            ("started_at", "Started"),
            ("finished_at", "Finished"),
            ("message", "Message"),
        ],
        "No runs found.",
    )
    print()


def show_pages(connection: sqlite3.Connection, page_limit: int | None = None) -> None:
    print_heading("Pages", "-")

    if not table_exists(connection, "pages"):
        print("No pages table found.")
        print()
        return

    sql = """
        SELECT
            pages.url,
            pages.first_seen_at,
            pages.last_seen_at
          FROM pages
         ORDER BY pages.url
    """
    parameters: tuple[Any, ...] = ()

    if page_limit is not None:
        sql += " LIMIT ?"
        parameters = (page_limit,)

    rows = fetchall(connection, sql, parameters)

    display_rows = [
        {
            "url": unquote(row["url"]),
            "first_seen_at": row["first_seen_at"],
            "last_seen_at": row["last_seen_at"],
        }
        for row in rows
    ]

    print_rows(
        display_rows,
        [
            ("url", "URL"),
            ("first_seen_at", "First Seen"),
            ("last_seen_at", "Last Seen"),
        ],
        "No pages found.",
    )
    print()


def show_query_summary(connection: sqlite3.Connection) -> None:
    print_heading("Queries", "-")

    if not table_exists(connection, "queries"):
        print("No queries table found yet.")
        print()
        return

    active = fetchone(connection, "SELECT COUNT(*) AS count FROM queries WHERE is_active = 1")
    inactive = fetchone(connection, "SELECT COUNT(*) AS count FROM queries WHERE is_active = 0")

    print_key_value("Active Queries", active["count"])
    print_key_value("Inactive Queries", inactive["count"])

    if table_exists(connection, "query_results"):
        result_count = fetchone(connection, "SELECT COUNT(*) AS count FROM query_results")
        print_key_value("Query Results", result_count["count"])

    print()


def show_queries(connection: sqlite3.Connection) -> None:
    print_heading("Tracked Queries", "-")

    if not table_exists(connection, "queries"):
        print("No queries table found yet.")
        print()
        return

    rows = fetchall(
        connection,
        """
        SELECT
            id,
            CASE
                WHEN is_active = 1 THEN 'active'
                ELSE 'inactive'
            END AS status,
            query_text,
            created_at,
            updated_at
          FROM queries
         ORDER BY is_active DESC,
                  query_text
        """,
    )

    print_rows(
        rows,
        [
            ("id", "ID"),
            ("status", "Status"),
            ("query_text", "Query"),
            ("created_at", "Created"),
            ("updated_at", "Updated"),
        ],
        "No queries found.",
    )
    print()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show a rudimentary Oracle dashboard."
    )
    parser.add_argument(
        "--run-limit",
        type=int,
        default=DEFAULT_RUN_LIMIT,
        help=f"Number of recent runs to show. Default: {DEFAULT_RUN_LIMIT}",
    )
    parser.add_argument(
        "--page-limit",
        type=int,
        default=None,
        help="Number of pages to show. Default: all pages.",
    )
    parser.add_argument(
        "-view",
        choices=["all","summary","sites","runs","pages","queries","results"],
        default="all",
        help="Display a single dashboard view (default: all).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    config = load_config()
    db_path = database_path_for_site(config.website)

    print()
    print(f"Website : {config.website}")
    print(f"Database: {db_path}")
    print()

    with connect_database(db_path) as connection:
        view=args.view
        if view in ("all","summary"):
            show_overview(connection)
        if view in ("all","sites"):
            show_sites(connection)
        if view in ("all","runs"):
            show_recent_runs(connection, args.run_limit)
        if view in ("all","pages"):
            show_pages(connection, args.page_limit)
        if view in ("all","queries"):
            show_query_summary(connection)
            show_queries(connection)
        if view=="results":
            print_heading("Search Performance","-")
            print("Search Performance view coming next.")
            print()

    print("Dashboard complete.")


if __name__ == "__main__":
    main()
