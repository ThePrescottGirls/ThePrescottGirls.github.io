#!/usr/bin/env python3
"""
dashboard.py

Oracle dashboard.

Reads Oracle's SQLite database and presents views. Dashboard is read-only:
it should not discover pages, run searches, call Google APIs, or modify
the database.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from common import database_path, website
from config import load_config

from views import pages
from views import queries
from views import results
from views import runs
from views import sites
from views import summary


DEFAULT_RUN_LIMIT = 10
DEFAULT_RESULT_LIMIT = 5
DEFAULT_OUTPUT_DIR = "dashboard_html"

VIEWS = {
    "summary": summary,
    "sites": sites,
    "runs": runs,
    "pages": pages,
    "queries": queries,
    "results": results,
}

HTML_ORDER = ["summary", "results", "queries", "runs", "pages", "sites"]


def connect_database(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)

    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}")

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show or render the Oracle dashboard."
    )
    parser.add_argument(
        "-view",
        choices=["all", *VIEWS.keys()],
        default=None,
        help=(
            "Display a diagnostic text view. If omitted, dashboard renders HTML files."
        ),
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
        "--result-limit",
        type=int,
        default=DEFAULT_RESULT_LIMIT,
        help=f"Number of top search results to show per query. Default: {DEFAULT_RESULT_LIMIT}",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for generated HTML files. Default: {DEFAULT_OUTPUT_DIR}",
    )
    return parser.parse_args()


def nav_items() -> list[tuple[str, str]]:
    return [
        ("Summary", "index.html"),
        ("Results", "results.html"),
        ("Queries", "queries.html"),
        ("Runs", "runs.html"),
        ("Pages", "pages.html"),
        ("Sites", "sites.html"),
    ]


def common_kwargs(args: argparse.Namespace, website: str) -> dict:
    return {
        "run_limit": args.run_limit,
        "page_limit": args.page_limit,
        "result_limit": args.result_limit,
        "site_url": website,
    }


def show_text_view(connection: sqlite3.Connection, view: str, kwargs: dict) -> None:
    if view == "all":
        for view_name in HTML_ORDER:
            VIEWS[view_name].show_text(connection, **kwargs)
        return

    VIEWS[view].show_text(connection, **kwargs)


def render_html(
    connection: sqlite3.Connection,
    output_dir: str,
    kwargs: dict,
) -> list[Path]:
    written: list[Path] = []
    nav = nav_items()

    for view_name in HTML_ORDER:
        written.append(
            VIEWS[view_name].render_html(
                connection,
                output_dir=output_dir,
                nav_items=nav,
                **kwargs,
            )
        )

    return written


def main() -> None:
    args = parse_arguments()

    config = load_config()

    site = website(config)
    db_path = database_path(config)

    print()
    print(f"Website : {site}")
    print(f"Database: {db_path}")
    print()

    kwargs = common_kwargs(args, site)

    with connect_database(db_path) as connection:
        if args.view:
            show_text_view(connection, args.view, kwargs)
        else:
            written = render_html(connection, args.output_dir, kwargs)
            print("HTML dashboard generated:")
            for path in written:
                print(f"    {path}")

    print()
    print("Dashboard complete.")


if __name__ == "__main__":
    main()
