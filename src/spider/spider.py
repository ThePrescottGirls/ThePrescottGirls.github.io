from pathlib import Path

from googleapiclient.errors import HttpError

from sitemap import read_sitemap_urls
from inspector import inspect_urls
from report import write_inspection_csv
from archive import archive
from summary import print_summary

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parents[1]

CREDENTIALS_DIR = BASE_DIR / "credentials"
REPORTS_DIR = BASE_DIR / "reports"
CSV_REPORT = REPORTS_DIR / "inspection.csv"
HISTORY_DB = REPORTS_DIR / "inspection_history.db"
SITEMAP_FILE = ROOT_DIR / "sitemap.xml"

CREDENTIALS_FILE = CREDENTIALS_DIR / "google-search-console-credentials.json"

PROPERTY_URL = "sc-domain:theprescottgirls.com"
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def main():
    CREDENTIALS_DIR.mkdir(exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)

    urls = read_sitemap_urls(SITEMAP_FILE)

    print("SPIDER")
    print("======")
    print()
    print(f"Sitemap: {SITEMAP_FILE}")
    print(f"Found {len(urls)} URLs")
    print()

    if not CREDENTIALS_FILE.exists():
        print("Search Console credentials not found.")
        print()
        print("Expected location:")
        print(f"  {CREDENTIALS_FILE}")
        return

    try:
        results = inspect_urls(
            urls=urls,
            credentials_file=CREDENTIALS_FILE,
            property_url=PROPERTY_URL,
            scopes=SCOPES,
        )

        write_inspection_csv(results, CSV_REPORT)
        archive_summary = archive(CSV_REPORT, HISTORY_DB)
        print_summary(
            results,
            archive_summary,
            CSV_REPORT,
            HISTORY_DB,
        )

    except HttpError as e:
        print()
        print("Search Console API error:")
        print(e)


if __name__ == "__main__":
    main()
