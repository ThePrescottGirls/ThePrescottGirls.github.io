#!/usr/bin/env python3

"""
Discovery

Reads a website sitemap and populates Oracle's database with
pages discovered on the website.

Discovery does not contact search engines or AI systems.
Its purpose is simply to learn the structure of the website.
"""

import sys
from pathlib import Path

from database import Database
from sitemap import read_sitemap_urls


DEFAULT_SITE = "https://www.theprescottgirls.com"
DEFAULT_SITEMAP = "../../sitemap.xml"


def main():

    site_url = (
        sys.argv[1]
        if len(sys.argv) > 1
        else DEFAULT_SITE
    )

    sitemap_file = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else Path(DEFAULT_SITEMAP)
    )

    print("Discovery")
    print("=========")
    print()
    print(f"Site     : {site_url}")
    print(f"Sitemap  : {sitemap_file}")
    print()

    # ------------------------------------------------------------
    # Open Oracle database
    # ------------------------------------------------------------

    db = Database("database/oracle.db")
    db.initialize()

    site_id = db.get_or_create_site(site_url)
    run_id = db.start_run(site_id, run_type="discovery")

    # ------------------------------------------------------------
    # Read sitemap
    # ------------------------------------------------------------

    urls = read_sitemap_urls(sitemap_file)

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
    print(f"Database : database/oracle.db")
    print(f"Site ID  : {site_id}")
    print(f"Run ID   : {run_id}")
    print(f"Status   : {run['status']}")
    print()
    print("Discovery complete.")


if __name__ == "__main__":
    main()
