#!/usr/bin/env python3
"""
backfill_referent_time — populate the event-clock column from existing
node metadata / source_file hints.

Background
----------
Cashew's `timestamp` column is the ingestion clock. `referent_time` (added
alongside this script) is the event clock — when the fact/event actually
happened. New writes populate it explicitly; this script walks existing
nodes and tries to recover an event time from what we have on disk.

Rules
-----
- Operate via the cashew CLI envelope where possible; this script accesses
  the DB directly (single-writer backfill utility, same pattern as
  scripts/declassify.py).
- Only UPDATE rows where referent_time IS NULL.
- Never default NULL to timestamp. Unrecoverable rows stay NULL.
- Only accept tz-aware ISO8601 — refuse to guess local tz (fail loud).
- Dry-run by default. Requires --apply to actually write.

Sources scanned
---------------
- metadata JSON fields: event_time, referent_time, occurred_at,
  happened_at, original_timestamp
- source_file YYYY-MM-DD / YYYY/MM/DD prefix patterns (WhatsApp-style
  archive filenames, Obsidian daily note names).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Optional, Tuple

# Resolve repo root so we can import the normalizer.
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from core.session import _normalize_referent_time  # noqa: E402
from core import db as cdb  # noqa: E402


METADATA_KEYS = (
    "event_time",
    "referent_time",
    "occurred_at",
    "happened_at",
    "original_timestamp",
    "source_time",
)

# YYYY-MM-DD or YYYY/MM/DD appearing anywhere in source_file.
_DATE_RE = re.compile(r"(\d{4})[-/](\d{2})[-/](\d{2})")


def _resolve_db_path(cli_arg: Optional[str]) -> str:
    """Respect CASHEW_DB_PATH / CASHEW_CONFIG_PATH overrides.

    Delegates to core.db.resolve_db_path so precedence rules stay in one
    place (CLI arg > CASHEW_DB_PATH > configured path).
    """
    try:
        return cdb.resolve_db_path(cli_arg)
    except Exception:
        # Fall back to repo-local default if config isn't loadable (test envs).
        if cli_arg:
            return cli_arg
        env = os.environ.get("CASHEW_DB_PATH")
        if env:
            return env
        default = _REPO / "data" / "graph.db"
        return str(default)


def _try_metadata(metadata_raw: Optional[str]) -> Optional[str]:
    if not metadata_raw:
        return None
    try:
        meta = json.loads(metadata_raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(meta, dict):
        return None
    for key in METADATA_KEYS:
        val = meta.get(key)
        if not val or not isinstance(val, str):
            continue
        try:
            return _normalize_referent_time(val)
        except ValueError:
            continue
    return None


def _try_source_file(source_file: Optional[str]) -> Optional[str]:
    if not source_file:
        return None
    m = _DATE_RE.search(source_file)
    if not m:
        return None
    y, mo, d = (int(p) for p in m.groups())
    try:
        dt = datetime(y, mo, d, tzinfo=timezone.utc)
    except ValueError:
        return None
    return dt.isoformat()


def _recover(metadata_raw: Optional[str], source_file: Optional[str]) -> Tuple[Optional[str], str]:
    """Return (iso_or_none, reason)."""
    got = _try_metadata(metadata_raw)
    if got:
        return got, "metadata"
    got = _try_source_file(source_file)
    if got:
        return got, "source_file_date"
    return None, "none"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=None,
                        help="Database path (overrides CASHEW_DB_PATH)")
    parser.add_argument("--apply", action="store_true",
                        help="Actually write changes (default: dry run)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of rows processed (debugging)")
    args = parser.parse_args()

    db_path = _resolve_db_path(args.db)
    if not os.path.exists(db_path):
        print(f"ERROR: db not found: {db_path}", file=sys.stderr)
        return 1

    conn = cdb.connect(db_path)
    try:
        cols = set(cdb.pragma_columns(conn, cdb.NODES_TABLE))
        if "referent_time" not in cols:
            print("ERROR: referent_time column missing. Run cashew CLI first "
                  "to apply the migration (any call to _ensure_schema).",
                  file=sys.stderr)
            return 2

        cursor = cdb.execute(
            conn,
            f"SELECT id, metadata, source_file FROM {cdb.NODES_TABLE} "
            "WHERE referent_time IS NULL",
        )
        rows = cursor.fetchall()
        if args.limit:
            rows = rows[: args.limit]

        total = len(rows)
        recovered = 0
        by_reason = {"metadata": 0, "source_file_date": 0, "none": 0}
        updates = []

        for node_id, metadata_raw, source_file in rows:
            got, reason = _recover(metadata_raw, source_file)
            by_reason[reason] = by_reason.get(reason, 0) + 1
            if got is not None:
                recovered += 1
                updates.append((got, node_id))

        print(f"Scanned: {total}")
        print(f"Recoverable: {recovered}")
        print(f"  from metadata:         {by_reason['metadata']}")
        print(f"  from source_file date: {by_reason['source_file_date']}")
        print(f"  unrecoverable (left NULL): {by_reason['none']}")

        if not args.apply:
            print("\nDry run only. Re-run with --apply to write.")
            return 0

        write_cursor = cdb.executemany(
            conn,
            f"UPDATE {cdb.NODES_TABLE} SET referent_time = ? "
            "WHERE id = ? AND referent_time IS NULL",
            updates,
        )
        conn.commit()
        print(f"\nWrote referent_time to {write_cursor.rowcount} rows.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
