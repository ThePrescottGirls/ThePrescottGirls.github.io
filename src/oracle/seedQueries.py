#!/usr/bin/env python3
"""
seedQueries.py

Seeds Oracle's query table from discovered website pages.

This tool does not search Google or any other search engine.
It only derives candidate search queries from page URLs already stored
in the configured Oracle database.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from urllib.parse import unquote, urlparse

from common import database_path, website
from config import load_config
from database import Database


DEFAULT_IGNORED_PREFIXES = (
    "Study Guide - ",
    "Press Release - ",
)


def clean_query_from_url(url: str) -> str:
    """Derive a readable query candidate from a page URL."""
    parsed = urlparse(url)
    path = parsed.path.strip("/")

    if not path:
        return domain_name_from_url(url)

    filename = path.split("/")[-1]
    filename = unquote(filename)

    if "." in filename:
        filename = filename.rsplit(".", 1)[0]

    query = filename.replace("_", " ").replace("-", " ")
    query = re.sub(r"\s+", " ", query).strip()

    for prefix in DEFAULT_IGNORED_PREFIXES:
        if query.startswith(prefix):
            query = query[len(prefix):].strip()

    return query


def domain_name_from_url(url: str) -> str:
    """Return a readable fallback query from a site's domain."""
    host = urlparse(url).netloc.lower().strip()

    if host.startswith("www."):
        host = host[4:]

    if "." in host:
        host = host.rsplit(".", 1)[0]

    return host.replace("-", " ").replace("_", " ").strip()


def should_seed_query(query: str) -> bool:
    """Return True if the derived query is worth adding."""
    if not query:
        return False

    lowered = query.lower()

    ignored_exact = {
        "index",
        "home",
        "contact",
        "faq",
    }

    if lowered in ignored_exact:
        return False

    if len(query) < 3:
        return False

    return True


def fetch_pages(db: Database, site_id: int) -> list[sqlite3.Row]:
    return db.fetchall(
        """
        SELECT id, url
          FROM pages
         WHERE site_id = ?
         ORDER BY url
        """,
        (site_id,),
    )


def seed_queries(dry_run: bool = False) -> None:
    config = load_config()

    site = website(config)
    db_path = database_path(config)

    print("Seed Queries")
    print("============")
    print()
    print(f"Website : {site}")
    print(f"Database: {db_path}")
    print()

    db = Database(db_path)
    db.initialize()

    site_id = db.get_or_create_site(site)
    pages = fetch_pages(db, site_id)

    if not pages:
        print("No pages found. Run Discovery first.")
        return

    candidates: list[tuple[str, str]] = []

    for page in pages:
        query = clean_query_from_url(page["url"])

        if should_seed_query(query):
            candidates.append((page["url"], query))

    added = 0
    existing = 0
    skipped = len(pages) - len(candidates)

    print("Candidates")
    print("----------")
    print()

    for _, query in candidates:
        row = db.fetchone(
            """
            SELECT id
              FROM queries
             WHERE site_id = ?
               AND query_text = ?
            """,
            (site_id, query),
        )

        if row:
            existing += 1
            status = "existing"
        else:
            status = "new"
            if not dry_run:
                db.get_or_create_query(site_id, query)
            added += 1

        print(f"{status:8} {query}")

    print()
    print("Summary")
    print("-------")
    print()
    print(f"Pages scanned     : {len(pages)}")
    print(f"Candidates found  : {len(candidates)}")
    print(f"Skipped pages     : {skipped}")
    print(f"Existing queries  : {existing}")
    print(f"New queries       : {added}")
    print(f"Dry run           : {'yes' if dry_run else 'no'}")
    print()
    print("Seed Queries complete.")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed Oracle query candidates from discovered pages."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show candidate queries without writing them to the database.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    seed_queries(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
