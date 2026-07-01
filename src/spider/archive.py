#!/usr/bin/env python3
"""
archive.py

Import a Google URL Inspection CSV snapshot into a local SQLite history database.

Use from spider.py:
    from archive import archive
    summary = archive("reports/inspection.csv", "reports/inspection_history.db")

Use directly:
    python archive.py inspection.csv
    python archive.py inspection.csv --db inspection_history.db
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Any


EXPECTED_COLUMNS = [
    "url",
    "verdict",
    "coverage",
    "last_crawl",
    "user_canonical",
    "google_canonical",
    "robots",
    "fetch",
    "indexing",
    "crawled_as",
]

INDEXED_COVERAGE_VALUES = {
    "Submitted and indexed",
    "Indexed, not submitted in sitemap",
}


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def normalize_value(value: Optional[str]) -> str:
    return "" if value is None else str(value).strip()


def is_indexed(row: Dict[str, str]) -> int:
    coverage = normalize_value(row.get("coverage"))
    verdict = normalize_value(row.get("verdict"))

    if coverage in INDEXED_COVERAGE_VALUES:
        return 1

    if verdict == "PASS" and "indexed" in coverage.lower() and "not indexed" not in coverage.lower():
        return 1

    return 0


def read_csv_rows(csv_path: Path) -> List[Dict[str, str]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise ValueError("CSV has no header row.")

        missing = [col for col in EXPECTED_COLUMNS if col not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV is missing expected columns: {', '.join(missing)}")

        rows = []
        for raw in reader:
            row = {col: normalize_value(raw.get(col)) for col in EXPECTED_COLUMNS}
            if row["url"]:
                rows.append(row)

    if not rows:
        raise ValueError("CSV contains no URL rows.")

    return rows


def row_signature(row: Dict[str, str]) -> Dict[str, str]:
    return {col: normalize_value(row.get(col)) for col in EXPECTED_COLUMNS}


def snapshot_hash(rows: Iterable[Dict[str, str]]) -> str:
    canonical_rows = sorted(
        (row_signature(row) for row in rows),
        key=lambda item: item.get("url", ""),
    )
    payload = json.dumps(canonical_rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def connect_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def initialize_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_time TEXT NOT NULL,
            source_csv TEXT NOT NULL,
            source_csv_mtime TEXT,
            total_urls INTEGER NOT NULL,
            indexed_count INTEGER NOT NULL,
            not_indexed_count INTEGER NOT NULL,
            changed_since_previous INTEGER NOT NULL,
            snapshot_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS url_inspections (
            inspection_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            verdict TEXT,
            coverage TEXT,
            is_indexed INTEGER NOT NULL,
            last_crawl TEXT,
            user_canonical TEXT,
            google_canonical TEXT,
            robots TEXT,
            fetch TEXT,
            indexing TEXT,
            crawled_as TEXT,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_runs_run_time
            ON runs(run_time);

        CREATE INDEX IF NOT EXISTS idx_runs_snapshot_hash
            ON runs(snapshot_hash);

        CREATE INDEX IF NOT EXISTS idx_url_inspections_url
            ON url_inspections(url);

        CREATE INDEX IF NOT EXISTS idx_url_inspections_run_id
            ON url_inspections(run_id);

        CREATE INDEX IF NOT EXISTS idx_url_inspections_status
            ON url_inspections(is_indexed, coverage);
        """
    )

    conn.commit()


def previous_snapshot_hash(conn: sqlite3.Connection) -> Optional[str]:
    row = conn.execute(
        "SELECT snapshot_hash FROM runs ORDER BY run_id DESC LIMIT 1"
    ).fetchone()

    return None if row is None else row["snapshot_hash"]


def import_snapshot(
    conn: sqlite3.Connection,
    csv_path: Path,
    rows: List[Dict[str, str]],
    run_time: str,
) -> int:
    total_urls = len(rows)
    indexed_count = sum(is_indexed(row) for row in rows)
    not_indexed_count = total_urls - indexed_count

    sig = snapshot_hash(rows)
    previous_sig = previous_snapshot_hash(conn)
    changed = 1 if previous_sig != sig else 0

    try:
        mtime = datetime.fromtimestamp(csv_path.stat().st_mtime, timezone.utc).replace(
            microsecond=0
        )
        source_csv_mtime = mtime.isoformat().replace("+00:00", "Z")
    except OSError:
        source_csv_mtime = None

    with conn:
        cur = conn.execute(
            """
            INSERT INTO runs (
                run_time,
                source_csv,
                source_csv_mtime,
                total_urls,
                indexed_count,
                not_indexed_count,
                changed_since_previous,
                snapshot_hash,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_time,
                str(csv_path),
                source_csv_mtime,
                total_urls,
                indexed_count,
                not_indexed_count,
                changed,
                sig,
                utc_now_iso(),
            ),
        )

        run_id = int(cur.lastrowid)

        conn.executemany(
            """
            INSERT INTO url_inspections (
                run_id,
                url,
                verdict,
                coverage,
                is_indexed,
                last_crawl,
                user_canonical,
                google_canonical,
                robots,
                fetch,
                indexing,
                crawled_as
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    row["url"],
                    row["verdict"],
                    row["coverage"],
                    is_indexed(row),
                    row["last_crawl"],
                    row["user_canonical"],
                    row["google_canonical"],
                    row["robots"],
                    row["fetch"],
                    row["indexing"],
                    row["crawled_as"],
                )
                for row in rows
            ],
        )

    return run_id


def summarize_run(
    conn: sqlite3.Connection,
    run_id: int,
) -> Tuple[sqlite3.Row, List[sqlite3.Row]]:
    run = conn.execute(
        "SELECT * FROM runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()

    previous = conn.execute(
        "SELECT run_id FROM runs WHERE run_id < ? ORDER BY run_id DESC LIMIT 1",
        (run_id,),
    ).fetchone()

    changes: List[sqlite3.Row] = []

    if previous is not None:
        changes = conn.execute(
            """
            SELECT
                current.url,
                previous.coverage AS previous_coverage,
                current.coverage AS current_coverage,
                previous.is_indexed AS previous_is_indexed,
                current.is_indexed AS current_is_indexed,
                previous.last_crawl AS previous_last_crawl,
                current.last_crawl AS current_last_crawl
            FROM url_inspections current
            LEFT JOIN url_inspections previous
                ON previous.url = current.url
               AND previous.run_id = ?
            WHERE current.run_id = ?
              AND (
                    previous.url IS NULL
                 OR previous.coverage IS NOT current.coverage
                 OR previous.is_indexed IS NOT current.is_indexed
                 OR previous.last_crawl IS NOT current.last_crawl
              )
            ORDER BY current.url
            """,
            (previous["run_id"], run_id),
        ).fetchall()

    return run, changes


def archive(
    csv_file: str | Path,
    db_file: str | Path = "inspection_history.db",
    run_time: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Archive one inspection CSV into SQLite.

    Returns a summary dictionary suitable for spider.py.
    """

    if run_time is None:
        run_time = utc_now_iso()

    csv_path = Path(csv_file).expanduser().resolve()
    db_path = Path(db_file).expanduser().resolve()

    rows = read_csv_rows(csv_path)

    conn = connect_db(db_path)
    try:
        initialize_schema(conn)
        run_id = import_snapshot(conn, csv_path, rows, run_time)
        run, changes = summarize_run(conn, run_id)
    finally:
        conn.close()

    return {
        "run_id": run_id,
        "database": str(db_path),
        "source_csv": str(csv_path),
        "run_time": run["run_time"],
        "total_urls": run["total_urls"],
        "indexed": run["indexed_count"],
        "not_indexed": run["not_indexed_count"],
        "changed": bool(run["changed_since_previous"]),
        "changes": changes,
    }



# ---------------------------------------------------------------------------
# Read API
# ---------------------------------------------------------------------------

def latest_run(db_file: str | Path) -> Optional[Dict[str, Any]]:
    """
    Return the most recent run row as a plain dictionary.

    This is intended for reporting tools such as dashboard.py.
    """
    db_path = Path(db_file).expanduser().resolve()

    if not db_path.exists():
        return None

    conn = connect_db(db_path)
    try:
        initialize_schema(conn)

        row = conn.execute(
            """
            SELECT *
            FROM runs
            ORDER BY run_id DESC
            LIMIT 1
            """
        ).fetchone()

        if row is None:
            return None

        return dict(row)
    finally:
        conn.close()


def inspections_for_run(
    db_file: str | Path,
    run_id: int,
) -> List[Dict[str, Any]]:
    """
    Return inspection rows for a specific run as plain dictionaries.
    """
    db_path = Path(db_file).expanduser().resolve()

    if not db_path.exists():
        return []

    conn = connect_db(db_path)
    try:
        initialize_schema(conn)

        rows = conn.execute(
            """
            SELECT
                url,
                verdict,
                coverage,
                is_indexed,
                last_crawl,
                user_canonical,
                google_canonical,
                robots,
                fetch,
                indexing,
                crawled_as
            FROM url_inspections
            WHERE run_id = ?
            ORDER BY url
            """,
            (run_id,),
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


def latest_inspections(db_file: str | Path) -> List[Dict[str, Any]]:
    """
    Return inspection rows for the most recent run as plain dictionaries.
    """
    run = latest_run(db_file)

    if run is None:
        return []

    return inspections_for_run(db_file, int(run["run_id"]))


def changes_for_run(
    db_file: str | Path,
    run_id: int,
) -> List[Dict[str, Any]]:
    """
    Return changes for a specific run compared with the previous run.

    A row is considered changed when coverage, indexed state, or last crawl
    differs from the previous run, or when the URL is new in this run.
    """
    db_path = Path(db_file).expanduser().resolve()

    if not db_path.exists():
        return []

    conn = connect_db(db_path)
    try:
        initialize_schema(conn)
        _run, changes = summarize_run(conn, run_id)
        return [dict(row) for row in changes]
    finally:
        conn.close()


def latest_changes(db_file: str | Path) -> List[Dict[str, Any]]:
    """
    Return changes for the most recent run compared with the previous run.
    """
    run = latest_run(db_file)

    if run is None:
        return []

    return changes_for_run(db_file, int(run["run_id"]))


def latest_archive_summary(db_file: str | Path) -> Dict[str, Any]:
    """
    Return a summary dictionary for the most recent run.

    This mirrors the structure returned by archive(...), but reads from the
    database instead of importing a new CSV snapshot.
    """
    run = latest_run(db_file)

    if run is None:
        return {
            "run_id": None,
            "database": str(Path(db_file).expanduser().resolve()),
            "source_csv": "",
            "run_time": "",
            "total_urls": 0,
            "indexed": 0,
            "not_indexed": 0,
            "changed": False,
            "changes": [],
        }

    changes = latest_changes(db_file)

    return {
        "run_id": run["run_id"],
        "database": str(Path(db_file).expanduser().resolve()),
        "source_csv": run.get("source_csv", ""),
        "run_time": run.get("run_time", ""),
        "total_urls": run.get("total_urls", 0),
        "indexed": run.get("indexed_count", 0),
        "not_indexed": run.get("not_indexed_count", 0),
        "changed": bool(run.get("changed_since_previous", 0)),
        "changes": changes,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archive URL Inspection CSV results into SQLite."
    )

    parser.add_argument(
        "csv",
        help="Path to inspection CSV file.",
    )

    parser.add_argument(
        "--db",
        default="inspection_history.db",
        help="SQLite database path. Default: inspection_history.db",
    )

    parser.add_argument(
        "--run-time",
        default=None,
        help="Run timestamp, ISO format. Default: current UTC time.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        summary = archive(
            csv_file=args.csv,
            db_file=args.db,
            run_time=args.run_time,
        )
    except Exception as exc:
        print(f"Archive failed: {exc}", file=sys.stderr)
        return 1

    print(f"Archived run #{summary['run_id']}")
    print(f"Database: {summary['database']}")
    print(f"Source CSV: {summary['source_csv']}")
    print(f"Run time: {summary['run_time']}")
    print(f"URLs: {summary['total_urls']}")
    print(f"Indexed: {summary['indexed']}")
    print(f"Not indexed: {summary['not_indexed']}")
    print(f"Changed since previous: {'yes' if summary['changed'] else 'no'}")

    changes = summary["changes"]

    if changes:
        print()
        print("Changed URLs since previous run:")

        for row in changes[:25]:
            previous = row["previous_coverage"] or "new URL"
            current = row["current_coverage"] or ""
            print(f"- {row['url']}: {previous} -> {current}")

        if len(changes) > 25:
            print(f"...and {len(changes) - 25} more")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
