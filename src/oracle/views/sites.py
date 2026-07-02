from __future__ import annotations

import sqlite3
from views.common import fetchall, html_escape, print_heading, print_rows, table_exists, write_html_page


VIEW_NAME = "sites"
HTML_FILE = "sites.html"


def _rows(connection: sqlite3.Connection):
    if not table_exists(connection, "sites"):
        return []

    return fetchall(
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


def show_text(connection: sqlite3.Connection, **kwargs) -> None:
    print_heading("Sites", "-")

    if not table_exists(connection, "sites"):
        print("No sites table found.")
        print()
        return

    print_rows(
        _rows(connection),
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


def render_html(connection: sqlite3.Connection, output_dir, nav_items, **kwargs):
    rows = _rows(connection)
    body = ["<table><thead><tr><th>ID</th><th>Site</th><th>Pages</th><th>Created</th><th>Updated</th></tr></thead><tbody>"]
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{html_escape(row['id'])}</td>"
            f"<td>{html_escape(row['site_url'])}</td>"
            f"<td>{html_escape(row['pages'])}</td>"
            f"<td>{html_escape(row['created_at'])}</td>"
            f"<td>{html_escape(row['updated_at'])}</td>"
            "</tr>"
        )
    body.append("</tbody></table>")

    if not rows:
        body = ["<p>No sites found.</p>"]

    return write_html_page(output_dir, HTML_FILE, "Sites", "\n".join(body), nav_items)
