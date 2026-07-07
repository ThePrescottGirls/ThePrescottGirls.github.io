#!/usr/bin/env python3
"""
buildsite.py

Small static-site helper for The Prescott Girls.

This version does not require page directives such as:

    <!--#HEADER PAGE=book-->

Instead, it determines the active navigation item from the filename.

Template location:
    src/buildsite/templates/header.html

The header template should contain nav class placeholders:

    {{HOME}}
    {{BOOK}}
    {{GALLERIES}}
    {{INTERPRETATIONS}}
    {{RESEARCH}}
    {{AUTHOR}}
    {{TEACHERS}}
    {{EVENTS}}
    {{FAQ}}

The placeholder matching the current page is replaced with "active".
All other placeholders are replaced with an empty string.

The generated header is inserted only inside <body>. If the page begins
with a skip link immediately after <body>, the header is inserted after
that skip link so the skip link remains the first focusable element.
Any earlier generated TPG header blocks are removed first, including
accidental headers before <head> or inside <head>.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR / "templates"
HEADER_TEMPLATE = TEMPLATE_DIR / "header.html"

HEADER_START = "<!-- TPG_HEADER_START -->"
HEADER_END = "<!-- TPG_HEADER_END -->"

BODY_OPEN_RE = re.compile(r"(<body\b[^>]*>)", re.IGNORECASE)
SKIP_LINK_RE = re.compile(
    r"^(\s*<a\b[^>]*class=[\'\"][^\'\"]*\bskip\b[^\'\"]*[\'\"][^>]*>.*?</a>)",
    re.IGNORECASE | re.DOTALL,
)
MAIN_OPEN_RE = re.compile(r"<main\b[^>]*>", re.IGNORECASE)
HEADER_BLOCK_RE = re.compile(r"\s*<header\b[^>]*>.*?</header>\s*", re.IGNORECASE | re.DOTALL)
MARKED_HEADER_RE = re.compile(
    re.escape(HEADER_START) + r".*?" + re.escape(HEADER_END),
    re.IGNORECASE | re.DOTALL,
)

NAV_KEYS = {
    "home": "HOME",
    "index": "HOME",

    "book": "BOOK",

    "illustrations": "GALLERIES",
    "historicalgallery": "GALLERIES",
    "authorgallery": "GALLERIES",

    "interpretations": "INTERPRETATIONS",
    "research": "RESEARCH",
    "author": "AUTHOR",
    "teachers": "TEACHERS",
    "events": "EVENTS",
    "faq": "FAQ",
}


def read_text(path: Path) -> str:
    """Read a UTF-8 text file with a useful error message."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SystemExit(f"Missing file: {path}")
    except OSError as exc:
        raise SystemExit(f"Unable to read {path}: {exc}")


def write_text(path: Path, text: str) -> None:
    """Write a UTF-8 text file with a useful error message."""
    try:
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"Unable to write {path}: {exc}")


def page_key_for_path(path: Path) -> str:
    """Return the navigation key name inferred from the HTML filename."""
    name = path.stem.strip().lower()
    active_key = NAV_KEYS.get(name)

    if active_key is None:
        known = ", ".join(sorted(NAV_KEYS))
        raise SystemExit(
            f"Unknown page '{path.name}'. "
            f"Add '{name}' to NAV_KEYS in buildsite.py. Known pages: {known}"
        )

    return active_key


def render_header(active_key: str) -> str:
    """Render the shared header and mark the current page active."""
    header = read_text(HEADER_TEMPLATE)

    for key in set(NAV_KEYS.values()):
        placeholder = "{{" + key + "}}"
        header = header.replace(placeholder, "active" if key == active_key else "")

    return f"{HEADER_START}\n{header.strip()}\n{HEADER_END}"


def remove_marked_headers(html: str) -> str:
    """Remove any previously generated marked TPG headers."""
    return MARKED_HEADER_RE.sub("", html)


def remove_bad_headers_before_body(html: str) -> str:
    """
    Remove accidental header blocks before <body>.

    This cleans up files where a rendered header was accidentally placed
    before <head> or inside <head>. It deliberately does not touch anything
    after the opening <body> tag.
    """
    body_match = BODY_OPEN_RE.search(html)
    if not body_match:
        raise SystemExit("No <body> tag found.")

    before_body = html[:body_match.start()]
    body_and_after = html[body_match.start():]

    before_body = HEADER_BLOCK_RE.sub("\n", before_body)
    before_body = re.sub(r"\n{3,}", "\n\n", before_body)

    return before_body + body_and_after


def remove_first_header_before_main(body_content: str) -> str:
    """
    Remove the first header block after <body> and before <main>.

    This handles older unmarked generated headers. It does not remove headers
    inside page content after <main>.
    """
    main_match = MAIN_OPEN_RE.search(body_content)

    if main_match:
        before_main = body_content[:main_match.start()]
        main_and_after = body_content[main_match.start():]
        before_main = HEADER_BLOCK_RE.sub("\n", before_main, count=1)
        before_main = re.sub(r"\n{3,}", "\n\n", before_main)
        return before_main + main_and_after

    return HEADER_BLOCK_RE.sub("\n", body_content, count=1)


def insert_header_after_body(html: str, header: str) -> str:
    """
    Insert the rendered header inside <body>.

    If a skip link appears immediately after the opening <body> tag, preserve
    it before the header so it remains the first focusable element.
    """
    body_match = BODY_OPEN_RE.search(html)
    if not body_match:
        raise SystemExit("No <body> tag found.")

    before_body_tag = html[:body_match.end()]
    body_content = html[body_match.end():]

    body_content = remove_first_header_before_main(body_content)
    body_content = body_content.lstrip()

    skip_match = SKIP_LINK_RE.match(body_content)
    if skip_match:
        skip_link = skip_match.group(1).strip()
        rest = body_content[skip_match.end():].lstrip()
        return before_body_tag + "\n" + skip_link + "\n" + header + "\n" + rest

    return before_body_tag + "\n" + header + "\n" + body_content


def build_page(path: Path) -> bool:
    """
    Replace the shared header in one page.

    Returns True if the page was changed, False if unchanged.
    """
    original = read_text(path)

    active_key = page_key_for_path(path)
    header = render_header(active_key)

    updated = remove_marked_headers(original)
    updated = remove_bad_headers_before_body(updated)
    updated = insert_header_after_body(updated, header)

    if updated == original:
        print(f"Skipped {path} — already up to date")
        return False

    write_text(path, updated)
    print(f"Updated {path}")
    return True


def main(argv: list[str]) -> int:
    if not argv:
        print("Usage: python3 src/buildsite/buildsite.py PAGE.html [PAGE.html ...]")
        return 2

    changed = 0

    for arg in argv:
        path = Path(arg)

        if not path.exists():
            print(f"Missing page: {path}", file=sys.stderr)
            continue

        if path.is_dir():
            print(f"Skipping directory: {path}", file=sys.stderr)
            continue

        if path.suffix.lower() not in {".html", ".htm"}:
            print(f"Skipping non-HTML file: {path}", file=sys.stderr)
            continue

        if build_page(path):
            changed += 1

    print(f"\nDone. Updated {changed} page(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
