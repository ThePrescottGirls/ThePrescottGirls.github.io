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


def load_config(config_file: str | Path = CONFIG_FILE) -> OracleConfig:
    """Load Oracle configuration from config.ini."""
    path = Path(config_file)

    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}\n"
            "Create config.ini with:\n\n"
            "# Oracle Configuration\n\n"
            "[project]\n"
            "website = https://www.example.com\n"
        )

    parser = ConfigParser()
    parser.read(path)

    if "project" not in parser:
        raise ValueError("Missing [project] section in config.ini")

    website = parser.get("project", "website", fallback="").strip()

    if not website:
        raise ValueError("Missing 'website' setting in [project] section of config.ini")

    return OracleConfig(website=website)


if __name__ == "__main__":
    config = load_config()
    print("Oracle Configuration")
    print("====================")
    print()
    print(f"Website : {config.website}")
