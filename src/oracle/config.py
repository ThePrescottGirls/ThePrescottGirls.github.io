#!/usr/bin/env python3
"""
config.py

Simple INI configuration loader.

Provides access to configuration values using hierarchical keys in the
form "section.option".
"""

from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path


CONFIG_FILE = Path(__file__).with_name("config.ini")


class Config:
    """Simple configuration service."""

    def __init__(self, parser: ConfigParser):
        self._parser = parser

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


def load_config(config_file: str | Path | None = None) -> Config:
    """
    Load configuration from an INI file.

    If no configuration file is specified, config.ini in the same
    directory as this module is used.
    """
    if config_file is None:
        config_file = CONFIG_FILE

    path = Path(config_file)

    if not path.exists():
        raise FileNotFoundError(
            f"""
Configuration file not found: {path}

Create the configuration file and add the required settings.

Do not commit configuration files containing private values, credentials,
or local machine settings.
"""
        )

    parser = ConfigParser()
    parser.read(path)

    return Config(parser)


if __name__ == "__main__":
    load_config()
    print("Configuration loaded.")
