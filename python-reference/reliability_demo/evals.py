from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from . import ai, db, engine


Check = Callable[[dict[str, Any]], tuple[bool, str]]


def _base_intent(**changes: Any) -> dict[str, Any]:
    payload = {
        "intent": "shift_reassignment",
        "original_caregiver": "Maya Patel",
        "replacement_caregiver": "Devon Brooks",
        "client_name": "Eleanor Price",
        "service_type": "personal_care",
        "requested_time": "tomorrow 2 PM",
        "replacement_accepted": True,
        "needs_human": False,
        "confidence": 0.93,
    }
    payload.update(changes)
    return payload


def _run_case(
    title: str,
    expected: str,
    *,
    scenario_id: str | None = None,
    transcript: str | None = None,
    reassignment_delta: int = 0,
    handoff_delta: int = 0,
    log_delta: int = 0,
    check: Check | None = None,
    intent_override: dict[str, Any] | None = None,
    parser_source: str = "deterministic",
) -> dict[str, Any]:
    db.init_db(reset=True)
    before = db.counts()
    original_parser = ai.parse_intent
    if intent_override is not None:
        ai.parse_intent = lambda _: (intent_override, parser_source)
    try:
        result = engine.run_request(scenario_id=scenario_id, transcript=transcript)
    finally:
        ai.parse_intent = original_parser
    after = db.counts()

    failures: list[str] = []
    actual = result["outcome"]["type"]
    if actual != expected:
        failures.append(f"expected {expected}, got {actual}")
    if after["reassignments"] - before["reassignments"] != reassignment_delta:
        failures.append(
            "unexpected reassignment delta "
            f"{after['reassignments'] - before['reassignments']}"
        )
    if after["handoffs"] - before["handoffs"] != handoff_delta:
        failures.append(
            f"unexpected handoff delta {after['handoffs'] - before['handoffs']}"
        )
    if after["logs"] - before["logs"] != log_delta:
        failures.append(f"unexpected log delta {after['logs'] - before['logs']}")
    if check:
        passed, detail = check(result)
        if not passed:
            failures.append(detail)

    return {
        "scenario_id": scenario_id or title,
        "title": title,
        "expected": expected,
        "actual": actual,
        "passed": not failures,
        "failures": failures,
        "parser_source": result["ai_source"],
    }


def _coverage_check(result: dict[str, Any]) -> tuple[bool, str]:
    events = result["events"]
    required_mock_calls = {
        "GET /workforce/caregiver",
        "GET /care-plan/client",
        "GET /scheduler/shift",
        "POST /compliance/eligibility",
        "GET /scheduler/conflicts",
        "POST /emr/shift-assignment",
    }
    calls = {event["call"] for event in events}
    missing = {
        f"MOCK {call}"
        for call in required_mock_calls
        if f"MOCK {call}" not in calls
    }
    if missing:
        return False, f"missing mock-adapter labels: {sorted(missing)}"
    packet = result["outcome"]["packet"]
    if packet.get("Replacement") != "Devon Brooks":
        return False, "replacement was not Devon Brooks"
    if packet.get("Qualification") != "Verified":
        return False, "qualification was not verified"
    return True, "coverage write and adapter labels verified"


def _candidate_check(result: dict[str, Any]) -> tuple[bool, str]:
    packet = result["outcome"]["packet"]
    if packet.get("Qualified candidates") != "Devon Brooks":
        return False, f"unexpected candidate list: {packet.get('Qualified candidates')}"
    return True, "candidate filtering verified"


def _repeat_idempotency_case() -> dict[str, Any]:
    db.init_db(reset=True)
    before = db.counts()
    first = engine.run_request(scenario_id="coverage")
    after_first = db.counts()
    second = engine.run_request(scenario_id="coverage")
    after_second = db.counts()
    failures: list[str] = []
    if first["outcome"]["type"] != "REASSIGNED":
        failures.append("first request did not reassign")
    if second["outcome"]["type"] != "DUPLICATE_FOUND":
        failures.append("second request did not detect existing state")
    if after_first["reassignments"] - before["reassignments"] != 1:
        failures.append("first request did not create exactly one reassignment")
    if after_second["reassignments"] - after_first["reassignments"] != 0:
        failures.append("second request created another reassignment")
    return {
        "scenario_id": "repeat_coverage",
        "title": "Repeated coverage request",
        "expected": "DUPLICATE_FOUND",
        "actual": second["outcome"]["type"],
        "passed": not failures,
        "failures": failures,
        "parser_source": second["ai_source"],
    }


def run_all() -> dict[str, Any]:
    original_db_path = db.DB_PATH
    original_mock_flag = os.environ.get("RELIABILITY_DEMO_USE_MOCK_LLM")
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        db.DB_PATH = Path(tmp_dir) / "evals.db"
        os.environ["RELIABILITY_DEMO_USE_MOCK_LLM"] = "1"
        try:
            results.extend(
                [
                    _run_case(
                        "safe shift reassignment",
                        "REASSIGNED",
                        scenario_id="coverage",
                        reassignment_delta=1,
                        log_delta=1,
                        check=_coverage_check,
                    ),
                    _run_case(
                        "ambiguous call-out",
                        "CLARIFY",
                        scenario_id="ambiguous",
                    ),
                    _run_case(
                        "scheduler outage",
                        "HANDOFF",
                        scenario_id="outage",
                        handoff_delta=1,
                    ),
                    _run_case(
                        "qualification mismatch",
                        "BLOCKED",
                        scenario_id="qualification",
                        handoff_delta=1,
                    ),
                    _run_case(
                        "replacement schedule conflict",
                        "BLOCKED",
                        scenario_id="conflict",
                        handoff_delta=1,
                    ),
                    _run_case(
                        "candidate filtering",
                        "HANDOFF",
                        scenario_id="candidate_search",
                        handoff_delta=1,
                        check=_candidate_check,
                    ),
                    _run_case(
                        "seeded duplicate",
                        "DUPLICATE_FOUND",
                        scenario_id="duplicate",
                    ),
                    _run_case(
                        "EMR outage",
                        "HANDOFF",
                        scenario_id="emr_outage",
                        handoff_delta=1,
                    ),
                    _run_case(
                        "urgent request",
                        "HANDOFF",
                        scenario_id="urgent",
                        handoff_delta=1,
                    ),
                    _run_case(
                        "missing original caregiver",
                        "CLARIFY",
                        transcript=(
                            "Eleanor's personal-care visit tomorrow at 2 PM needs coverage."
                        ),
                    ),
                    _run_case(
                        "unknown original caregiver",
                        "HANDOFF",
                        transcript="Morgan called out of Eleanor's visit tomorrow at 2 PM.",
                        handoff_delta=1,
                        intent_override=_base_intent(
                            original_caregiver="Morgan Vale",
                            replacement_caregiver=None,
                            replacement_accepted=False,
                        ),
                    ),
                    _run_case(
                        "unknown client",
                        "HANDOFF",
                        transcript="Maya called out of Clara's visit tomorrow at 2 PM.",
                        handoff_delta=1,
                        intent_override=_base_intent(
                            client_name="Clara Stone",
                            replacement_caregiver=None,
                            replacement_accepted=False,
                        ),
                    ),
                    _run_case(
                        "missing shift time",
                        "CLARIFY",
                        transcript="Maya called out of Eleanor's personal-care visit tomorrow.",
                    ),
                    _run_case(
                        "unknown replacement caregiver",
                        "HANDOFF",
                        transcript=(
                            "Maya called out of Eleanor's visit tomorrow at 2 PM. "
                            "Alex accepted."
                        ),
                        handoff_delta=1,
                        intent_override=_base_intent(
                            replacement_caregiver="Alex Rivera",
                        ),
                    ),
                    _run_case(
                        "replacement acceptance missing",
                        "CLARIFY",
                        transcript=(
                            "Maya called out of Eleanor's personal-care visit tomorrow at 2 PM. "
                            "Consider Devon."
                        ),
                        intent_override=_base_intent(replacement_accepted=False),
                    ),
                    _run_case(
                        "low confidence blocks write",
                        "HANDOFF",
                        transcript="Maybe change a shift.",
                        handoff_delta=1,
                        intent_override=_base_intent(confidence=0.21),
                        parser_source="openai",
                    ),
                    _run_case(
                        "parser outage blocks write",
                        "HANDOFF",
                        transcript=(
                            "Maya called out of Eleanor's visit tomorrow at 2 PM. "
                            "Devon accepted."
                        ),
                        handoff_delta=1,
                        intent_override={
                            "intent": "unknown",
                            "original_caregiver": None,
                            "replacement_caregiver": None,
                            "client_name": None,
                            "service_type": None,
                            "requested_time": None,
                            "replacement_accepted": False,
                            "needs_human": True,
                            "confidence": 0.0,
                            "_parser_error": "simulated parser outage",
                        },
                        parser_source="openai_error",
                    ),
                    _repeat_idempotency_case(),
                ]
            )
        finally:
            if original_mock_flag is None:
                os.environ.pop("RELIABILITY_DEMO_USE_MOCK_LLM", None)
            else:
                os.environ["RELIABILITY_DEMO_USE_MOCK_LLM"] = original_mock_flag
            db.DB_PATH = original_db_path

    return {
        "passed": all(row["passed"] for row in results),
        "results": results,
    }


if __name__ == "__main__":
    print(json.dumps(run_all(), indent=2))
