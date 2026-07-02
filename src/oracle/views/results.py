from __future__ import annotations

import sqlite3
from urllib.parse import unquote

from views.common import (
    domain_from_url,
    fetchall,
    fetchone,
    html_escape,
    print_heading,
    short_path_from_url,
    table_exists,
    write_html_page,
)

VIEW_NAME = "results"
HTML_FILE = "results.html"


def _feature_present(connection: sqlite3.Connection, query_id: int, run_id: int, feature_type: str) -> bool:
    if not table_exists(connection, "serp_features"):
        return False

    row = fetchone(
        connection,
        """
        SELECT 1
          FROM serp_features
         WHERE query_id = ?
           AND run_id = ?
           AND feature_type = ?
         LIMIT 1
        """,
        (query_id, run_id, feature_type),
    )
    return row is not None


def _query_rows(connection: sqlite3.Connection):
    if not table_exists(connection, "queries") or not table_exists(connection, "query_results"):
        return []

    return fetchall(
        connection,
        """
        SELECT
            queries.id,
            queries.query_text,
            queries.is_active,
            COUNT(DISTINCT query_results.run_id) AS run_count,
            COUNT(query_results.id) AS result_count,
            MAX(query_results.checked_at) AS last_checked_at
          FROM queries
          JOIN query_results
            ON query_results.query_id = queries.id
         GROUP BY queries.id
         ORDER BY last_checked_at DESC,
                  queries.query_text
        """,
    )


def _latest_run_id(connection: sqlite3.Connection, query_id: int) -> int | None:
    row = fetchone(
        connection,
        """
        SELECT run_id
          FROM query_results
         WHERE query_id = ?
         ORDER BY checked_at DESC,
                  run_id DESC
         LIMIT 1
        """,
        (query_id,),
    )
    return int(row["run_id"]) if row else None


def _top_results(connection: sqlite3.Connection, query_id: int, run_id: int, limit: int = 5):
    return fetchall(
        connection,
        """
        SELECT
            query_results.position,
            query_results.result_url,
            query_results.title,
            query_results.source,
            query_results.page_id,
            pages.url AS matched_page_url
          FROM query_results
          LEFT JOIN pages
            ON pages.id = query_results.page_id
         WHERE query_results.query_id = ?
           AND query_results.run_id = ?
         ORDER BY query_results.position
         LIMIT ?
        """,
        (query_id, run_id, limit),
    )


def _best_site_rank(connection: sqlite3.Connection, query_id: int, run_id: int) -> tuple[int | None, str | None]:
    row = fetchone(
        connection,
        """
        SELECT
            query_results.position,
            pages.url AS matched_page_url
          FROM query_results
          JOIN pages
            ON pages.id = query_results.page_id
         WHERE query_results.query_id = ?
           AND query_results.run_id = ?
         ORDER BY query_results.position
         LIMIT 1
        """,
        (query_id, run_id),
    )

    if not row:
        return None, None

    return int(row["position"]), row["matched_page_url"]


def build_model(connection: sqlite3.Connection, site_url: str, result_limit: int = 5):
    site_domain = domain_from_url(site_url)
    model = []

    for query in _query_rows(connection):
        run_id = _latest_run_id(connection, query["id"])
        if run_id is None:
            continue

        top_results = []
        for result in _top_results(connection, query["id"], run_id, result_limit):
            top_results.append(
                {
                    "position": result["position"],
                    "title": result["title"] or "",
                    "url": result["result_url"] or "",
                    "domain": domain_from_url(result["result_url"]),
                    "source": result["source"] or "",
                    "page_id": result["page_id"],
                    "matched_page_url": result["matched_page_url"],
                }
            )

        best_rank, matched_page_url = _best_site_rank(connection, query["id"], run_id)

        model.append(
            {
                "query_id": query["id"],
                "query_text": query["query_text"],
                "status": "active" if query["is_active"] else "inactive",
                "run_count": query["run_count"],
                "result_count": query["result_count"],
                "last_checked_at": query["last_checked_at"],
                "latest_run_id": run_id,
                "site_domain": site_domain,
                "website_found": best_rank is not None,
                "best_rank": best_rank,
                "matched_page_url": matched_page_url,
                "ai_overview": _feature_present(connection, query["id"], run_id, "ai_overview"),
                "top_results": top_results,
            }
        )

    return model


def show_text(connection: sqlite3.Connection, site_url: str, result_limit: int = 5, **kwargs) -> None:
    print_heading("Search Performance", "-")

    if not table_exists(connection, "query_results"):
        print("No query results found.")
        print()
        return

    model = build_model(connection, site_url=site_url, result_limit=result_limit)

    if not model:
        print("No observed queries found.")
        print()
        return

    for item in model:
        print(item["query_text"])
        print(f"    Status        : {item['status']}")
        print(f"    Runs          : {item['run_count']}")
        print(f"    Last checked  : {item['last_checked_at']}")
        print(f"    Website found : {'yes' if item['website_found'] else 'no'}")
        print(f"    Best rank     : {'#' + str(item['best_rank']) if item['best_rank'] else '—'}")
        print(f"    AI Overview   : {'yes' if item['ai_overview'] else 'no'}")

        if item["matched_page_url"]:
            print(f"    Matched page  : {unquote(short_path_from_url(item['matched_page_url']))}")

        print()
        print("    Top results")
        for result in item["top_results"]:
            marker = " *site match*" if result["page_id"] else ""
            title = result["title"] or result["url"]
            print(f"        #{result['position']:<2} {result['domain']}{marker}")
            print(f"            {title}")

        print()

    print()


def render_html(connection: sqlite3.Connection, output_dir, nav_items, site_url: str, result_limit: int = 5, **kwargs):
    model = build_model(connection, site_url=site_url, result_limit=result_limit)

    body = []

    if not model:
        body.append("<p>No observed queries found.</p>")
    else:
        for item in model:
            status_class = "good" if item["website_found"] else "bad"
            best_rank = f"#{item['best_rank']}" if item["best_rank"] else "—"

            body.append('<section class="card">')
            body.append(f"<h2>{html_escape(item['query_text'])}</h2>")
            body.append('<div class="grid">')
            body.append(f'<div class="metric"><div class="label">Website Found</div><div class="value {status_class}">{html_escape("yes" if item["website_found"] else "no")}</div></div>')
            body.append(f'<div class="metric"><div class="label">Best Rank</div><div class="value">{html_escape(best_rank)}</div></div>')
            body.append(f'<div class="metric"><div class="label">Runs</div><div class="value">{html_escape(item["run_count"])}</div></div>')
            body.append(f'<div class="metric"><div class="label">AI Overview</div><div class="value">{html_escape("yes" if item["ai_overview"] else "no")}</div></div>')
            body.append("</div>")

            body.append(f'<p class="muted">Last checked: {html_escape(item["last_checked_at"])} · Query status: {html_escape(item["status"])} · Latest run: {html_escape(item["latest_run_id"])}</p>')

            if item["matched_page_url"]:
                path = short_path_from_url(item["matched_page_url"])
                body.append(f'<p><strong>Matched page:</strong> <a href="{html_escape(item["matched_page_url"])}">{html_escape(path)}</a></p>')

            body.append('<div class="result-list">')
            for result in item["top_results"]:
                marker = ' <span class="badge good">site match</span>' if result["page_id"] else ""
                title = result["title"] or result["url"]
                body.append('<div class="result-row">')
                body.append(f'<div>#{html_escape(result["position"])}</div>')
                body.append(f'<div><strong>{html_escape(result["domain"])}</strong>{marker}</div>')
                body.append(f'<div class="result-title"><a href="{html_escape(result["url"])}">{html_escape(title)}</a></div>')
                body.append("</div>")
            body.append("</div>")
            body.append("</section>")

    return write_html_page(output_dir, HTML_FILE, "Search Performance", "\n".join(body), nav_items)
