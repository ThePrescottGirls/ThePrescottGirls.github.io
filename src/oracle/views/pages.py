from __future__ import annotations

import sqlite3
from urllib.parse import unquote
from views.common import fetchall, html_escape, print_heading, print_rows, table_exists, write_html_page

VIEW_NAME = "pages"
HTML_FILE = "pages.html"


def _rows(connection: sqlite3.Connection, page_limit: int | None):
    if not table_exists(connection, "pages"):
        return []

    sql = """
        SELECT
            pages.url,
            pages.first_seen_at,
            pages.last_seen_at
          FROM pages
         ORDER BY pages.url
    """
    parameters: tuple = ()

    if page_limit is not None:
        sql += " LIMIT ?"
        parameters = (page_limit,)

    rows = fetchall(connection, sql, parameters)
    return [
        {
            "url": unquote(row["url"]),
            "first_seen_at": row["first_seen_at"],
            "last_seen_at": row["last_seen_at"],
        }
        for row in rows
    ]


def show_text(connection: sqlite3.Connection, page_limit: int | None = None, **kwargs) -> None:
    print_heading("Pages", "-")

    if not table_exists(connection, "pages"):
        print("No pages table found.")
        print()
        return

    print_rows(
        _rows(connection, page_limit),
        [
            ("url", "URL"),
            ("first_seen_at", "First Seen"),
            ("last_seen_at", "Last Seen"),
        ],
        "No pages found.",
    )
    print()


def render_html(connection: sqlite3.Connection, output_dir, nav_items, page_limit: int | None = None, **kwargs):
    rows = _rows(connection, page_limit)
    body = ["<table><thead><tr><th>URL</th><th>First Seen</th><th>Last Seen</th></tr></thead><tbody>"]
    for row in rows:
        url = row["url"]
        body.append(
            "<tr>"
            f'<td><a href="{html_escape(url)}">{html_escape(url)}</a></td>'
            f"<td>{html_escape(row['first_seen_at'])}</td>"
            f"<td>{html_escape(row['last_seen_at'])}</td>"
            "</tr>"
        )
    body.append("</tbody></table>")

    if not rows:
        body = ["<p>No pages found.</p>"]

    return write_html_page(output_dir, HTML_FILE, "Pages", "\n".join(body), nav_items)
