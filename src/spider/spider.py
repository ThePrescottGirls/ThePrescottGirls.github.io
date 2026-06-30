from pathlib import Path
import time

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from sitemap import read_sitemap_urls
from models import URLResult
from report import write_inspection_csv
from archive import archive

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


def inspect_url(service, url):
    request = {
        "inspectionUrl": url,
        "siteUrl": PROPERTY_URL,
        "languageCode": "en-US",
    }

    return (
        service.urlInspection()
        .index()
        .inspect(body=request)
        .execute()
    )


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
        print(f"Expected location:")
        print(f"  {CREDENTIALS_FILE}")
        return

    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=SCOPES,
    )

    service = build("searchconsole", "v1", credentials=credentials)

    results = []

    try:
        for i, url in enumerate(urls, start=1):
            print(f"[{i:2}/{len(urls)}] {url}")

            for attempt in range(1, 4):
                try:
                    response = inspect_url(service, url)
                    break
                except TimeoutError:
                    if attempt == 3:
                        raise
                    print(f"    Timeout, retrying ({attempt}/3)...")
                    time.sleep(5)
            
            
            status = response["inspectionResult"]["indexStatusResult"]

            result = URLResult(
                url=url,
                verdict=status.get("verdict", ""),
                coverage=status.get("coverageState", ""),
                last_crawl=status.get("lastCrawlTime", ""),
                user_canonical=status.get("userCanonical", ""),
                google_canonical=status.get("googleCanonical", ""),
                robots=status.get("robotsTxtState", ""),
                fetch=status.get("pageFetchState", ""),
                indexing=status.get("indexingState", ""),
                crawled_as=status.get("crawledAs", ""),
            )

            results.append(result)

            print(f"    {result.coverage or 'Unknown'}")

        write_inspection_csv(results, CSV_REPORT)

        archive_summary = archive(CSV_REPORT, HISTORY_DB)

        # -------------------------------------------------------------
        # Summary
        # -------------------------------------------------------------

        indexed = []
        unknown = []
        canonical = []
        other = []

        indexed_states = {
            "Submitted and indexed",
            "Indexed, not submitted in sitemap",
        }

        for result in results:
            coverage = result.coverage or "Unknown"

            if coverage in indexed_states:
                indexed.append(result)
            elif coverage == "URL is unknown to Google":
                unknown.append(result)
            elif "canonical" in coverage.lower():
                canonical.append(result)
            else:
                other.append(result)

        print()
        print("===========================================")
        print("SUMMARY")
        print("===========================================")
        print()

        print(f"Pages inspected:        {len(results)}")
        print(f"Indexed:                {len(indexed)}")
        print(f"Unknown to Google:      {len(unknown)}")
        print(f"Canonical issues:       {len(canonical)}")
        print(f"Other issues:           {len(other)}")

        if unknown or canonical or other:
            print()
            print("Needs Attention")
            print("----------------")

            for result in unknown:
                print(f"• {Path(result.url).name}")
                print("    URL is unknown to Google")

            for result in canonical:
                print(f"• {Path(result.url).name}")
                print(f"    {result.coverage}")

            for result in other:
                print(f"• {Path(result.url).name}")
                print(f"    {result.coverage or 'Unknown'}")

        print()
        print("CSV report written to:")
        print(f"  {CSV_REPORT}")

        print()
        print("History database updated:")
        print(f"  {HISTORY_DB}")
        print(f"  Run ID: {archive_summary['run_id']}")
        changed = "yes" if archive_summary["changed"] else "no"
        print(f"  Changed since previous run: {changed}")

        if archive_summary["changes"]:
            print()
            print("Changed URLs")
            print("------------")

            for change in archive_summary["changes"][:10]:
                print(f"• {Path(change['url']).name}")
                print(f"    {change['previous_coverage']} -> {change['current_coverage']}")

            remaining = len(archive_summary["changes"]) - 10
            if remaining > 0:
                print(f"    ...and {remaining} more")

    except HttpError as e:
        print()
        print("Search Console API error:")
        print(e)


if __name__ == "__main__":
    main()
