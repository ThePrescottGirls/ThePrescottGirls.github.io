#!/usr/bin/env python3
"""
dashboard.py

Generate a stand-alone HTML dashboard from inspection_history.db.

Use directly:
    python dashboard.py

Optional:
    python dashboard.py --db reports/inspection_history.db --output reports/index.html
"""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
from urllib.parse import unquote, urlparse

from archive import latest_archive_summary, latest_inspections


BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "reports"

DEFAULT_HISTORY_DB = REPORTS_DIR / "inspection_history.db"
DEFAULT_OUTPUT_FILE = REPORTS_DIR / "index.html"


INDEXED_COVERAGE_VALUES = {
    "Submitted and indexed",
    "Indexed, not submitted in sitemap",
}


def coverage_group(coverage: str) -> str:
    coverage = coverage or "Unknown"

    if coverage in INDEXED_COVERAGE_VALUES:
        return "indexed"

    if coverage == "URL is unknown to Google":
        return "unknown"

    if "canonical" in coverage.lower():
        return "canonical"

    return "other"


def path_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    return unquote(path)


def html_attr(value: object) -> str:
    return escape(str(value or ""), quote=True)


def html_text(value: object) -> str:
    return escape(str(value or ""))


def inspection_value(row: dict, key: str) -> str:
    return str(row.get(key) or "")


def sort_by_path(row: dict) -> str:
    return path_from_url(inspection_value(row, "url")).lower()


def build_attention_html(rows: list[dict]) -> str:
    if not rows:
        return '<div class="empty">No pages currently need attention.</div>'

    parts = []

    for row in rows:
        url = inspection_value(row, "url")
        path = path_from_url(url)
        coverage = inspection_value(row, "coverage") or "Unknown"
        group = coverage_group(coverage)

        parts.append(
            f"""
            <div class="attention-item status-{group}">
                <div>
                    <div class="attention-title">{html_text(path)}</div>
                    <div class="attention-status">{html_text(coverage)}</div>
                </div>
                <button class="copy-button" data-copy="{html_attr(url)}">Copy URL</button>
            </div>
            """
        )

    return "\n".join(parts)


def build_changes_html(changes: list[dict]) -> str:
    if not changes:
        return '<div class="empty">No changes since previous run.</div>'

    parts = []

    for change in changes[:25]:
        url = str(change.get("url") or "")
        path = path_from_url(url)
        previous = str(change.get("previous_coverage") or "new URL")
        current = str(change.get("current_coverage") or "")

        parts.append(
            f"""
            <div class="change-item">
                <div class="change-path">{html_text(path)}</div>
                <div class="change-status">
                    {html_text(previous)}
                    <span class="arrow">→</span>
                    {html_text(current)}
                </div>
            </div>
            """
        )

    remaining = len(changes) - 25
    if remaining > 0:
        parts.append(f'<div class="empty">...and {remaining} more</div>')

    return "\n".join(parts)


def build_rows_html(rows: list[dict]) -> str:
    parts = []

    for row in rows:
        url = inspection_value(row, "url")
        path = path_from_url(url)
        coverage = inspection_value(row, "coverage") or "Unknown"
        group = coverage_group(coverage)

        parts.append(
            f"""
            <tr class="status-{group}">
                <td class="path-cell" data-sort="{html_attr(path.lower())}">
                    <a href="{html_attr(url)}" target="_blank" rel="noopener noreferrer">{html_text(path)}</a>
                </td>
                <td data-sort="{html_attr(group)}">
                    <span class="badge badge-{group}">{html_text(coverage)}</span>
                </td>
                <td data-sort="{html_attr(inspection_value(row, "last_crawl"))}">
                    {html_text(inspection_value(row, "last_crawl"))}
                </td>
                <td>{html_text(inspection_value(row, "robots"))}</td>
                <td>{html_text(inspection_value(row, "fetch"))}</td>
                <td>{html_text(inspection_value(row, "indexing"))}</td>
                <td class="canonical-cell">{html_text(inspection_value(row, "user_canonical"))}</td>
                <td class="canonical-cell">{html_text(inspection_value(row, "google_canonical"))}</td>
                <td>
                    <button class="copy-button" data-copy="{html_attr(url)}">Copy</button>
                </td>
            </tr>
            """
        )

    return "\n".join(parts)


def write_dashboard(
    db_file: str | Path = DEFAULT_HISTORY_DB,
    output_file: str | Path = DEFAULT_OUTPUT_FILE,
) -> None:
    db_file = Path(db_file).expanduser().resolve()
    output_file = Path(output_file).expanduser().resolve()

    summary = latest_archive_summary(db_file)
    inspections = latest_inspections(db_file)

    indexed = []
    unknown = []
    canonical = []
    other = []

    for row in inspections:
        group = coverage_group(inspection_value(row, "coverage"))
        if group == "indexed":
            indexed.append(row)
        elif group == "unknown":
            unknown.append(row)
        elif group == "canonical":
            canonical.append(row)
        else:
            other.append(row)

    needs_attention = sorted(
        unknown + canonical + other,
        key=sort_by_path,
    )

    sorted_inspections = sorted(
        inspections,
        key=sort_by_path,
    )

    changes = list(summary.get("changes") or [])
    needs_attention_urls = "\n".join(inspection_value(row, "url") for row in needs_attention)

    run_id = summary.get("run_id") or ""
    run_time = summary.get("run_time") or ""
    changed = "yes" if summary.get("changed") else "no"

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Search Console Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {{
    --bg: #f6f7f9;
    --panel: #ffffff;
    --text: #1f2937;
    --muted: #6b7280;
    --line: #d1d5db;
    --green-bg: #dcfce7;
    --green-text: #166534;
    --yellow-bg: #fef9c3;
    --yellow-text: #854d0e;
    --red-bg: #fee2e2;
    --red-text: #991b1b;
    --blue-bg: #dbeafe;
    --blue-text: #1e40af;
}}

* {{ box-sizing: border-box; }}

body {{
    margin: 0;
    padding: 28px;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}

header {{
    margin-bottom: 24px;
}}

h1 {{
    margin: 0 0 8px;
    font-size: 28px;
}}

h2 {{
    margin: 0 0 14px;
    font-size: 20px;
}}

.meta {{
    color: var(--muted);
    font-size: 14px;
}}

.cards {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 14px;
    margin-bottom: 24px;
}}

.card {{
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, .04);
}}

.card-label {{
    color: var(--muted);
    font-size: 13px;
    margin-bottom: 8px;
}}

.card-value {{
    font-size: 32px;
    font-weight: 700;
}}

.panel {{
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 18px;
    margin-bottom: 24px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, .04);
}}

.toolbar {{
    display: flex;
    gap: 10px;
    align-items: center;
    flex-wrap: wrap;
    margin-bottom: 14px;
}}

button {{
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #ffffff;
    color: var(--text);
    padding: 7px 10px;
    font-size: 13px;
    cursor: pointer;
}}

button:hover {{
    background: #f3f4f6;
}}

.copy-all {{
    font-weight: 600;
}}

.attention-list,
.change-list {{
    display: grid;
    gap: 10px;
}}

.attention-item {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    border: 1px solid var(--line);
    border-left-width: 5px;
    border-radius: 10px;
    padding: 12px;
}}

.attention-title,
.change-path {{
    font-weight: 600;
    overflow-wrap: anywhere;
}}

.attention-status,
.change-status {{
    color: var(--muted);
    font-size: 13px;
    margin-top: 4px;
}}

.change-item {{
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 10px;
}}

.status-indexed {{
    border-left-color: #22c55e;
}}

.status-unknown {{
    border-left-color: #ef4444;
}}

.status-canonical {{
    border-left-color: #f59e0b;
}}

.status-other {{
    border-left-color: #3b82f6;
}}

.table-wrap {{
    overflow: auto;
    border: 1px solid var(--line);
    border-radius: 10px;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    min-width: 1100px;
    background: white;
}}

th,
td {{
    padding: 10px 12px;
    border-bottom: 1px solid var(--line);
    text-align: left;
    vertical-align: top;
    font-size: 13px;
}}

th {{
    position: sticky;
    top: 0;
    z-index: 1;
    background: #f9fafb;
    color: #374151;
    user-select: none;
    cursor: pointer;
    white-space: nowrap;
}}

tr:last-child td {{
    border-bottom: 0;
}}

.path-cell {{
    font-weight: 600;
    overflow-wrap: anywhere;
}}

.path-cell a {{
    color: inherit;
    text-decoration: none;
}}

.path-cell a:hover {{
    text-decoration: underline;
}}

.canonical-cell {{
    max-width: 260px;
    overflow-wrap: anywhere;
    color: var(--muted);
}}

.badge {{
    display: inline-block;
    border-radius: 999px;
    padding: 4px 8px;
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
}}

.badge-indexed {{
    background: var(--green-bg);
    color: var(--green-text);
}}

.badge-unknown {{
    background: var(--red-bg);
    color: var(--red-text);
}}

.badge-canonical {{
    background: var(--yellow-bg);
    color: var(--yellow-text);
}}

.badge-other {{
    background: var(--blue-bg);
    color: var(--blue-text);
}}

.empty {{
    color: var(--muted);
    font-style: italic;
}}

.arrow {{
    padding: 0 6px;
}}

.toast {{
    position: fixed;
    right: 18px;
    bottom: 18px;
    background: #111827;
    color: white;
    padding: 10px 14px;
    border-radius: 10px;
    opacity: 0;
    transform: translateY(8px);
    transition: opacity .15s ease, transform .15s ease;
    pointer-events: none;
}}

.toast.show {{
    opacity: 1;
    transform: translateY(0);
}}

@media (max-width: 700px) {{
    body {{
        padding: 16px;
    }}

    .attention-item {{
        align-items: flex-start;
        flex-direction: column;
    }}
}}
</style>
</head>
<body>
<header>
    <h1>Search Console Dashboard</h1>
    <div class="meta">
        Run ID: {html_text(run_id)}
        · Run time: {html_text(run_time)}
        · Changed since previous run: {html_text(changed)}
        · DB: {html_text(db_file)}
    </div>
</header>

<section class="cards">
    <div class="card">
        <div class="card-label">Pages inspected</div>
        <div class="card-value">{len(inspections)}</div>
    </div>
    <div class="card">
        <div class="card-label">Indexed</div>
        <div class="card-value">{len(indexed)}</div>
    </div>
    <div class="card">
        <div class="card-label">Unknown to Google</div>
        <div class="card-value">{len(unknown)}</div>
    </div>
    <div class="card">
        <div class="card-label">Canonical issues</div>
        <div class="card-value">{len(canonical)}</div>
    </div>
    <div class="card">
        <div class="card-label">Other issues</div>
        <div class="card-value">{len(other)}</div>
    </div>
    <div class="card">
        <div class="card-label">Changed URLs</div>
        <div class="card-value">{len(changes)}</div>
    </div>
</section>

<section class="panel">
    <h2>Needs Attention</h2>
    <div class="toolbar">
        <button class="copy-all" data-copy="{html_attr(needs_attention_urls)}">Copy All Needs-Attention URLs</button>
        <span class="meta">{len(needs_attention)} URL(s)</span>
    </div>
    <div class="attention-list">
        {build_attention_html(needs_attention)}
    </div>
</section>

<section class="panel">
    <h2>Changes Since Previous Run</h2>
    <div class="change-list">
        {build_changes_html(changes)}
    </div>
</section>

<section class="panel">
    <h2>Pages</h2>
    <div class="toolbar">
        <span class="meta">Default sort: path. Click a column heading to sort.</span>
    </div>
    <div class="table-wrap">
        <table id="pages-table">
            <thead>
                <tr>
                    <th data-type="text">Path</th>
                    <th data-type="text">Coverage</th>
                    <th data-type="text">Last Crawl</th>
                    <th data-type="text">Robots</th>
                    <th data-type="text">Fetch</th>
                    <th data-type="text">Indexing</th>
                    <th data-type="text">User Canonical</th>
                    <th data-type="text">Google Canonical</th>
                    <th data-type="none">Copy</th>
                </tr>
            </thead>
            <tbody>
                {build_rows_html(sorted_inspections)}
            </tbody>
        </table>
    </div>
</section>

<div id="toast" class="toast">Copied</div>

<script>
function showToast(message) {{
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.classList.add("show");
    window.setTimeout(() => toast.classList.remove("show"), 1200);
}}

async function copyText(text) {{
    try {{
        await navigator.clipboard.writeText(text);
        showToast("Copied");
    }} catch (error) {{
        const textarea = document.createElement("textarea");
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        textarea.remove();
        showToast("Copied");
    }}
}}

document.querySelectorAll("[data-copy]").forEach(button => {{
    button.addEventListener("click", () => copyText(button.dataset.copy || ""));
}});

document.querySelectorAll("#pages-table th").forEach((header, columnIndex) => {{
    if (header.dataset.type === "none") {{
        return;
    }}

    header.addEventListener("click", () => {{
        const table = header.closest("table");
        const tbody = table.querySelector("tbody");
        const rows = Array.from(tbody.querySelectorAll("tr"));
        const ascending = header.dataset.ascending !== "true";

        rows.sort((a, b) => {{
            const aCell = a.children[columnIndex];
            const bCell = b.children[columnIndex];

            const aValue = (aCell.dataset.sort || aCell.textContent || "").trim().toLowerCase();
            const bValue = (bCell.dataset.sort || bCell.textContent || "").trim().toLowerCase();

            if (aValue < bValue) return ascending ? -1 : 1;
            if (aValue > bValue) return ascending ? 1 : -1;
            return 0;
        }});

        document.querySelectorAll("#pages-table th").forEach(th => delete th.dataset.ascending);
        header.dataset.ascending = ascending ? "true" : "false";

        rows.forEach(row => tbody.appendChild(row));
    }});
}});
</script>
</body>
</html>
"""

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the Search Console dashboard from inspection_history.db."
    )

    parser.add_argument(
        "--db",
        default=DEFAULT_HISTORY_DB,
        help="SQLite database path. Default: reports/inspection_history.db",
    )

    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_FILE,
        help="Output HTML path. Default: reports/index.html",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        write_dashboard(
            db_file=args.db,
            output_file=args.output,
        )
    except Exception as exc:
        print(f"Dashboard failed: {exc}")
        return 1

    print("Dashboard written to:")
    print(f"  {Path(args.output).expanduser().resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
