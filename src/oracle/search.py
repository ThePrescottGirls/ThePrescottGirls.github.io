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
from datetime import UTC, datetime
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urldefrag
from urllib.request import Request, urlopen

from config import load_config
from database import Database, database_path_for_site


DEFAULT_RESULTS_PER_QUERY = 10
DEFAULT_DELAY_SECONDS = 1.0
DEFAULT_SERPAPI_LOCATION = "United States"
DEFAULT_SERPAPI_HL = "en"
DEFAULT_SERPAPI_GL = "us"
DEFAULT_SERPAPI_GOOGLE_DOMAIN = "google.com"
DEFAULT_SERPAPI_DEVICE = "desktop"


@dataclass(frozen=True)
class SearchSettings:
    provider: str
    serpapi_api_key: str
    serpapi_location: str
    serpapi_hl: str
    serpapi_gl: str
    serpapi_google_domain: str
    serpapi_device: str


@dataclass(frozen=True)
class SearchResult:
    position: int
    title: str
    url: str
    snippet: str
    raw_json: dict[str, Any]
    displayed_link: str | None = None
    redirect_link: str | None = None
    source: str | None = None
    result_type: str = "organic"
    favicon: str | None = None
    result_date: str | None = None
    about_this_result: dict[str, Any] | None = None


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


def load_search_settings(config_file: str | Path = "config.ini") -> SearchSettings:
    """Load search-provider settings that are not yet part of config.py."""
    parser = ConfigParser()
    parser.read(config_file)

    provider = parser.get("search", "provider", fallback="google").strip().lower()

    return SearchSettings(
        provider=provider,
        serpapi_api_key=(
            parser.get("search", "SERPAPI_API_KEY", fallback="").strip()
            or parser.get("search", "SERPAPI_KEY", fallback="").strip()
            or os.environ.get("SERPAPI_KEY", "").strip()
        ),
        serpapi_location=parser.get(
            "search", "serpapi_location", fallback=DEFAULT_SERPAPI_LOCATION
        ).strip(),
        serpapi_hl=parser.get(
            "search", "serpapi_hl", fallback=DEFAULT_SERPAPI_HL
        ).strip(),
        serpapi_gl=parser.get(
            "search", "serpapi_gl", fallback=DEFAULT_SERPAPI_GL
        ).strip(),
        serpapi_google_domain=parser.get(
            "search", "serpapi_google_domain", fallback=DEFAULT_SERPAPI_GOOGLE_DOMAIN
        ).strip(),
        serpapi_device=parser.get(
            "search", "serpapi_device", fallback=DEFAULT_SERPAPI_DEVICE
        ).strip(),
    )


def decode_http_error(error: HTTPError) -> str:
    """Return the most useful message available from an HTTPError body."""
    error_body = error.read().decode("utf-8", errors="replace")

    try:
        error_payload = json.loads(error_body)
        return json.dumps(error_payload, indent=2)
    except json.JSONDecodeError:
        return error_body.strip() or str(error)


def fetch_google_custom_search_results(
    query: str,
    results_per_query: int,
    api_key: str,
    search_engine_id: str,
) -> tuple[dict[str, Any], list[SearchResult]]:
    """
    Fetch search results using Google's legacy Custom Search JSON API.

    This is retained as a legacy provider. New Oracle searches should normally
    use SerpApi, because Google has closed Custom Search JSON API access to
    new signups.
    """
    if not api_key:
        raise RuntimeError("Missing config value: [search] GOOGLE_SEARCH_API_KEY")

    if not search_engine_id:
        raise RuntimeError("Missing config value: [search] GOOGLE_SEARCH_ENGINE_ID")

    parameters = {
        "key": api_key,
        "cx": search_engine_id,
        "q": query,
        "num": max(1, min(results_per_query, 10)),
    }

    url = "https://www.googleapis.com/customsearch/v1?" + urlencode(parameters)

    safe_url = (
        url
        .replace(api_key, "***API_KEY***")
        .replace(search_engine_id, "***CX***")
    )
    print(f"    GET {safe_url}")

    request = Request(
        url,
        headers={
            "User-Agent": "Oracle Search Collector/1.0",
        },
    )

    try:
        with urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(
            f"Google Custom Search API error {error.code}: {decode_http_error(error)}"
        ) from error
    except URLError as error:
        raise RuntimeError(f"Network error calling Google Custom Search API: {error}") from error

    results: list[SearchResult] = []

    for index, item in enumerate(payload.get("items", []), start=1):
        results.append(
            SearchResult(
                position=index,
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
                displayed_link=item.get("displayLink"),
                raw_json=item,
                result_type="organic",
            )
        )

    return payload, results


def fetch_serpapi_google_results(
    query: str,
    results_per_query: int,
    settings: SearchSettings,
) -> tuple[dict[str, Any], list[SearchResult]]:
    """Fetch Google search results through SerpApi."""
    if not settings.serpapi_api_key:
        raise RuntimeError(
            "Missing config value: [search] SERPAPI_API_KEY or environment variable SERPAPI_KEY"
        )

    parameters = {
        "engine": "google",
        "q": query,
        "api_key": settings.serpapi_api_key,
        "location": settings.serpapi_location,
        "hl": settings.serpapi_hl,
        "gl": settings.serpapi_gl,
        "google_domain": settings.serpapi_google_domain,
        "device": settings.serpapi_device,
        "num": max(1, min(results_per_query, 10)),
    }

    url = "https://serpapi.com/search.json?" + urlencode(parameters)

    safe_url = url.replace(settings.serpapi_api_key, "***SERPAPI_KEY***")
    print(f"    GET {safe_url}")

    request = Request(
        url,
        headers={
            "User-Agent": "Oracle Search Collector/1.0",
        },
    )

    try:
        with urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(
            f"SerpApi error {error.code}: {decode_http_error(error)}"
        ) from error
    except URLError as error:
        raise RuntimeError(f"Network error calling SerpApi: {error}") from error

    if payload.get("error"):
        raise RuntimeError(f"SerpApi error: {payload.get('error')}")

    results: list[SearchResult] = []

    for item in payload.get("organic_results", []):
        position = item.get("position")
        if position is None:
            position = len(results) + 1

        results.append(
            SearchResult(
                position=int(position),
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
                displayed_link=item.get("displayed_link"),
                redirect_link=item.get("redirect_link"),
                source=item.get("source"),
                result_type="organic",
                favicon=item.get("favicon"),
                result_date=item.get("date"),
                about_this_result=item.get("about_this_result"),
                raw_json=item,
            )
        )

    return payload, results


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


def utc_timestamp() -> str:
    """Return a compact UTC timestamp matching Oracle's database convention."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def query_history(db: Database, query_id: int) -> dict[str, Any]:
    """Return prior observation history for a query."""
    row = db.fetchone(
        """
        SELECT
            COUNT(query_results.id) AS result_count,
            COUNT(DISTINCT query_results.run_id) AS run_count,
            MAX(query_results.checked_at) AS last_checked_at
          FROM query_results
         WHERE query_results.query_id = ?
        """,
        (query_id,),
    )

    return {
        "result_count": row["result_count"] if row else 0,
        "run_count": row["run_count"] if row else 0,
        "last_checked_at": row["last_checked_at"] if row else None,
    }


def get_query_by_text(db: Database, site_id: int, query_text: str) -> Any | None:
    """Return an existing query row without changing its active state."""
    return db.fetchone(
        """
        SELECT id, query_text, is_active, created_at, updated_at
          FROM queries
         WHERE site_id = ?
           AND query_text = ?
        """,
        (site_id, query_text),
    )


def create_ad_hoc_query(db: Database, site_id: int, query_text: str) -> int:
    """Create an inactive ad-hoc query and return its id."""
    now = utc_timestamp()
    cursor = db.execute(
        """
        INSERT INTO queries (
            site_id,
            query_text,
            created_at,
            updated_at,
            is_active
        )
        VALUES (?, ?, ?, ?, 0)
        """,
        (site_id, query_text, now, now),
    )
    return cursor.lastrowid


def update_query_seen_time(db: Database, query_id: int) -> None:
    """Touch an existing query without changing whether it is active."""
    db.execute(
        """
        UPDATE queries
           SET updated_at = ?
         WHERE id = ?
        """,
        (utc_timestamp(), query_id),
    )


def confirm_existing_query_run(
    query_text: str,
    history: dict[str, Any],
    assume_yes: bool,
) -> bool:
    """Ask before spending a search call on a query that already has observations."""
    if assume_yes or history["result_count"] == 0:
        return True

    print()
    print("Query already exists:")
    print(f"    {query_text}")
    print()
    print("Previous observations:")
    print(f"    Last run : {history['last_checked_at'] or 'unknown'}")
    print(f"    Runs     : {history['run_count']}")
    print(f"    Results  : {history['result_count']}")
    print()

    try:
        answer = input("Run this search again? [y/N] ").strip().lower()
    except EOFError:
        answer = ""

    return answer in {"y", "yes"}


def resolve_query_override(
    db: Database,
    site_id: int,
    query_text: str,
    assume_yes: bool,
    dry_run: bool,
) -> list[dict[str, Any]]:
    """Resolve a command-line query override into the single query to run."""
    query_text = " ".join(query_text.split()).strip()

    if not query_text:
        raise RuntimeError("The -query value cannot be empty.")

    row = get_query_by_text(db, site_id, query_text)

    if row:
        history = query_history(db, row["id"])
        status = "active" if row["is_active"] else "inactive"

        print("Using existing query:")
        print(f"    {query_text}")
        print(f"    Status   : {status}")
        print(f"    Last run : {history['last_checked_at'] or 'never'}")
        print(f"    Runs     : {history['run_count']}")
        print(f"    Results  : {history['result_count']}")

        if not confirm_existing_query_run(query_text, history, assume_yes):
            print()
            print("Search cancelled.")
            return []

        if not dry_run:
            update_query_seen_time(db, row["id"])

        return [{"id": row["id"], "query_text": query_text}]

    print("Query not found.")
    print("Added inactive ad-hoc query:")
    print(f"    {query_text}")

    if dry_run:
        print("Dry run: query was not added to the database.")
        return [{"id": -1, "query_text": query_text}]

    query_id = create_ad_hoc_query(db, site_id, query_text)
    return [{"id": query_id, "query_text": query_text}]


def register_search_response_if_supported(
    db: Database,
    run_id: int,
    query_id: int,
    provider: str,
    payload: dict[str, Any],
) -> int | None:
    """Store the complete provider response when the database supports it."""
    if not hasattr(db, "register_search_response"):
        return None

    search_metadata = payload.get("search_metadata", {})
    search_parameters = payload.get("search_parameters", {})
    search_information = payload.get("search_information", {})

    return db.register_search_response(
        run_id=run_id,
        query_id=query_id,
        provider=provider,
        engine=search_parameters.get("engine"),
        query_text=search_parameters.get("q"),
        location_requested=search_parameters.get("location_requested"),
        location_used=search_parameters.get("location_used"),
        google_domain=search_parameters.get("google_domain"),
        hl=search_parameters.get("hl"),
        gl=search_parameters.get("gl"),
        device=search_parameters.get("device"),
        total_results=search_information.get("total_results"),
        time_taken_displayed=search_information.get("time_taken_displayed"),
        organic_results_state=search_information.get("organic_results_state"),
        search_metadata=search_metadata,
        search_parameters=search_parameters,
        search_information=search_information,
        raw_json=payload,
    )


def register_serp_features_if_supported(
    db: Database,
    run_id: int,
    query_id: int,
    search_response_id: int | None,
    payload: dict[str, Any],
) -> None:
    """Store non-organic SERP features when the database supports them."""
    if not hasattr(db, "register_serp_feature"):
        return

    feature_keys = [
        "knowledge_graph",
        "ai_overview",
        "related_questions",
        "related_searches",
        "pagination",
        "serpapi_pagination",
        "inline_images",
        "top_stories",
        "local_results",
        "shopping_results",
    ]

    for feature_type in feature_keys:
        feature_value = payload.get(feature_type)
        if feature_value:
            db.register_serp_feature(
                run_id=run_id,
                query_id=query_id,
                search_response_id=search_response_id,
                feature_type=feature_type,
                raw_json=feature_value,
            )


def collect_search_results(
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
    query_limit: int | None = None,
    query_override: str | None = None,
    assume_yes: bool = False,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    dry_run: bool = False,
) -> None:
    config = load_config()
    settings = load_search_settings()
    db_path = database_path_for_site(config.website)

    provider_label = (
        "SerpApi Google Search API"
        if settings.provider == "serpapi"
        else "Google Custom Search JSON API"
    )

    print("Search")
    print("======")
    print()
    print(f"Website : {config.website}")
    print(f"Database: {db_path}")
    print(f"Provider: {provider_label}")
    if settings.provider == "serpapi":
        print(
            "Market  : "
            f"{settings.serpapi_location}, hl={settings.serpapi_hl}, "
            f"gl={settings.serpapi_gl}, device={settings.serpapi_device}"
        )
    if query_override:
        print("Mode    : Single command-line query override")
        print(f"Query   : {query_override}")
    print()

    db = Database(db_path)
    db.initialize()

    site_id = db.get_or_create_site(config.website)

    if query_override:
        queries = resolve_query_override(
            db=db,
            site_id=site_id,
            query_text=query_override,
            assume_yes=assume_yes,
            dry_run=dry_run,
        )
    else:
        queries = active_queries(db, site_id, query_limit)

    if not queries:
        if query_override:
            return
        print("No active queries found. Run seedQueries first, or use -query.")
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
                if settings.provider == "serpapi":
                    payload, results = fetch_serpapi_google_results(
                        query_text,
                        results_per_query,
                        settings,
                    )
                elif settings.provider == "google":
                    payload, results = fetch_google_custom_search_results(
                        query_text,
                        results_per_query,
                        config.search_google_api_key,
                        config.search_google_engine_id,
                    )
                else:
                    raise RuntimeError(
                        f"Unsupported search provider: {settings.provider}. "
                        "Use 'serpapi' or 'google'."
                    )
            except Exception as error:
                failed_queries += 1
                print(f"    ERROR: {error}")
                continue

            search_response_id = None
            if not dry_run:
                search_response_id = register_search_response_if_supported(
                    db=db,
                    run_id=run_id,
                    query_id=query_id,
                    provider=settings.provider,
                    payload=payload,
                )
                register_serp_features_if_supported(
                    db=db,
                    run_id=run_id,
                    query_id=query_id,
                    search_response_id=search_response_id,
                    payload=payload,
                )

            if not results:
                print("    No organic results")
            else:
                for result in results:
                    result_key = canonical_result_url(result.url)
                    page_id = page_lookup.get(result_key)

                    if not dry_run:
                        db.register_query_result(
                            run_id=run_id,
                            query_id=query_id,
                            search_response_id=search_response_id,
                            page_id=page_id,
                            position=result.position,
                            result_url=result.url,
                            displayed_link=result.displayed_link,
                            redirect_link=result.redirect_link,
                            title=result.title,
                            snippet=result.snippet,
                            source=result.source,
                            result_type=result.result_type,
                            favicon=result.favicon,
                            result_date=result.result_date,
                            about_this_result=result.about_this_result,
                            raw_json=result.raw_json,
                        )

                    stored_results += 1

                    match_note = " *site match*" if page_id else ""
                    source_note = f" [{result.source}]" if result.source else ""
                    print(f"    {result.position:2}. {result.title}{match_note}{source_note}")
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
        "limit",
        nargs="?",
        type=int,
        help="Optional positional limit on the number of active queries to execute (testing shortcut).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_RESULTS_PER_QUERY,
        help=f"Number of organic results per query, up to 10. Default: {DEFAULT_RESULTS_PER_QUERY}",
    )
    parser.add_argument(
        "--query-limit",
        type=int,
        default=None,
        help="Maximum number of active queries to check. Default: all active queries.",
    )
    parser.add_argument(
        "-query",
        "--query",
        nargs="+",
        default=None,
        metavar="TEXT",
        help=(
            "Run exactly one ad-hoc query instead of active queries. "
            "Supports quoted text or unquoted words."
        ),
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Do not ask before rerunning an existing query with prior observations.",
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

    query_override = " ".join(args.query).strip() if args.query else None

    collect_search_results(
        results_per_query=args.top,
        query_limit=args.query_limit if args.query_limit is not None else args.limit,
        query_override=query_override,
        assume_yes=args.yes,
        delay_seconds=args.delay,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
