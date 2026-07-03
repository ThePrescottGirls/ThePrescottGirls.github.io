#!/usr/bin/env python3
"""
config.py

Shared configuration loader for Oracle.

All Oracle tools should read config.ini through this module rather than
hard-coding project settings.
"""

from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path


CONFIG_FILE = Path(__file__).with_name("config.ini")


class Config:
    """Simple configuration service."""

    def __init__(self, parser: ConfigParser):
        self._parser = parser

    def website(self) -> str:
        """Return the configured website."""
        return self.require("project.website")

    def get(self, key: str, default: str | None = None) -> str | None:
        """
        Return a configuration value.

        Args:
            key: Configuration key in the form "section.option".
            default: Value returned if the key does not exist.

        Returns:
            Configuration value or default.
        """
        try:
            section, option = key.split(".", 1)
        except ValueError:
            raise ValueError(
                f"Invalid configuration key '{key}'. "
                "Expected 'section.option'."
            )

        value = self._parser.get(section, option, fallback=default)

        if isinstance(value, str):
            value = value.strip()

        return value

    def require(self, key: str) -> str:
        """
        Return a required configuration value.

        Raises:
            ValueError if the value is missing or empty.
        """
        value = self.get(key)

        if not value:
            raise ValueError(
                f"Missing required configuration value '{key}' in {CONFIG_FILE.name}"
            )

        return value


def load_config(config_file: str | Path = CONFIG_FILE) -> Config:
    """
    Load Oracle configuration from config.ini.
    """
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

2. Edit config.ini and enter your project settings.

IMPORTANT

config.ini contains private information and should NEVER be
committed to GitHub.

Only config_TEMPLATE.ini belongs in the repository.
"""
        )

    parser = ConfigParser()
    parser.read(path)

    return Config(parser)


if __name__ == "__main__":
    config = load_config()

    print("Oracle Configuration")
    print("====================")
    print()

    print("Project")
    print("-------")
    print(f"Website : {config.website()}")
