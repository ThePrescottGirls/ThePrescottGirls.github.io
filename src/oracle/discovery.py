#!/usr/bin/env python3

"""
Discovery

Reads the configured website sitemap and populates Oracle's database with
pages discovered on the website.
"""

from common import database_path, website
from config import load_config
from database import Database
from sitemap import read_sitemap_urls


def sitemap_url(website: str) -> str:
    """Return the default sitemap URL for a website."""
    return f"{website.rstrip('/')}/sitemap.xml"


def main():
    config = load_config()

    site = website(config)
    sitemap = sitemap_url(site)

    print("Discovery")
    print("=========")
    print()
    print(f"Site     : {site}")
    print(f"Sitemap  : {sitemap}")
    print()

    db_path = database_path(config)

    db = Database(db_path)
    db.initialize()

    site_id = db.get_or_create_site(site)
    run_id = db.start_run(site_id, run_type="discovery")

    urls = read_sitemap_urls(sitemap)

    new_pages = 0
    for url in urls:
        _, created = db.register_page(site_id, url)
        if created:
            new_pages += 1

    db.finish_run(run_id)
    run = db.get_run(run_id)

    print("Summary")
    print("-------")
    print()
    print(f"URLs discovered : {len(urls)}")
    print(f"New pages       : {new_pages}")
    print(f"Total pages     : {db.page_count(site_id)}")
    print()
    print(f"Database : {db_path}")
    print(f"Site ID  : {site_id}")
    print(f"Run ID   : {run_id}")
    print(f"Status   : {run['status']}")
    print()
    print("Discovery complete.")


if __name__ == "__main__":
    main()
