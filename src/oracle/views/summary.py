from __future__ import annotations

import sqlite3

from views.common import (
    count_rows,
    fetchone,
    html_escape,
    print_heading,
    print_key_value,
    table_exists,
    write_html_page,
)


VIEW_NAME = "summary"
HTML_FILE = "index.html"


def _count_where(connection: sqlite3.Connection, table_name: str, where_sql: str) -> int:
    if not table_exists(connection, table_name):
        return 0

    row = fetchone(connection, f"SELECT COUNT(*) AS count FROM {table_name} WHERE {where_sql}")
    return int(row["count"]) if row else 0


def _search_provider_calls(connection: sqlite3.Connection) -> int:
    if table_exists(connection, "search_responses"):
        return count_rows(connection, "search_responses")

    if table_exists(connection, "query_results"):
        row = fetchone(
            connection,
            """
            SELECT COUNT(*) AS count
              FROM (
                    SELECT DISTINCT run_id, query_id
                      FROM query_results
                   )
            """,
        )
        return int(row["count"]) if row else 0

    return 0


def _ai_overviews(connection: sqlite3.Connection) -> int:
    if not table_exists(connection, "serp_features"):
        return 0

    row = fetchone(
        connection,
        """
        SELECT COUNT(*) AS count
          FROM serp_features
         WHERE feature_type = 'ai_overview'
        """,
    )
    return int(row["count"]) if row else 0


def _last_updated(connection: sqlite3.Connection) -> str:
    candidates = []

    for table_name, column_name in [
        ("sites", "updated_at"),
        ("pages", "last_seen_at"),
        ("queries", "updated_at"),
        ("runs", "finished_at"),
        ("query_results", "checked_at"),
    ]:
        if table_exists(connection, table_name):
            row = fetchone(connection, f"SELECT MAX({column_name}) AS value FROM {table_name}")
            if row and row["value"]:
                candidates.append(row["value"])

    return max(candidates) if candidates else "unknown"


def _metrics(connection: sqlite3.Connection, site_url: str) -> dict[str, object]:
    return {
        "website": site_url,
        "discovered_pages": count_rows(connection, "pages"),
        "suggested_queries": _count_where(connection, "queries", "is_active = 1"),
        "manual_queries": _count_where(connection, "queries", "is_active = 0"),
        "serpapi_searches": _search_provider_calls(connection),
        "ai_overviews": _ai_overviews(connection),
        "last_updated": _last_updated(connection),
    }


def show_text(connection: sqlite3.Connection, site_url: str, **kwargs) -> None:
    metrics = _metrics(connection, site_url)

    print_heading("Oracle Dashboard")

    print_key_value("Website", metrics["website"])
    print_key_value("Discovered Pages", metrics["discovered_pages"])
    print_key_value("Suggested Queries", metrics["suggested_queries"])
    print_key_value("Manual Queries", metrics["manual_queries"])
    print_key_value("SerpApi Searches", metrics["serpapi_searches"])
    print_key_value("AI Overviews", metrics["ai_overviews"])
    print_key_value("Last Updated", metrics["last_updated"])
    print()


def render_html(connection: sqlite3.Connection, output_dir, nav_items, site_url: str, **kwargs):
    metrics = _metrics(connection, site_url)

    metric_cards = [
        ("Discovered Pages", metrics["discovered_pages"]),
        ("Suggested Queries", metrics["suggested_queries"]),
        ("Manual Queries", metrics["manual_queries"]),
        ("SerpApi Searches", metrics["serpapi_searches"]),
        ("AI Overviews", metrics["ai_overviews"]),
    ]

    body = []

    body.append('<section class="card">')
    body.append("<h2>Website</h2>")
    body.append(f'<p><a href="{html_escape(metrics["website"])}">{html_escape(metrics["website"])}</a></p>')
    body.append(f'<p class="muted">Last updated: {html_escape(metrics["last_updated"])}</p>')
    body.append("</section>")

    body.append('<section class="grid">')
    for label, value in metric_cards:
        body.append(
            f'<div class="metric"><div class="label">{html_escape(label)}</div>'
            f'<div class="value">{html_escape(value)}</div></div>'
        )
    body.append("</section>")

    return write_html_page(output_dir, HTML_FILE, "Oracle Dashboard", "\n".join(body), nav_items)
