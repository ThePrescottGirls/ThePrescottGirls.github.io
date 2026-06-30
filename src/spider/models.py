from dataclasses import dataclass


@dataclass
class URLResult:
    url: str
    verdict: str = ""
    coverage: str = ""
    last_crawl: str = ""
    user_canonical: str = ""
    google_canonical: str = ""
    robots: str = ""
    fetch: str = ""
    indexing: str = ""
    crawled_as: str = ""
    error: str = ""
