from __future__ import annotations

import sqlite3
from views.common import fetchall, fetchone, html_escape, print_heading, print_key_value, print_rows, table_exists, write_html_page

VIEW_NAME = "queries"
HTML_FILE = "queries.html"


def _rows(connection: sqlite3.Connection):
    if not table_exists(connection, "queries"):
        return []

    return fetchall(
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


def show_text(connection: sqlite3.Connection, **kwargs) -> None:
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
    print_heading("Tracked Queries", "-")

    print_rows(
        _rows(connection),
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


def render_html(connection: sqlite3.Connection, output_dir, nav_items, **kwargs):
    rows = _rows(connection)

    body = []
    if table_exists(connection, "queries"):
        active = fetchone(connection, "SELECT COUNT(*) AS count FROM queries WHERE is_active = 1")
        inactive = fetchone(connection, "SELECT COUNT(*) AS count FROM queries WHERE is_active = 0")
        body.append('<section class="grid">')
        body.append(f'<div class="metric"><div class="label">Active Queries</div><div class="value">{html_escape(active["count"])}</div></div>')
        body.append(f'<div class="metric"><div class="label">Inactive Queries</div><div class="value">{html_escape(inactive["count"])}</div></div>')
        body.append('</section>')

    body.append("<table><thead><tr><th>ID</th><th>Status</th><th>Query</th><th>Created</th><th>Updated</th></tr></thead><tbody>")
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{html_escape(row['id'])}</td>"
            f"<td>{html_escape(row['status'])}</td>"
            f"<td>{html_escape(row['query_text'])}</td>"
            f"<td>{html_escape(row['created_at'])}</td>"
            f"<td>{html_escape(row['updated_at'])}</td>"
            "</tr>"
        )
    body.append("</tbody></table>")

    if not rows:
        body = ["<p>No queries found.</p>"]

    return write_html_page(output_dir, HTML_FILE, "Queries", "\n".join(body), nav_items)
