#!/usr/bin/env python3
"""
common.py

Shared Oracle application helpers.

This module contains Oracle-level routines shared by multiple applications.
It sits above the generic config loader and below individual tools such as
Discovery, Search, Seed Queries, and Dashboard.
"""

from __future__ import annotations

from pathlib import Path

from config import Config
from database import database_path_for_site


def website(config: Config) -> str:
    """Return the configured Oracle website."""
    return config.require("project.website")


def database_path(config: Config) -> Path:
    """Return the database path for the configured Oracle website."""
    return database_path_for_site(website(config))
