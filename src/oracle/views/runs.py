from __future__ import annotations

import sqlite3
from views.common import fetchall, html_escape, print_heading, print_rows, table_exists, write_html_page

VIEW_NAME = "runs"
HTML_FILE = "runs.html"


def _rows(connection: sqlite3.Connection, run_limit: int):
    if not table_exists(connection, "runs"):
        return []

    return fetchall(
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
        (run_limit,),
    )


def show_text(connection: sqlite3.Connection, run_limit: int = 10, **kwargs) -> None:
    print_heading("Recent Runs", "-")

    if not table_exists(connection, "runs"):
        print("No runs table found.")
        print()
        return

    print_rows(
        _rows(connection, run_limit),
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


def render_html(connection: sqlite3.Connection, output_dir, nav_items, run_limit: int = 10, **kwargs):
    rows = _rows(connection, run_limit)
    body = ["<table><thead><tr><th>Run</th><th>Type</th><th>Status</th><th>Started</th><th>Finished</th><th>Message</th></tr></thead><tbody>"]
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{html_escape(row['id'])}</td>"
            f"<td>{html_escape(row['run_type'])}</td>"
            f"<td>{html_escape(row['status'])}</td>"
            f"<td>{html_escape(row['started_at'])}</td>"
            f"<td>{html_escape(row['finished_at'])}</td>"
            f"<td>{html_escape(row['message'])}</td>"
            "</tr>"
        )
    body.append("</tbody></table>")

    if not rows:
        body = ["<p>No runs found.</p>"]

    return write_html_page(output_dir, HTML_FILE, "Recent Runs", "\n".join(body), nav_items)
