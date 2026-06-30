import csv
from pathlib import Path


def write_inspection_csv(results, output_file: Path):
    fieldnames = [
        "url",
        "verdict",
        "coverage",
        "last_crawl",
        "user_canonical",
        "google_canonical",
        "robots",
        "fetch",
        "indexing",
        "crawled_as",
    ]

    with output_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for result in results:
            writer.writerow({
                "url": result.url,
                "verdict": result.verdict,
                "coverage": result.coverage,
                "last_crawl": result.last_crawl,
                "user_canonical": result.user_canonical,
                "google_canonical": result.google_canonical,
                "robots": result.robots,
                "fetch": result.fetch,
                "indexing": result.indexing,
                "crawled_as": result.crawled_as,
            })
