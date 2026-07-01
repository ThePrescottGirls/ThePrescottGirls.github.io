from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable, List

from google.oauth2 import service_account
from googleapiclient.discovery import build

from models import URLResult


def build_service(credentials_file: str | Path, scopes: list[str]):
    credentials = service_account.Credentials.from_service_account_file(
        credentials_file,
        scopes=scopes,
    )

    return build("searchconsole", "v1", credentials=credentials)


def inspect_url(service, url: str, property_url: str, language_code: str = "en-US") -> dict:
    request = {
        "inspectionUrl": url,
        "siteUrl": property_url,
        "languageCode": language_code,
    }

    return (
        service.urlInspection()
        .index()
        .inspect(body=request)
        .execute()
    )


def inspect_url_with_retries(
    service,
    url: str,
    property_url: str,
    retries: int = 3,
    retry_delay_seconds: int = 5,
) -> dict:
    for attempt in range(1, retries + 1):
        try:
            return inspect_url(service, url, property_url)
        except TimeoutError:
            if attempt == retries:
                raise
            print(f"    Timeout, retrying ({attempt}/{retries})...")
            time.sleep(retry_delay_seconds)

    raise RuntimeError("URL inspection failed unexpectedly.")


def result_from_response(url: str, response: dict) -> URLResult:
    status = response["inspectionResult"]["indexStatusResult"]

    return URLResult(
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


def inspect_urls(
    urls: Iterable[str],
    credentials_file: str | Path,
    property_url: str,
    scopes: list[str],
) -> List[URLResult]:
    url_list = list(urls)
    service = build_service(credentials_file, scopes)
    results: List[URLResult] = []

    for i, url in enumerate(url_list, start=1):
        print(f"[{i:2}/{len(url_list)}] {url}")

        response = inspect_url_with_retries(service, url, property_url)
        result = result_from_response(url, response)

        results.append(result)
        print(f"    {result.coverage or 'Unknown'}")

    return results
