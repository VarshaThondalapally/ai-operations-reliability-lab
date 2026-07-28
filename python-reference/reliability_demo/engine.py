from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any

from . import ai, db


MOCK_ADAPTER_SYSTEMS = {
    "workforce",
    "scheduler",
    "care_plan",
    "compliance",
    "emr",
    "routing",
}
MIN_WRITE_CONFIDENCE = 0.65


STEPS = [
    {
        "id": "request",
        "title": "Request received",
        "description": "Raw operations language is preserved.",
        "why": "The original request remains available for audit and human review.",
    },
    {
        "id": "ai",
        "title": "Intent structured",
        "description": "Language becomes typed operational intent.",
        "why": "Parsing is separated from permission to change a schedule.",
    },
    {
        "id": "route",
        "title": "Workflow routed",
        "description": "The backend selects the required checks.",
        "why": "Call-outs, reassignments, and questions require different evidence.",
    },
    {
        "id": "checks",
        "title": "Systems checked",
        "description": "Mock workforce, schedule, care-plan, compliance, and EMR data are verified.",
        "why": "A plausible language-model output is not operational truth.",
    },
    {
        "id": "gate",
        "title": "Decision gate",
        "description": "The system completes, clarifies, blocks, or escalates.",
        "why": "Every write requires identity, shift, eligibility, availability, and acceptance.",
    },
    {
        "id": "final",
        "title": "Action + visibility",
        "description": "The shift is updated or an owned handoff is created.",
        "why": "Operations teams need a recoverable outcome and an explanation.",
    },
]


SCENARIOS = {
    "coverage": {
        "title": "Shift covered safely",
        "subtitle": "Verified reassignment",
        "transcript": (
            "Maya called out of Eleanor's personal-care visit tomorrow at 2 PM. "
            "Devon accepted the replacement."
        ),
    },
    "ambiguous": {
        "title": "Ambiguous call-out",
        "subtitle": "Clarify instead of guessing",
        "transcript": "Maya called out tomorrow.",
    },
    "outage": {
        "title": "Scheduler outage",
        "subtitle": "Dependency failure becomes handoff",
        "transcript": (
            "Maya called out of Eleanor's personal-care visit tomorrow at 2 PM. "
            "Devon accepted the replacement."
        ),
        "force_offline": "scheduler",
    },
    "qualification": {
        "title": "Qualification mismatch",
        "subtitle": "Unsafe replacement is blocked",
        "transcript": (
            "Maya called out of Robert's medication-reminder visit tomorrow at 10 AM. "
            "Jordan accepted the replacement."
        ),
    },
    "conflict": {
        "title": "Schedule conflict",
        "subtitle": "No double assignment",
        "transcript": (
            "Maya called out of Robert's medication-reminder visit tomorrow at 10 AM. "
            "Devon accepted the replacement."
        ),
    },
    "candidate_search": {
        "title": "Coverage candidates",
        "subtitle": "Rank options, keep human confirmation",
        "transcript": (
            "Maya called out of Eleanor's personal-care visit tomorrow at 2 PM. "
            "Find a qualified replacement."
        ),
    },
    "duplicate": {
        "title": "Duplicate update",
        "subtitle": "Existing reassignment found",
        "transcript": (
            "Maya called out of Eleanor's personal-care visit tomorrow at 4 PM. "
            "Devon accepted the replacement."
        ),
    },
    "emr_outage": {
        "title": "EMR unavailable",
        "subtitle": "No false completion",
        "transcript": (
            "Maya called out of Eleanor's personal-care visit tomorrow at 2 PM. "
            "Devon accepted the replacement."
        ),
        "force_offline": "emr",
    },
    "urgent": {
        "title": "Urgent escalation",
        "subtitle": "Human ownership before automation",
        "transcript": (
            "Urgent: Maya called out of Eleanor's personal-care visit tomorrow at 2 PM. "
            "The family mentioned a hospital risk."
        ),
    },
}


def scenario_list() -> list[dict[str, Any]]:
    return [{"id": key, **value} for key, value in SCENARIOS.items()]


def _event(
    step: str,
    call: str,
    why: str,
    input_: Any,
    result: Any,
    status: str = "info",
    system: str | None = None,
) -> dict[str, Any]:
    display_call = call
    if system in MOCK_ADAPTER_SYSTEMS and not call.startswith("MOCK "):
        display_call = f"MOCK {call}"
    return {
        "step": step,
        "call": display_call,
        "why": why,
        "input": input_,
        "result": result,
        "status": status,
        "system": system,
    }


def _tomorrow_slot(hour: int, minute: int = 0) -> str:
    return (
        datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        + timedelta(days=1)
    ).isoformat()


def _requested_slot(intent: dict[str, Any]) -> str | None:
    requested = str(intent.get("requested_time") or "").lower()
    if "tomorrow" not in requested:
        return None
    patterns = [
        (r"\b10(?::00)?\s*am\b", 10),
        (r"\b2(?::00)?\s*pm\b", 14),
        (r"\b4(?::00)?\s*pm\b", 16),
        (r"\b6(?::00)?\s*pm\b", 18),
    ]
    for pattern, hour in patterns:
        if re.search(pattern, requested):
            return _tomorrow_slot(hour)
    return None


def _slot_label(starts_at: str) -> str:
    value = datetime.fromisoformat(starts_at)
    return f"tomorrow at {value.strftime('%I:%M %p').lstrip('0')}"


def _parser_block_reason(intent: dict[str, Any], parser_source: str) -> str | None:
    if parser_source in {
        "openai_error",
        "openai_invalid",
        "deterministic_invalid",
    }:
        return intent.get("_parser_error") or "The intent parser was unavailable or invalid."
    try:
        confidence = float(intent.get("confidence", 0))
    except (TypeError, ValueError):
        return "Parser confidence was invalid."
    if confidence < MIN_WRITE_CONFIDENCE:
        return f"Parser confidence {confidence:.2f} is below the write threshold."
    if intent.get("needs_human"):
        return "The request contains an urgent or high-risk signal."
    return None


def _clarify_outcome(
    title: str,
    detail: str,
    reason: str,
    events: list[dict[str, Any]],
    packet: dict[str, Any] | None = None,
    suggestions: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    events.append(
        _event(
            "gate",
            "POST /decision/gate",
            reason,
            {},
            "Clarification required; no schedule write occurred.",
            "warn",
        )
    )
    return {
        "type": "CLARIFY",
        "title": title,
        "detail": detail,
        "status": "warning",
        "packet": packet
        or {
            "Action": "Ask for missing information",
            "Reason": reason,
            "Schedule write": "None",
        },
        "suggestions": suggestions or [],
    }


def _handoff_outcome(
    conn,
    transcript: str,
    intent: dict[str, Any],
    detail: str,
    reason: str,
    events: list[dict[str, Any]],
    queue: str = "care-coordination",
    packet: dict[str, Any] | None = None,
    status: str = "warning",
    outcome_type: str = "HANDOFF",
) -> dict[str, Any]:
    handoff = db.create_handoff(
        conn,
        queue,
        reason,
        detail,
        {"transcript": transcript, "intent": intent, "packet": packet or {}},
    )
    events.append(
        _event(
            "gate",
            "POST /decision/gate",
            reason,
            intent,
            "Automation stopped.",
            "warn" if status == "warning" else "bad",
        )
    )
    events.append(
        _event(
            "final",
            "POST /operations/handoff",
            "Give the unresolved work an owner and preserve context.",
            {"queue": queue, "reason": reason},
            f"Handoff #{handoff['id']} created.",
            "warn",
            "routing",
        )
    )
    return {
        "type": outcome_type,
        "title": "Operations handoff created",
        "detail": detail,
        "status": status,
        "packet": packet
        or {
            "Queue": queue,
            "Reason": reason,
            "Schedule write": "None",
            "Handoff": f"#{handoff['id']}",
        },
    }


def _integration_block(
    conn,
    required: list[str],
    events: list[dict[str, Any]],
) -> str | None:
    for key in required:
        if not db.integration_online(conn, key):
            events.append(
                _event(
                    "checks",
                    f"GET /integrations/{key}",
                    "A required operational dependency must be available before a schedule write.",
                    {"system": key},
                    "OFFLINE",
                    "bad",
                    key,
                )
            )
            return key
    return None


def _candidate_rows(
    conn,
    original_id: str,
    shift: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM caregivers ORDER BY name").fetchall()
    candidates: list[dict[str, Any]] = []
    required = set(shift["required_skills"])
    for row in rows:
        caregiver = dict(row)
        if caregiver["id"] == original_id:
            continue
        skills = set(json.loads(caregiver.pop("skills_json")))
        zones = set(json.loads(caregiver.pop("zones_json")))
        reasons: list[str] = []
        if not required.issubset(skills):
            reasons.append("missing qualification")
        if shift["client_zone"] not in zones:
            reasons.append("outside service zone")
        if not bool(caregiver["outreach_consent"]):
            reasons.append("no outreach permission")
        if db.caregiver_has_conflict(
            conn,
            caregiver["id"],
            shift["starts_at"],
            shift["id"],
        ):
            reasons.append("schedule conflict")
        if not reasons:
            candidates.append(
                {
                    "id": caregiver["id"],
                    "name": caregiver["name"],
                    "skills": sorted(skills),
                    "zone": shift["client_zone"],
                }
            )
    return candidates


def _process_request(
    conn,
    scenario_id: str | None,
    transcript: str,
    intent: dict[str, Any],
    parser_source: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    events = [
        _event(
            "request",
            "INBOUND_OPERATION",
            "Preserve the exact coordinator or caregiver language.",
            transcript,
            "Request stored.",
            "good",
        ),
        _event(
            "ai",
            "POST /ai/intent",
            "Convert messy language into typed fields without granting write authority.",
            transcript,
            intent,
            "good" if parser_source == "openai" else "info",
        ),
        _event(
            "route",
            "POST /workflow/route",
            "Route call-out and reassignment work to the required checks.",
            intent.get("intent"),
            "Shift coverage workflow",
            "good",
        ),
    ]

    block_reason = _parser_block_reason(intent, parser_source)
    if block_reason:
        return (
            _handoff_outcome(
                conn,
                transcript,
                intent,
                "A coordinator must review this request before any schedule change.",
                block_reason,
                events,
                status="error" if parser_source.endswith("error") else "warning",
            ),
            events,
        )

    if intent.get("intent") not in {"shift_callout", "shift_reassignment"}:
        return (
            _clarify_outcome(
                "The workflow needs a shift-coverage request",
                "The request was not specific enough to identify a call-out or reassignment.",
                "Unsupported or unclear operational intent.",
                events,
            ),
            events,
        )

    original_name = intent.get("original_caregiver")
    if not original_name:
        return (
            _clarify_outcome(
                "Which caregiver called out?",
                "Caregiver identity is required before the system can look up assigned shifts.",
                "Missing original caregiver.",
                events,
            ),
            events,
        )
    original = db.find_caregiver(conn, original_name)
    events.append(
        _event(
            "checks",
            "GET /workforce/caregiver",
            "Resolve the caregiver against the workforce directory.",
            original_name,
            original["name"] if original else "NOT FOUND",
            "good" if original else "bad",
            "workforce",
        )
    )
    if not original:
        return (
            _handoff_outcome(
                conn,
                transcript,
                intent,
                "The named caregiver was not found in the mock workforce directory.",
                "Unknown caregiver identity.",
                events,
            ),
            events,
        )

    client_name = intent.get("client_name")
    if not client_name:
        possible = db.shifts_for_original(conn, original["id"])
        suggestions = [
            {
                "label": f"{row['client_name']} · {_slot_label(row['starts_at'])}",
                "transcript": (
                    f"{original['name']} called out of {row['client_name']}'s "
                    f"{row['service_type'].replace('_', '-')} visit {_slot_label(row['starts_at'])}."
                ),
            }
            for row in possible[:3]
        ]
        return (
            _clarify_outcome(
                "Which client visit is affected?",
                f"{original['name']} has more than one scheduled visit, so the workflow will not guess.",
                "Missing client and shift identity.",
                events,
                {
                    "Caregiver": original["name"],
                    "Candidate shifts": len(possible),
                    "Schedule write": "None",
                },
                suggestions,
            ),
            events,
        )

    client = db.find_client(conn, client_name)
    events.append(
        _event(
            "checks",
            "GET /care-plan/client",
            "Resolve the client and required qualifications.",
            client_name,
            client["name"] if client else "NOT FOUND",
            "good" if client else "bad",
            "care_plan",
        )
    )
    if not client:
        return (
            _handoff_outcome(
                conn,
                transcript,
                intent,
                "The named client was not found in the mock care-plan system.",
                "Unknown client.",
                events,
            ),
            events,
        )

    starts_at = _requested_slot(intent)
    if not starts_at:
        possible = db.shifts_for_original(conn, original["id"], client["id"])
        suggestions = [
            {
                "label": _slot_label(row["starts_at"]),
                "transcript": (
                    f"{original['name']} called out of {client['name']}'s "
                    f"{row['service_type'].replace('_', '-')} visit {_slot_label(row['starts_at'])}."
                ),
            }
            for row in possible[:3]
        ]
        return (
            _clarify_outcome(
                "Which scheduled visit?",
                "A specific supported date and time are required before changing a shift.",
                "Missing or unsupported shift time.",
                events,
                {
                    "Caregiver": original["name"],
                    "Client": client["name"],
                    "Matching scheduled visits": len(possible),
                    "Schedule write": "None",
                },
                suggestions,
            ),
            events,
        )

    shift_at_time = db.find_shift_by_client_time(conn, client["id"], starts_at)
    replacement_name = intent.get("replacement_caregiver")
    replacement = (
        db.find_caregiver(conn, replacement_name) if replacement_name else None
    )
    if shift_at_time and replacement:
        existing = db.completed_reassignment(
            conn,
            shift_at_time["id"],
            replacement["id"],
        )
        if existing:
            events.append(
                _event(
                    "checks",
                    "GET /scheduler/reassignments",
                    "Detect a completed matching reassignment before retrying.",
                    {
                        "shift": shift_at_time["id"],
                        "replacement": replacement["name"],
                    },
                    f"EXISTING #{existing['id']}",
                    "good",
                    "scheduler",
                )
            )
            events.append(
                _event(
                    "gate",
                    "POST /decision/gate",
                    "The requested final state already exists.",
                    {},
                    "Duplicate write prevented.",
                    "good",
                )
            )
            return (
                {
                    "type": "DUPLICATE_FOUND",
                    "title": "Existing reassignment confirmed",
                    "detail": (
                        f"{replacement['name']} is already assigned to "
                        f"{client['name']}'s visit {_slot_label(starts_at)}."
                    ),
                    "status": "success",
                    "packet": {
                        "Client": client["name"],
                        "Replacement": replacement["name"],
                        "Shift": _slot_label(starts_at),
                        "New write": "None",
                        "Existing reassignment": f"#{existing['id']}",
                    },
                },
                events,
            )

    shift = db.find_shift(conn, original["id"], client["id"], starts_at)
    events.append(
        _event(
            "checks",
            "GET /scheduler/shift",
            "Verify the exact assigned visit before changing it.",
            {
                "caregiver": original["name"],
                "client": client["name"],
                "starts_at": starts_at,
            },
            shift["id"] if shift else "NOT FOUND",
            "good" if shift else "bad",
            "scheduler",
        )
    )
    if not shift:
        return (
            _handoff_outcome(
                conn,
                transcript,
                intent,
                "No matching scheduled visit was found for that caregiver, client, and time.",
                "Shift identity could not be verified.",
                events,
            ),
            events,
        )

    if intent.get("service_type") and intent["service_type"] != shift["service_type"]:
        return (
            _clarify_outcome(
                "Service details do not match",
                "The stated service type conflicts with the scheduled visit.",
                "Care-plan and request mismatch.",
                events,
                {
                    "Requested service": intent["service_type"],
                    "Scheduled service": shift["service_type"],
                    "Schedule write": "None",
                },
            ),
            events,
        )

    offline = _integration_block(
        conn,
        ["workforce", "scheduler", "care_plan", "compliance", "emr"],
        events,
    )
    if offline:
        return (
            _handoff_outcome(
                conn,
                transcript,
                intent,
                f"The {offline} dependency is unavailable, so the workflow will not report a completed reassignment.",
                f"Required integration offline: {offline}.",
                events,
                status="error",
            ),
            events,
        )

    if not replacement_name:
        candidates = _candidate_rows(conn, original["id"], shift)
        events.append(
            _event(
                "checks",
                "POST /coverage/candidates",
                "Filter by qualification, zone, availability, and outreach permission.",
                {
                    "shift": shift["id"],
                    "required_skills": shift["required_skills"],
                    "zone": shift["client_zone"],
                },
                [row["name"] for row in candidates] or "NONE",
                "good" if candidates else "warn",
                "compliance",
            )
        )
        if candidates:
            names = ", ".join(row["name"] for row in candidates)
            return (
                _handoff_outcome(
                    conn,
                    transcript,
                    intent,
                    f"Qualified candidates were prepared ({names}), but no one is assigned until acceptance is confirmed.",
                    "Human outreach and acceptance are still required.",
                    events,
                    packet={
                        "Client": client["name"],
                        "Shift": _slot_label(starts_at),
                        "Qualified candidates": names,
                        "Schedule write": "None",
                    },
                ),
                events,
            )
        return (
            _handoff_outcome(
                conn,
                transcript,
                intent,
                "No qualified, available, contactable replacement was found.",
                "Coverage search exhausted.",
                events,
                status="error",
            ),
            events,
        )

    events.append(
        _event(
            "checks",
            "GET /workforce/replacement",
            "Resolve the proposed replacement against the workforce directory.",
            replacement_name,
            replacement["name"] if replacement else "NOT FOUND",
            "good" if replacement else "bad",
            "workforce",
        )
    )
    if not replacement:
        return (
            _handoff_outcome(
                conn,
                transcript,
                intent,
                "The proposed replacement was not found in the workforce directory.",
                "Unknown replacement caregiver.",
                events,
            ),
            events,
        )

    if not intent.get("replacement_accepted"):
        return (
            _clarify_outcome(
                "Has the replacement accepted?",
                "The workflow will not assign a caregiver merely because they appear eligible.",
                "Replacement acceptance is not confirmed.",
                events,
                {
                    "Proposed replacement": replacement["name"],
                    "Schedule write": "None",
                },
            ),
            events,
        )

    required = set(shift["required_skills"])
    replacement_skills = set(replacement["skills"])
    qualified = required.issubset(replacement_skills)
    zone_match = shift["client_zone"] in set(replacement["zones"])
    events.append(
        _event(
            "checks",
            "POST /compliance/eligibility",
            "Verify required skills and service-zone compatibility deterministically.",
            {
                "required_skills": sorted(required),
                "caregiver_skills": sorted(replacement_skills),
                "required_zone": shift["client_zone"],
                "caregiver_zones": replacement["zones"],
            },
            {
                "qualified": qualified,
                "zone_match": zone_match,
            },
            "good" if qualified and zone_match else "bad",
            "compliance",
        )
    )
    if not qualified or not zone_match:
        missing = sorted(required - replacement_skills)
        return (
            _handoff_outcome(
                conn,
                transcript,
                intent,
                (
                    f"{replacement['name']} cannot be assigned because the "
                    f"eligibility checks failed"
                    + (f": missing {', '.join(missing)}." if missing else ".")
                ),
                "Replacement does not satisfy care-plan constraints.",
                events,
                status="error",
                outcome_type="BLOCKED",
            ),
            events,
        )

    conflict = db.caregiver_has_conflict(
        conn,
        replacement["id"],
        starts_at,
        shift["id"],
    )
    events.append(
        _event(
            "checks",
            "GET /scheduler/conflicts",
            "Prevent the replacement from being assigned to overlapping visits.",
            {"caregiver": replacement["name"], "starts_at": starts_at},
            "CONFLICT" if conflict else "AVAILABLE",
            "bad" if conflict else "good",
            "scheduler",
        )
    )
    if conflict:
        return (
            _handoff_outcome(
                conn,
                transcript,
                intent,
                f"{replacement['name']} already has a scheduled visit at that time.",
                "Replacement schedule conflict.",
                events,
                status="error",
                outcome_type="BLOCKED",
            ),
            events,
        )

    events.append(
        _event(
            "gate",
            "POST /decision/gate",
            "Identity, shift, qualifications, zone, availability, and acceptance all passed.",
            {},
            "Reassignment allowed.",
            "good",
        )
    )
    reassignment = db.apply_reassignment(conn, shift, replacement)
    events.append(
        _event(
            "final",
            "POST /emr/shift-assignment",
            "Write only the verified assignment and retain the previous owner.",
            {
                "shift": shift["id"],
                "from": original["name"],
                "to": replacement["name"],
            },
            f"Reassignment #{reassignment.get('id')} completed.",
            "good",
            "emr",
        )
    )
    db.create_operation_log(
        conn,
        "shift_reassigned",
        f"{client['name']} visit reassigned to {replacement['name']}.",
        {
            "shift_id": shift["id"],
            "from": original["id"],
            "to": replacement["id"],
            "starts_at": starts_at,
        },
    )
    events.append(
        _event(
            "final",
            "POST /operations/audit-log",
            "Record the decision inputs and final action for operations review.",
            {"reassignment_id": reassignment.get("id")},
            "Audit entry stored.",
            "good",
            "emr",
        )
    )
    return (
        {
            "type": "REASSIGNED",
            "title": "Shift reassigned safely",
            "detail": (
                f"{replacement['name']} is assigned to {client['name']}'s "
                f"{shift['service_type'].replace('_', ' ')} visit {_slot_label(starts_at)}."
            ),
            "status": "success",
            "packet": {
                "Client": client["name"],
                "Shift": _slot_label(starts_at),
                "Service": shift["service_type"].replace("_", " "),
                "Previous caregiver": original["name"],
                "Replacement": replacement["name"],
                "Qualification": "Verified",
                "Schedule conflict": "None",
                "Acceptance": "Confirmed",
                "Reassignment": f"#{reassignment.get('id')}",
            },
        },
        events,
    )


def run_request(
    scenario_id: str | None = None,
    transcript: str | None = None,
) -> dict[str, Any]:
    db.init_db()
    scenario = SCENARIOS.get(scenario_id or "", {})
    transcript = transcript or scenario.get("transcript") or ""
    if not transcript.strip():
        raise ValueError("transcript is required")

    forced_offline = scenario.get("force_offline")
    restore_online = False
    if forced_offline:
        current = next(
            (
                item
                for item in db.list_integrations()
                if item["key"] == forced_offline
            ),
            None,
        )
        restore_online = bool(current and current["online"])
        db.set_integration(forced_offline, False)

    try:
        intent, parser_source = ai.parse_intent(transcript)
        with db.connect() as conn:
            outcome, events = _process_request(
                conn,
                scenario_id,
                transcript,
                intent,
                parser_source,
            )
            run_id = db.save_run(
                conn,
                scenario_id,
                transcript,
                parser_source,
                intent,
                outcome,
                events,
            )
            conn.commit()
        integrations = db.list_integrations()
        return {
            "run_id": run_id,
            "scenario_id": scenario_id,
            "transcript": transcript,
            "intent": intent,
            "ai_source": parser_source,
            "events": events,
            "outcome": outcome,
            "integrations": integrations,
        }
    finally:
        if forced_offline and restore_online:
            db.set_integration(forced_offline, True)
