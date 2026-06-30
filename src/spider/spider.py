from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from sitemap import read_sitemap_urls

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parents[1]

CREDENTIALS_DIR = BASE_DIR / "credentials"
REPORTS_DIR = BASE_DIR / "reports"
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

    try:
        for i, url in enumerate(urls, start=1):
            print(f"[{i:2}/{len(urls)}] {url}")

            response = inspect_url(service, url)
            status = response["inspectionResult"]["indexStatusResult"]

            print(f"    {status.get('coverageState', 'Unknown')}")

    except HttpError as e:
        print()
        print("Search Console API error:")
        print(e)


if __name__ == "__main__":
    main()
