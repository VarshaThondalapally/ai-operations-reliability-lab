from __future__ import annotations

import json
import os
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


SYSTEM_PROMPT = """You parse fictional home-care operations requests into strict JSON.
You do not reassign shifts, contact caregivers, update an EMR, or decide eligibility.

Return JSON with exactly these keys:
intent: one of ["shift_reassignment","shift_callout","schedule_question","unknown"]
original_caregiver: string or null
replacement_caregiver: string or null
client_name: string or null
service_type: one of ["personal_care","companion","medication_reminder", null]
requested_time: short natural language string or null
replacement_accepted: boolean
needs_human: boolean
confidence: number 0..1

Extract only what is present. Do not invent missing people, clients, times, or acceptance."""


class ParsedIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["shift_reassignment", "shift_callout", "schedule_question", "unknown"]
    original_caregiver: str | None
    replacement_caregiver: str | None
    client_name: str | None
    service_type: Literal["personal_care", "companion", "medication_reminder"] | None
    requested_time: str | None
    replacement_accepted: bool
    needs_human: bool
    confidence: float = Field(ge=0, le=1)

    @field_validator(
        "original_caregiver",
        "replacement_caregiver",
        "client_name",
        "requested_time",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value


def _safe_unknown(reason: str) -> dict[str, Any]:
    return {
        "intent": "unknown",
        "original_caregiver": None,
        "replacement_caregiver": None,
        "client_name": None,
        "service_type": None,
        "requested_time": None,
        "replacement_accepted": False,
        "needs_human": True,
        "confidence": 0.0,
        "_parser_error": reason[:220],
    }


def _validated(payload: dict[str, Any]) -> dict[str, Any]:
    return ParsedIntent.model_validate(payload).model_dump()


def mock_parse(transcript: str) -> dict[str, Any]:
    text = transcript.lower()
    names = {
        "maya": "Maya Patel",
        "devon": "Devon Brooks",
        "jordan": "Jordan Lee",
        "priya": "Priya Shah",
    }
    clients = {
        "eleanor": "Eleanor Price",
        "robert": "Robert Chen",
    }

    mentioned_people = [name for token, name in names.items() if token in text]
    original_caregiver = mentioned_people[0] if mentioned_people else None
    replacement_caregiver = mentioned_people[1] if len(mentioned_people) > 1 else None
    client_name = next((name for token, name in clients.items() if token in text), None)

    if any(term in text for term in ["called out", "call-out", "cannot cover", "can't cover"]):
        intent = "shift_callout"
    elif any(term in text for term in ["reassign", "replace", "cover", "accepted"]):
        intent = "shift_reassignment"
    elif any(term in text for term in ["schedule", "shift"]):
        intent = "schedule_question"
    else:
        intent = "unknown"

    replacement_accepted = any(
        term in text
        for term in ["accepted", "can cover", "will cover", "confirmed", "agreed to cover"]
    )
    if replacement_caregiver and replacement_accepted:
        intent = "shift_reassignment"

    service_type = None
    if any(term in text for term in ["personal care", "personal-care", "daily living"]):
        service_type = "personal_care"
    elif any(term in text for term in ["companion", "companionship"]):
        service_type = "companion"
    elif any(term in text for term in ["medication", "med reminder", "medication-reminder"]):
        service_type = "medication_reminder"

    requested_time = None
    if "tomorrow" in text:
        requested_time = "tomorrow"
    time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text)
    if time_match:
        requested_time = (
            f"{requested_time} {time_match.group(0)}"
            if requested_time
            else time_match.group(0)
        )

    needs_human = any(term in text for term in ["urgent", "emergency", "hospital"])
    confidence = 0.93 if intent != "unknown" else 0.32

    return {
        "intent": intent,
        "original_caregiver": original_caregiver,
        "replacement_caregiver": replacement_caregiver,
        "client_name": client_name,
        "service_type": service_type,
        "requested_time": requested_time,
        "replacement_accepted": replacement_accepted,
        "needs_human": needs_human,
        "confidence": confidence,
    }


def parse_intent(transcript: str) -> tuple[dict[str, Any], str]:
    if (
        os.getenv("RELIABILITY_DEMO_USE_MOCK_LLM") == "1"
        or not os.getenv("OPENAI_API_KEY")
    ):
        try:
            return _validated(mock_parse(transcript)), "deterministic"
        except ValidationError as exc:
            return _safe_unknown(
                f"Deterministic parser failed schema validation: {exc.errors()}"
            ), "deterministic_invalid"

    try:
        from openai import OpenAI

        client = OpenAI()
        model = os.getenv("RELIABILITY_DEMO_OPENAI_MODEL", "gpt-4o-mini")
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
        )
        parsed = json.loads(response.choices[0].message.content or "{}")
        return _validated(parsed), "openai"
    except ValidationError as exc:
        return _safe_unknown(
            f"OpenAI output failed schema validation: {exc.errors()}"
        ), "openai_invalid"
    except Exception as exc:
        return _safe_unknown(f"OpenAI parser unavailable: {exc}"), "openai_error"
