#!/usr/bin/env python3
"""
config.py

Shared configuration loader for Oracle.

All Oracle tools should read config.ini through this module rather than
hard-coding website URLs or other project settings.
"""

from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path


CONFIG_FILE = Path("config.ini")


@dataclass(frozen=True)
class OracleConfig:
    website: str
    search_google_api_key: str
    search_google_engine_id: str


def load_config(config_file: str | Path = CONFIG_FILE) -> OracleConfig:
    """Load Oracle configuration from config.ini."""
    path = Path(config_file)

    if not path.exists():
        raise FileNotFoundError(
            f"""
Configuration file not found: {path}

To configure Oracle:

1. Copy

       config_TEMPLATE.ini

   to

       config.ini

2. Edit config.ini and enter your website and API credentials.

IMPORTANT

config.ini contains private information and should NEVER be
committed to GitHub.

Only config_TEMPLATE.ini belongs in the repository.
"""
        )

    parser = ConfigParser()
    parser.read(path)

    if "project" not in parser:
        raise ValueError("Missing [project] section in config.ini")

    website = parser.get("project", "website", fallback="").strip()

    if not website:
        raise ValueError("Missing 'website' setting in [project] section of config.ini")
        
    search_google_api_key = parser.get(
        "search",
        "GOOGLE_SEARCH_API_KEY",
        fallback=""
    ).strip()

    search_google_engine_id = parser.get(
        "search",
        "GOOGLE_SEARCH_ENGINE_ID",
        fallback=""
    ).strip()

    return OracleConfig(
        website=website,
        search_google_api_key=search_google_api_key,
        search_google_engine_id=search_google_engine_id,
    )

if __name__ == "__main__":
    config = load_config()
    print("Oracle Configuration")
    print("====================")
    print()
    print(f"Website : {config.website}")
