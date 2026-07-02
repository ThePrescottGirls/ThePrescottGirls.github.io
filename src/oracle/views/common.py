from __future__ import annotations

import html
import sqlite3
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urlparse


def fetchone(connection: sqlite3.Connection, sql: str, parameters: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    cursor = connection.cursor()
    cursor.execute(sql, parameters)
    return cursor.fetchone()


def fetchall(connection: sqlite3.Connection, sql: str, parameters: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    cursor = connection.cursor()
    cursor.execute(sql, parameters)
    return cursor.fetchall()


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = fetchone(
        connection,
        """
        SELECT name
          FROM sqlite_master
         WHERE type = 'table'
           AND name = ?
        """,
        (table_name,),
    )
    return row is not None


def count_rows(connection: sqlite3.Connection, table_name: str) -> int:
    if not table_exists(connection, table_name):
        return 0

    row = fetchone(connection, f"SELECT COUNT(*) AS count FROM {table_name}")
    return int(row["count"]) if row else 0


def print_heading(title: str, underline: str = "=") -> None:
    print(title)
    print(underline * len(title))
    print()


def print_key_value(label: str, value: Any) -> None:
    print(f"{label:<18}: {value}")


def print_rows(rows: Iterable[sqlite3.Row | dict[str, Any]], columns: list[tuple[str, str]], empty_message: str) -> None:
    rows = list(rows)

    if not rows:
        print(empty_message)
        return

    widths: list[int] = []
    for key, heading in columns:
        max_value_width = max(len(str(row[key] if row[key] is not None else "")) for row in rows)
        widths.append(max(len(heading), max_value_width))

    header = "  ".join(heading.ljust(width) for (_, heading), width in zip(columns, widths))
    rule = "  ".join("-" * width for width in widths)

    print(header)
    print(rule)

    for row in rows:
        values = []
        for index, (key, _) in enumerate(columns):
            value = row[key]
            values.append(str(value if value is not None else "").ljust(widths[index]))
        print("  ".join(values))


def html_escape(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def domain_from_url(url: str | None) -> str:
    if not url:
        return ""

    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def short_path_from_url(url: str | None) -> str:
    if not url:
        return ""

    parsed = urlparse(url)
    path = unquote(parsed.path or "/")
    return path


def write_html_page(output_dir: str | Path, filename: str, title: str, body: str, nav_items: list[tuple[str, str]]) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    nav = "\n".join(
        f'<a href="{html_escape(href)}">{html_escape(label)}</a>'
        for label, href in nav_items
    )

    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html_escape(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {{
    color-scheme: light;
    --bg: #f6f4ef;
    --card: #ffffff;
    --text: #1f2933;
    --muted: #667085;
    --line: #d8d3c8;
    --good: #1f7a4d;
    --warn: #b26a00;
    --bad: #b42318;
    --neutral: #344054;
}}
body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--text);
}}
header {{
    padding: 24px 32px 12px;
}}
nav {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    padding: 0 32px 22px;
}}
nav a {{
    color: var(--neutral);
    text-decoration: none;
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 6px 12px;
}}
main {{
    padding: 0 32px 48px;
    max-width: 1180px;
}}
.card {{
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 18px 20px;
    margin: 0 0 16px;
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
}}
.grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;
}}
.metric {{
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 14px 16px;
}}
.metric .label {{
    color: var(--muted);
    font-size: 0.86rem;
}}
.metric .value {{
    font-size: 1.6rem;
    font-weight: 700;
    margin-top: 4px;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    background: var(--card);
    border: 1px solid var(--line);
}}
th, td {{
    text-align: left;
    padding: 9px 10px;
    border-bottom: 1px solid var(--line);
    vertical-align: top;
}}
th {{
    color: var(--muted);
    font-weight: 600;
    font-size: 0.88rem;
}}
.badge {{
    display: inline-block;
    border-radius: 999px;
    padding: 3px 9px;
    font-size: 0.82rem;
    border: 1px solid var(--line);
    color: var(--neutral);
}}
.good {{ color: var(--good); }}
.warn {{ color: var(--warn); }}
.bad {{ color: var(--bad); }}
.muted {{ color: var(--muted); }}
.result-list {{
    margin-top: 12px;
}}
.result-row {{
    display: grid;
    grid-template-columns: 48px 220px 1fr;
    gap: 12px;
    padding: 8px 0;
    border-top: 1px solid var(--line);
}}
.result-row a {{
    color: var(--neutral);
}}
@media (max-width: 740px) {{
    header, nav, main {{ padding-left: 18px; padding-right: 18px; }}
    .result-row {{ grid-template-columns: 42px 1fr; }}
    .result-title {{ grid-column: 2; }}
}}
</style>
</head>
<body>
<header>
<h1>{html_escape(title)}</h1>
</header>
<nav>
{nav}
</nav>
<main>
{body}
</main>
</body>
</html>
"""

    target = output_path / filename
    target.write_text(document, encoding="utf-8")
    return target
