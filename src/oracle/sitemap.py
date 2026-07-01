from pathlib import Path
import xml.etree.ElementTree as ET


def read_sitemap_urls(sitemap_file: Path) -> list[str]:
    tree = ET.parse(sitemap_file)
    root = tree.getroot()

    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    return [
        loc.text.strip()
        for loc in root.findall(".//sm:loc", namespace)
        if loc.text
    ]
