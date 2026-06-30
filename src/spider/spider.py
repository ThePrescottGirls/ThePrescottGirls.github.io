from pathlib import Path

from googleapiclient.errors import HttpError

from sitemap import read_sitemap_urls
from inspector import inspect_urls
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


def print_summary(results, archive_summary):
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
        print_summary(results, archive_summary)

    except HttpError as e:
        print()
        print("Search Console API error:")
        print(e)


if __name__ == "__main__":
    main()
