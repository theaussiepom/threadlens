#!/usr/bin/env python3
"""Read-only SQLite event summary for Pass 28 mDNS flapping diagnostics."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def main() -> int:
    db_path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/study/threadlens.db")
    out_path = Path(
        sys.argv[2] if len(sys.argv) > 2 else "live-captures/pass28-mdns-flap/event-summary.txt"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    def q(title: str, sql: str) -> None:
        print(f"\n=== {title} ===")
        cur.execute(sql)
        rows = cur.fetchall()
        if not rows:
            print("(no rows)")
            return
        cols = rows[0].keys()
        print(" | ".join(cols))
        print("-" * 80)
        for row in rows:
            print(" | ".join(str(row[col]) for col in cols))

    queries = [
        (
            "event types 24h",
            """
            SELECT event_type, COUNT(*) AS count
            FROM events
            WHERE timestamp >= datetime('now', '-24 hour')
            GROUP BY event_type
            ORDER BY count DESC
            """,
        ),
        (
            "mdns by type/service_type 24h",
            """
            SELECT event_type,
                   json_extract(data_json, '$.service_type') AS service_type,
                   COUNT(*) AS count
            FROM events
            WHERE timestamp >= datetime('now', '-24 hour')
              AND event_type LIKE 'mdns.%'
            GROUP BY event_type, service_type
            ORDER BY count DESC
            """,
        ),
        (
            "top mdns services 24h",
            """
            SELECT event_type,
                   json_extract(data_json, '$.service_type') AS service_type,
                   json_extract(data_json, '$.service_name') AS service_name,
                   COUNT(*) AS count
            FROM events
            WHERE timestamp >= datetime('now', '-24 hour')
              AND event_type LIKE 'mdns.%'
            GROUP BY event_type, service_type, service_name
            ORDER BY count DESC
            LIMIT 50
            """,
        ),
        (
            "mdns with initial_observation 24h",
            """
            SELECT event_type,
                   json_extract(data_json, '$.service_type') AS service_type,
                   json_extract(data_json, '$.service_name') AS service_name,
                   json_extract(data_json, '$.initial_observation') AS initial_observation,
                   COUNT(*) AS count
            FROM events
            WHERE timestamp >= datetime('now', '-24 hour')
              AND event_type LIKE 'mdns.%'
            GROUP BY event_type, service_type, service_name, initial_observation
            ORDER BY count DESC
            LIMIT 80
            """,
        ),
        (
            "trel by type 24h",
            """
            SELECT event_type,
                   json_extract(data_json, '$.service_type') AS service_type,
                   COUNT(*) AS count
            FROM events
            WHERE timestamp >= datetime('now', '-24 hour')
              AND event_type LIKE 'trel.%'
            GROUP BY event_type, service_type
            ORDER BY count DESC
            """,
        ),
        (
            "flap-countable events last 1h (non-initial)",
            """
            SELECT event_type, COUNT(*) AS count
            FROM events
            WHERE timestamp >= datetime('now', '-1 hour')
              AND event_type IN (
                'mdns.service_added',
                'mdns.service_removed',
                'mdns.service_changed',
                'trel.service_added',
                'trel.service_removed',
                'trel.service_changed'
              )
              AND (
                json_extract(data_json, '$.initial_observation') IS NULL
                OR json_extract(data_json, '$.initial_observation') != 1
              )
            GROUP BY event_type
            ORDER BY count DESC
            """,
        ),
        (
            "total flap-countable non-initial last 1h",
            """
            SELECT COUNT(*) AS count
            FROM events
            WHERE timestamp >= datetime('now', '-1 hour')
              AND event_type IN (
                'mdns.service_added',
                'mdns.service_removed',
                'mdns.service_changed',
                'trel.service_added',
                'trel.service_removed',
                'trel.service_changed'
              )
              AND (
                json_extract(data_json, '$.initial_observation') IS NULL
                OR json_extract(data_json, '$.initial_observation') != 1
              )
            """,
        ),
        (
            "mdns flap events last 1h non-initial by service",
            """
            SELECT event_type,
                   json_extract(data_json, '$.service_type') AS service_type,
                   json_extract(data_json, '$.service_name') AS service_name,
                   COUNT(*) AS count
            FROM events
            WHERE timestamp >= datetime('now', '-1 hour')
              AND event_type IN (
                'mdns.service_added',
                'mdns.service_removed',
                'mdns.service_changed'
              )
              AND (
                json_extract(data_json, '$.initial_observation') IS NULL
                OR json_extract(data_json, '$.initial_observation') != 1
              )
            GROUP BY event_type, service_type, service_name
            ORDER BY count DESC
            LIMIT 30
            """,
        ),
    ]

    import io

    buffer = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buffer
    try:
        for title, sql in queries:
            q(title, sql)
    finally:
        sys.stdout = old_stdout

    out_path.write_text(buffer.getvalue(), encoding="utf-8")
    print(buffer.getvalue())
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
