from __future__ import annotations

import xml.etree.ElementTree as ET
from urllib.request import urlopen


def sitemap_url_for_site(site_url: str) -> str:
    """Return the default sitemap URL for a website."""
    return f"{site_url.rstrip('/')}/sitemap.xml"


def read_sitemap_urls_for_site(site_url: str) -> list[str]:
    """Read URLs from the website's sitemap."""
    return read_sitemap_urls(sitemap_url_for_site(site_url))


def read_sitemap_urls(sitemap_source: str) -> list[str]:
    """
    Read URLs from a sitemap.

    sitemap_source may be either:
        - a local file path
        - an http/https URL
    """
    sitemap_source = str(sitemap_source)

    if sitemap_source.startswith(("http://", "https://")):
        with urlopen(sitemap_source) as response:
            tree = ET.parse(response)
    else:
        tree = ET.parse(sitemap_source)

    root = tree.getroot()

    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    return [
        loc.text.strip()
        for loc in root.findall(".//sm:loc", namespace)
        if loc.text
    ]
