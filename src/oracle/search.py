#!/usr/bin/env python3
"""
search.py

Collects search result observations for Oracle's active queries.

Search does not analyze, score, graph, or interpret results. It only:
    - reads active queries from the configured site's database
    - asks a search provider for results
    - stores the returned result rows in query_results

Dashboard is responsible for interpreting the stored observations.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urldefrag
from urllib.request import Request, urlopen
from urllib.parse import urlencode

from config import load_config
from database import Database, database_path_for_site


DEFAULT_RESULTS_PER_QUERY = 10
DEFAULT_DELAY_SECONDS = 1.0


@dataclass(frozen=True)
class SearchResult:
    position: int
    title: str
    url: str
    snippet: str
    raw_json: dict[str, Any]


def canonical_result_url(url: str) -> str:
    """Return a stable URL form for matching against discovered pages."""
    clean_url, _fragment = urldefrag(url)
    return clean_url.rstrip("/")


def load_page_lookup(db: Database, site_id: int) -> dict[str, int]:
    """Map discovered page URLs to page ids for optional result linking."""
    rows = db.fetchall(
        """
        SELECT id, url
          FROM pages
         WHERE site_id = ?
        """,
        (site_id,),
    )

    return {
        canonical_result_url(row["url"]): row["id"]
        for row in rows
    }


def fetch_google_custom_search_results(
    query: str,
    results_per_query: int,
) -> list[SearchResult]:
    """
    Fetch search results using Google's Custom Search JSON API.

    Required environment variables:
        GOOGLE_SEARCH_API_KEY
        GOOGLE_SEARCH_ENGINE_ID

    The search engine should be configured to search the public web.
    """
    api_key = os.environ.get("GOOGLE_SEARCH_API_KEY", "").strip()
    search_engine_id = os.environ.get("GOOGLE_SEARCH_ENGINE_ID", "").strip()

    if not api_key:
        raise RuntimeError("Missing environment variable: GOOGLE_SEARCH_API_KEY")

    if not search_engine_id:
        raise RuntimeError("Missing environment variable: GOOGLE_SEARCH_ENGINE_ID")

    parameters = {
        "key": api_key,
        "cx": search_engine_id,
        "q": query,
        "num": max(1, min(results_per_query, 10)),
    }

    url = "https://www.googleapis.com/customsearch/v1?" + urlencode(parameters)

    request = Request(
        url,
        headers={
            "User-Agent": "Oracle Search Collector/1.0",
        },
    )

    with urlopen(request) as response:
        payload = json.loads(response.read().decode("utf-8"))

    results: list[SearchResult] = []

    for index, item in enumerate(payload.get("items", []), start=1):
        results.append(
            SearchResult(
                position=index,
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
                raw_json=item,
            )
        )

    return results


def active_queries(db: Database, site_id: int, limit: int | None = None) -> list[Any]:
    sql = """
        SELECT id, query_text
          FROM queries
         WHERE site_id = ?
           AND is_active = 1
         ORDER BY id
    """
    parameters: tuple[Any, ...] = (site_id,)

    if limit is not None:
        sql += " LIMIT ?"
        parameters = (site_id, limit)

    return db.fetchall(sql, parameters)


def collect_search_results(
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
    query_limit: int | None = None,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    dry_run: bool = False,
) -> None:
    config = load_config()
    db_path = database_path_for_site(config.website)

    print("Search")
    print("======")
    print()
    print(f"Website : {config.website}")
    print(f"Database: {db_path}")
    print(f"Provider: Google Custom Search JSON API")
    print()

    db = Database(db_path)
    db.initialize()

    site_id = db.get_or_create_site(config.website)
    queries = active_queries(db, site_id, query_limit)

    if not queries:
        print("No active queries found. Run seedQueries first.")
        return

    page_lookup = load_page_lookup(db, site_id)

    run_id = db.start_run(site_id, run_type="search")

    stored_results = 0
    failed_queries = 0

    try:
        for query_index, query_row in enumerate(queries, start=1):
            query_id = query_row["id"]
            query_text = query_row["query_text"]

            print(f"[{query_index:2}/{len(queries)}] {query_text}")

            try:
                results = fetch_google_custom_search_results(
                    query_text,
                    results_per_query,
                )
            except Exception as error:
                failed_queries += 1
                print(f"    ERROR: {error}")
                continue

            if not results:
                print("    No results")
            else:
                for result in results:
                    result_key = canonical_result_url(result.url)
                    page_id = page_lookup.get(result_key)

                    if not dry_run:
                        db.register_query_result(
                            run_id=run_id,
                            query_id=query_id,
                            page_id=page_id,
                            position=result.position,
                            result_url=result.url,
                            title=result.title,
                            snippet=result.snippet,
                            raw_json=result.raw_json,
                        )

                    stored_results += 1

                    match_note = " *site match*" if page_id else ""
                    print(f"    {result.position:2}. {result.title}{match_note}")
                    print(f"        {result.url}")

            if query_index < len(queries) and delay_seconds > 0:
                time.sleep(delay_seconds)

        status = "complete" if failed_queries == 0 else "partial"
        message = None if failed_queries == 0 else f"{failed_queries} queries failed"

        if dry_run:
            status = "dry_run"
            message = "Dry run; no query_results stored"

        db.finish_run(run_id, status=status, message=message)

    except Exception as error:
        db.finish_run(run_id, status="failed", message=str(error))
        raise

    print()
    print("Summary")
    print("-------")
    print()
    print(f"Queries checked   : {len(queries)}")
    print(f"Failed queries    : {failed_queries}")
    print(f"Results collected : {stored_results}")
    print(f"Dry run           : {'yes' if dry_run else 'no'}")
    print(f"Run ID            : {run_id}")
    print()
    print("Search complete.")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect search results for Oracle's active queries."
    )
    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_RESULTS_PER_QUERY,
        help=f"Number of results per query, up to 10. Default: {DEFAULT_RESULTS_PER_QUERY}",
    )
    parser.add_argument(
        "--query-limit",
        type=int,
        default=None,
        help="Maximum number of active queries to check. Default: all active queries.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help=f"Seconds to wait between queries. Default: {DEFAULT_DELAY_SECONDS}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and display results without storing them.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    collect_search_results(
        results_per_query=args.top,
        query_limit=args.query_limit,
        delay_seconds=args.delay,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
