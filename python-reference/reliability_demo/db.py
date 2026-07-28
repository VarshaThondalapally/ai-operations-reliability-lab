from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("RELIABILITY_DEMO_DB", ROOT / "operations_reliability.db"))


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def tomorrow_at(hour: int, minute: int = 0) -> str:
    return (
        datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        + timedelta(days=1)
    ).isoformat()


SCHEMA = """
CREATE TABLE IF NOT EXISTS agency (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  name TEXT NOT NULL,
  region TEXT NOT NULL,
  coverage_hours TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS integrations (
  key TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  description TEXT NOT NULL,
  online INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS caregivers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  phone TEXT NOT NULL,
  skills_json TEXT NOT NULL,
  zones_json TEXT NOT NULL,
  outreach_consent INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS clients (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  zone TEXT NOT NULL,
  required_skills_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shifts (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(id),
  assigned_caregiver_id TEXT NOT NULL REFERENCES caregivers(id),
  service_type TEXT NOT NULL,
  starts_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'scheduled'
);

CREATE TABLE IF NOT EXISTS reassignments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  shift_id TEXT NOT NULL REFERENCES shifts(id),
  from_caregiver_id TEXT NOT NULL REFERENCES caregivers(id),
  to_caregiver_id TEXT NOT NULL REFERENCES caregivers(id),
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_completed_reassignment
ON reassignments(shift_id, to_caregiver_id)
WHERE status = 'completed';

CREATE TABLE IF NOT EXISTS operation_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  summary TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS handoffs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  queue TEXT NOT NULL,
  reason TEXT NOT NULL,
  summary TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scenario_id TEXT,
  transcript TEXT NOT NULL,
  parser_source TEXT NOT NULL,
  intent_json TEXT NOT NULL,
  outcome_json TEXT NOT NULL,
  events_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


TABLES = [
    "runs",
    "handoffs",
    "operation_logs",
    "reassignments",
    "shifts",
    "clients",
    "caregivers",
    "integrations",
    "agency",
]


INTEGRATIONS = [
    ("workforce", "Caregiver directory", "Identity, skills, service zones, and contact permission."),
    ("scheduler", "Shift scheduler", "Assigned visits, availability, and schedule conflicts."),
    ("care_plan", "Client care plan", "Required service, location, and qualification constraints."),
    ("compliance", "Qualification rules", "Deterministic eligibility checks before reassignment."),
    ("emr", "Mock EMR", "Shift assignment and operational note updates."),
    ("routing", "Operations escalation", "Human ownership when automation must stop."),
]


def init_db(reset: bool = False) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        if reset:
            for table in TABLES:
                conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.commit()
        conn.executescript(SCHEMA)
        count = conn.execute("SELECT COUNT(*) FROM agency").fetchone()[0]
        if count == 0:
            seed(conn)


def seed(conn: sqlite3.Connection) -> None:
    ts = now_iso()
    conn.execute(
        "INSERT INTO agency(id, name, region, coverage_hours) VALUES (1, ?, ?, ?)",
        ("Northstar Home Support", "Central Texas", "24/7 coordination"),
    )
    conn.executemany(
        "INSERT INTO integrations(key, label, description, online, updated_at) VALUES (?, ?, ?, 1, ?)",
        [(key, label, description, ts) for key, label, description in INTEGRATIONS],
    )
    conn.executemany(
        """
        INSERT INTO caregivers(id, name, phone, skills_json, zones_json, outreach_consent)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "cg_maya",
                "Maya Patel",
                "+15125550101",
                json.dumps(["personal_care", "companion"]),
                json.dumps(["central", "north"]),
                1,
            ),
            (
                "cg_devon",
                "Devon Brooks",
                "+15125550102",
                json.dumps(["personal_care", "companion", "medication_reminder"]),
                json.dumps(["central", "north"]),
                1,
            ),
            (
                "cg_jordan",
                "Jordan Lee",
                "+15125550103",
                json.dumps(["companion"]),
                json.dumps(["central"]),
                1,
            ),
            (
                "cg_priya",
                "Priya Shah",
                "+15125550104",
                json.dumps(["personal_care", "medication_reminder"]),
                json.dumps(["central"]),
                0,
            ),
        ],
    )
    conn.executemany(
        "INSERT INTO clients(id, name, zone, required_skills_json) VALUES (?, ?, ?, ?)",
        [
            (
                "client_eleanor",
                "Eleanor Price",
                "central",
                json.dumps(["personal_care"]),
            ),
            (
                "client_robert",
                "Robert Chen",
                "central",
                json.dumps(["medication_reminder"]),
            ),
        ],
    )
    conn.executemany(
        """
        INSERT INTO shifts(id, client_id, assigned_caregiver_id, service_type, starts_at, status)
        VALUES (?, ?, ?, ?, ?, 'scheduled')
        """,
        [
            (
                "shift_eleanor_1400",
                "client_eleanor",
                "cg_maya",
                "personal_care",
                tomorrow_at(14),
            ),
            (
                "shift_eleanor_1800",
                "client_eleanor",
                "cg_maya",
                "companion",
                tomorrow_at(18),
            ),
            (
                "shift_robert_1000",
                "client_robert",
                "cg_maya",
                "medication_reminder",
                tomorrow_at(10),
            ),
            (
                "shift_devon_conflict",
                "client_eleanor",
                "cg_devon",
                "companion",
                tomorrow_at(10),
            ),
            (
                "shift_duplicate_1600",
                "client_eleanor",
                "cg_devon",
                "personal_care",
                tomorrow_at(16),
            ),
        ],
    )
    conn.execute(
        """
        INSERT INTO reassignments(
          shift_id, from_caregiver_id, to_caregiver_id, status, created_at
        ) VALUES (?, ?, ?, 'completed', ?)
        """,
        ("shift_duplicate_1600", "cg_maya", "cg_devon", ts),
    )
    conn.commit()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def agency() -> dict[str, Any]:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM agency WHERE id = 1").fetchone()
        return dict(row)


def list_integrations() -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM integrations ORDER BY rowid").fetchall()
        return [dict(row) for row in rows]


def set_integration(key: str, online: bool) -> dict[str, Any]:
    init_db()
    with connect() as conn:
        conn.execute(
            "UPDATE integrations SET online = ?, updated_at = ? WHERE key = ?",
            (1 if online else 0, now_iso(), key),
        )
        row = conn.execute("SELECT * FROM integrations WHERE key = ?", (key,)).fetchone()
        conn.commit()
        return dict(row)


def integration_online(conn: sqlite3.Connection, key: str) -> bool:
    row = conn.execute("SELECT online FROM integrations WHERE key = ?", (key,)).fetchone()
    return bool(row and row["online"])


def find_caregiver(conn: sqlite3.Connection, name_hint: str | None) -> dict[str, Any] | None:
    if not name_hint:
        return None
    row = conn.execute(
        "SELECT * FROM caregivers WHERE lower(name) LIKE ? LIMIT 1",
        (f"%{name_hint.lower()}%",),
    ).fetchone()
    if not row:
        return None
    caregiver = dict(row)
    caregiver["skills"] = json.loads(caregiver.pop("skills_json"))
    caregiver["zones"] = json.loads(caregiver.pop("zones_json"))
    caregiver["outreach_consent"] = bool(caregiver["outreach_consent"])
    return caregiver


def find_client(conn: sqlite3.Connection, name_hint: str | None) -> dict[str, Any] | None:
    if not name_hint:
        return None
    row = conn.execute(
        "SELECT * FROM clients WHERE lower(name) LIKE ? LIMIT 1",
        (f"%{name_hint.lower()}%",),
    ).fetchone()
    if not row:
        return None
    client = dict(row)
    client["required_skills"] = json.loads(client.pop("required_skills_json"))
    return client


def shifts_for_original(
    conn: sqlite3.Connection,
    caregiver_id: str,
    client_id: str | None = None,
) -> list[dict[str, Any]]:
    query = """
        SELECT shifts.*, clients.name AS client_name, clients.zone AS client_zone
        FROM shifts
        JOIN clients ON clients.id = shifts.client_id
        WHERE shifts.assigned_caregiver_id = ?
          AND shifts.status = 'scheduled'
    """
    params: list[Any] = [caregiver_id]
    if client_id:
        query += " AND shifts.client_id = ?"
        params.append(client_id)
    query += " ORDER BY shifts.starts_at"
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def find_shift(
    conn: sqlite3.Connection,
    original_caregiver_id: str,
    client_id: str,
    starts_at: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT shifts.*, clients.name AS client_name, clients.zone AS client_zone,
               clients.required_skills_json
        FROM shifts
        JOIN clients ON clients.id = shifts.client_id
        WHERE shifts.assigned_caregiver_id = ?
          AND shifts.client_id = ?
          AND shifts.starts_at = ?
          AND shifts.status = 'scheduled'
        LIMIT 1
        """,
        (original_caregiver_id, client_id, starts_at),
    ).fetchone()
    if not row:
        return None
    shift = dict(row)
    shift["required_skills"] = json.loads(shift.pop("required_skills_json"))
    return shift


def find_shift_by_client_time(
    conn: sqlite3.Connection,
    client_id: str,
    starts_at: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT shifts.*, clients.name AS client_name, clients.zone AS client_zone,
               clients.required_skills_json
        FROM shifts
        JOIN clients ON clients.id = shifts.client_id
        WHERE shifts.client_id = ?
          AND shifts.starts_at = ?
        LIMIT 1
        """,
        (client_id, starts_at),
    ).fetchone()
    if not row:
        return None
    shift = dict(row)
    shift["required_skills"] = json.loads(shift.pop("required_skills_json"))
    return shift


def caregiver_has_conflict(
    conn: sqlite3.Connection,
    caregiver_id: str,
    starts_at: str,
    exclude_shift_id: str | None = None,
) -> bool:
    query = """
        SELECT COUNT(*) AS count
        FROM shifts
        WHERE assigned_caregiver_id = ?
          AND starts_at = ?
          AND status = 'scheduled'
    """
    params: list[Any] = [caregiver_id, starts_at]
    if exclude_shift_id:
        query += " AND id != ?"
        params.append(exclude_shift_id)
    return conn.execute(query, params).fetchone()["count"] > 0


def completed_reassignment(
    conn: sqlite3.Connection,
    shift_id: str,
    replacement_id: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM reassignments
        WHERE shift_id = ? AND to_caregiver_id = ? AND status = 'completed'
        LIMIT 1
        """,
        (shift_id, replacement_id),
    ).fetchone()
    return row_to_dict(row)


def apply_reassignment(
    conn: sqlite3.Connection,
    shift: dict[str, Any],
    replacement: dict[str, Any],
) -> dict[str, Any]:
    existing = completed_reassignment(conn, shift["id"], replacement["id"])
    if existing:
        return existing
    conn.execute(
        """
        INSERT INTO reassignments(
          shift_id, from_caregiver_id, to_caregiver_id, status, created_at
        ) VALUES (?, ?, ?, 'completed', ?)
        """,
        (
            shift["id"],
            shift["assigned_caregiver_id"],
            replacement["id"],
            now_iso(),
        ),
    )
    conn.execute(
        "UPDATE shifts SET assigned_caregiver_id = ? WHERE id = ?",
        (replacement["id"], shift["id"]),
    )
    return completed_reassignment(conn, shift["id"], replacement["id"]) or {}


def create_operation_log(
    conn: sqlite3.Connection,
    kind: str,
    summary: str,
    payload: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO operation_logs(kind, summary, payload_json, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (kind, summary, json.dumps(payload), now_iso()),
    )


def create_handoff(
    conn: sqlite3.Connection,
    queue: str,
    reason: str,
    summary: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    cursor = conn.execute(
        """
        INSERT INTO handoffs(queue, reason, summary, payload_json, status, created_at)
        VALUES (?, ?, ?, ?, 'open', ?)
        """,
        (queue, reason, summary, json.dumps(payload), now_iso()),
    )
    row = conn.execute("SELECT * FROM handoffs WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def recent_handoffs(limit: int = 10) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM handoffs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def recent_runs(limit: int = 10) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def save_run(
    conn: sqlite3.Connection,
    scenario_id: str | None,
    transcript: str,
    parser_source: str,
    intent: dict[str, Any],
    outcome: dict[str, Any],
    events: list[dict[str, Any]],
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO runs(
          scenario_id, transcript, parser_source, intent_json,
          outcome_json, events_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            scenario_id,
            transcript,
            parser_source,
            json.dumps(intent),
            json.dumps(outcome),
            json.dumps(events),
            now_iso(),
        ),
    )
    return int(cursor.lastrowid)


def counts(conn: sqlite3.Connection | None = None) -> dict[str, int]:
    if conn is not None:
        return {
            "reassignments": conn.execute("SELECT COUNT(*) FROM reassignments").fetchone()[0],
            "handoffs": conn.execute("SELECT COUNT(*) FROM handoffs").fetchone()[0],
            "logs": conn.execute("SELECT COUNT(*) FROM operation_logs").fetchone()[0],
        }
    init_db()
    with connect() as owned:
        return counts(owned)
