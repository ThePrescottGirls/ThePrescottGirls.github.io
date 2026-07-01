#!/usr/bin/env python3

import sys
from pathlib import Path

from models import OracleDatabase
from sitemap import read_sitemap_urls


DEFAULT_PROPERTY = "https://www.theprescottgirls.com"
DEFAULT_SITEMAP = "../../sitemap.xml"


def main():
    property_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROPERTY
    sitemap_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(DEFAULT_SITEMAP)

    print("Oracle")
    print("======")
    print()
    print(f"Property: {property_url}")
    print(f"Sitemap:  {sitemap_file}")

    db = OracleDatabase("database/oracle.db")
    db.initialize()

    site_id = db.get_or_create_site(property_url)
    run_id = db.start_run(site_id)

    urls = read_sitemap_urls(sitemap_file)

    new_pages = 0

    for url in urls:
        _, created = db.register_page(site_id, url)

        if created:
            new_pages += 1

    db.finish_run(run_id)

    run = db.get_run(run_id)

    print()
    print(f"URLs found : {len(urls)}")
    print(f"New pages  : {new_pages}")
    print(f"Total pages: {db.page_count(site_id)}")
    print()
    print(f"Database: database/oracle.db")
    print(f"Site ID:  {site_id}")
    print(f"Run ID:   {run_id}")
    print(f"Status:   {run['status']}")
    print()
    print("Oracle database is ready.")


if __name__ == "__main__":
    main()
