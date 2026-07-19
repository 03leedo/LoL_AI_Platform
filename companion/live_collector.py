"""LoL AI Platform companion C1 — Live Client collector (Phase 9).

Collection-only: polls the local Live Client Data API during YOUR OWN games,
buffers compact snapshots in a local SQLite queue, and uploads them to your
backend AFTER the game ends. Nothing is ever displayed or advised in-game.

Requirements: Python 3.10+ (standard library only).

Usage (run on the PC where League is played):

    python live_collector.py --riot-id "게임이름#태그"
    # options: --backend http://localhost:8000  --interval 1.0  --db live_buffer.sqlite

Stop with Ctrl+C. Unuploaded games are kept in the SQLite buffer and are
uploaded automatically the next time the collector starts (idempotent: the
server ignores duplicate snapshot sequence numbers).
"""

import argparse
import json
import sqlite3
import ssl
import sys
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

COLLECTOR_VERSION = "c1-0.1.0"
LIVE_CLIENT_URL = "https://127.0.0.1:2999/liveclientdata/allgamedata"
UPLOAD_BATCH_SIZE = 500
UPLOAD_MAX_ATTEMPTS = 5

# The game client uses a self-signed certificate on 127.0.0.1.
_SSL_CONTEXT = ssl.create_default_context()
_SSL_CONTEXT.check_hostname = False
_SSL_CONTEXT.verify_mode = ssl.CERT_NONE

ACTIVE_STAT_KEYS = (
    "currentHealth",
    "maxHealth",
    "resourceValue",
    "resourceMax",
    "attackDamage",
    "abilityPower",
    "armor",
    "magicResist",
    "moveSpeed",
)


def compact_snapshot(
    data: dict[str, Any],
    seen_event_ids: set[int],
) -> tuple[dict[str, Any], list[int]]:
    """Reduce allgamedata to the C1 scope: my health/gold/stats + new events.

    Returns (payload, new_event_ids). Pure function — unit-tested.
    """
    active = data.get("activePlayer") or {}
    stats = active.get("championStats") or {}
    events_root = (data.get("events") or {}).get("Events") or []
    new_events = []
    new_ids: list[int] = []
    for event in events_root:
        event_id = event.get("EventID")
        if isinstance(event_id, int) and event_id not in seen_event_ids:
            new_events.append(event)
            new_ids.append(event_id)

    payload = {
        "game_time_s": float((data.get("gameData") or {}).get("gameTime") or 0.0),
        "active": {
            "riot_id": active.get("riotId") or active.get("summonerName"),
            "level": active.get("level"),
            "current_gold": active.get("currentGold"),
            "stats": {key: stats.get(key) for key in ACTIVE_STAT_KEYS},
        },
        "events": new_events,
    }
    return payload, new_ids


def estimate_game_start_ms(game_time_s: float, now_ms: int) -> int:
    """Wall-clock game start inferred from in-game time (collector may join late)."""
    return int(now_ms - game_time_s * 1000)


# --- local buffer -----------------------------------------------------------


def open_buffer(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sessions ("
        " session_id TEXT PRIMARY KEY, riot_id TEXT NOT NULL,"
        " game_start_ms INTEGER, state TEXT NOT NULL DEFAULT 'collecting',"
        " created_at INTEGER NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS snapshots ("
        " session_id TEXT NOT NULL, seq INTEGER NOT NULL,"
        " game_time_s REAL NOT NULL, payload TEXT,"
        " PRIMARY KEY (session_id, seq))"
    )
    conn.commit()
    return conn


def buffer_snapshot(
    conn: sqlite3.Connection,
    session_id: str,
    seq: int,
    payload: dict[str, Any],
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO snapshots (session_id, seq, game_time_s, payload)"
        " VALUES (?, ?, ?, ?)",
        (session_id, seq, payload["game_time_s"], json.dumps(payload, ensure_ascii=False)),
    )
    conn.commit()


# --- live client + backend I/O ----------------------------------------------


def poll_live_client(timeout: float = 2.0) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(LIVE_CLIENT_URL, timeout=timeout, context=_SSL_CONTEXT) as res:
            return json.loads(res.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, ValueError):
        return None


def post_json(url: str, body: dict[str, Any], timeout: float = 15.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def upload_session(conn: sqlite3.Connection, backend: str, session_id: str) -> bool:
    """Upload one buffered session; returns True when fully acknowledged."""
    row = conn.execute(
        "SELECT riot_id, game_start_ms FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    if row is None:
        return False
    riot_id, game_start_ms = row
    base = f"{backend.rstrip('/')}/api/v1/live/sessions/{session_id}"

    rows = conn.execute(
        "SELECT seq, game_time_s, payload FROM snapshots WHERE session_id = ? ORDER BY seq",
        (session_id,),
    ).fetchall()
    for start in range(0, len(rows), UPLOAD_BATCH_SIZE):
        batch = rows[start : start + UPLOAD_BATCH_SIZE]
        body = {
            "riot_id": riot_id,
            "collector_version": COLLECTOR_VERSION,
            "snapshots": [
                {"seq": seq, "game_time_s": gt, "payload": json.loads(payload) if payload else None}
                for seq, gt, payload in batch
            ],
        }
        for attempt in range(1, UPLOAD_MAX_ATTEMPTS + 1):
            try:
                post_json(f"{base}/snapshots", body)
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == UPLOAD_MAX_ATTEMPTS:
                    print(f"[upload] giving up for now ({exc}) — buffered locally", flush=True)
                    return False
                time.sleep(min(30, 2**attempt))

    try:
        result = post_json(
            f"{base}/complete",
            {"riot_id": riot_id, "game_start_ms": game_start_ms, "collector_version": COLLECTOR_VERSION},
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[upload] complete failed ({exc}) — will retry on next start", flush=True)
        return False

    conn.execute("UPDATE sessions SET state = 'uploaded' WHERE session_id = ?", (session_id,))
    conn.commit()
    print(
        f"[upload] session {session_id[:8]}… uploaded"
        f" (state={result.get('state')}, match={result.get('matched_match_id')})",
        flush=True,
    )
    return True


def upload_pending(conn: sqlite3.Connection, backend: str) -> None:
    pending = conn.execute(
        "SELECT session_id FROM sessions WHERE state != 'uploaded'"
    ).fetchall()
    for (session_id,) in pending:
        upload_session(conn, backend, session_id)


# --- main loop ---------------------------------------------------------------


def run(riot_id: str, backend: str, interval: float, db_path: str) -> None:
    conn = open_buffer(db_path)
    print(f"[collector] {COLLECTOR_VERSION} — riot_id={riot_id}, backend={backend}", flush=True)
    print("[collector] collection-only: nothing is shown in-game.", flush=True)
    upload_pending(conn, backend)

    session_id: str | None = None
    seq = 0
    seen_event_ids: set[int] = set()

    while True:
        data = poll_live_client()
        if data is not None:
            if session_id is None:
                session_id = str(uuid.uuid4())
                seq = 0
                seen_event_ids = set()
                payload, _ = compact_snapshot(data, set())
                start_ms = estimate_game_start_ms(payload["game_time_s"], int(time.time() * 1000))
                conn.execute(
                    "INSERT INTO sessions (session_id, riot_id, game_start_ms, state, created_at)"
                    " VALUES (?, ?, ?, 'collecting', ?)",
                    (session_id, riot_id, start_ms, int(time.time())),
                )
                conn.commit()
                print(f"[collector] game detected → session {session_id[:8]}…", flush=True)
            payload, new_ids = compact_snapshot(data, seen_event_ids)
            seen_event_ids.update(new_ids)
            buffer_snapshot(conn, session_id, seq, payload)
            seq += 1
        elif session_id is not None:
            print(f"[collector] game ended → uploading {seq} snapshots", flush=True)
            conn.execute(
                "UPDATE sessions SET state = 'pending_upload' WHERE session_id = ?", (session_id,)
            )
            conn.commit()
            upload_session(conn, backend, session_id)
            session_id = None
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--riot-id", required=True, help='본인 라이엇 ID, 예: "게임이름#KR1"')
    parser.add_argument("--backend", default="http://localhost:8000")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--db", default="live_buffer.sqlite")
    args = parser.parse_args()

    if "#" not in args.riot_id:
        print('riot id must look like "게임이름#태그"', file=sys.stderr)
        raise SystemExit(2)
    try:
        run(args.riot_id, args.backend, max(0.25, args.interval), args.db)
    except KeyboardInterrupt:
        print("\n[collector] stopped. Unuploaded games stay buffered locally.", flush=True)


if __name__ == "__main__":
    main()
