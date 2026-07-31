# AI Operations Reliability Lab

Live demo:
<https://ai-operations-reliability-lab.varsha143225.chatgpt.site/>

An interactive, fully synthetic portfolio prototype showing how an AI-assisted
restoration-intake workflow can turn a messy after-hours loss report into a
verified booking, clarification, safety escalation, duplicate-safe update, or
owned human handoff.

The restoration company, callers, properties, claims, integrations, crews, and
outcomes are fictional. This project is an independent engineering
demonstration and does not reproduce any employer's private product, customer
data, prompts, vendor payloads, contracts, or architecture.

The core principle is simple:

> A model may interpret the call. Deterministic systems decide whether the
> company can promise or write an operational action.

## What this demonstrates

- Structured intent from messy operational language
- Deterministic source-of-truth checks before any business action
- Clarification instead of guessing when the property or required evidence is
  ambiguous
- Safety escalation before ordinary intake when hazards are present
- No-write failure handling when CRM or dispatch dependencies are unavailable
- Duplicate-safe updates for repeat calls on an open loss
- Human-owned referral or dispatch handoff when automation must stop
- Decision traces, visible evidence, and auditable outcomes
- Eighteen restoration-intake regression cases in the live demo coverage panel

The language model or parser is never treated as the source of operational,
coverage, dispatch, or claims truth.

## Current restoration scenarios

The deployed React experience includes eight visible restoration-intake
scenarios:

1. After-hours water loss - verified job and crew assignment
2. Ambiguous property - clarify instead of guessing
3. Immediate safety hazard - escalate before ordinary intake
4. Dispatch system outage - no invented arrival window
5. Repeat call for open loss - link context, do not duplicate work
6. Outside service territory - owned referral, not a dead end
7. No verified crew capacity - pending review, not a false booking
8. Missing claim evidence - book response, flag documentation gap

The coverage panel lists 18 regression cases across booking, clarification,
hazard escalation, dependency outages, duplicate prevention, referral handoff,
capacity review, contact restrictions, parser failures, idempotency, and audit
packet preservation.

## Repository structure

- `app/` - current restoration-intake TypeScript/React experience deployed
  with OpenAI Sites
- `tests/` - rendered-output checks for the deployed restoration experience
- `python-reference/` - earlier FastAPI/SQLite reference implementation from
  the home-care scheduling version of the same reliability pattern

## Project evolution

This project originally explored the same reliability pattern in a synthetic
home-care scheduling workflow. The current deployed version adapts the pattern
to restoration intake so it is closer to my SusanAI/restoration-estimating
experience:

messy operational request -> structured intent -> deterministic source checks
-> safe write, clarification, block, duplicate update, or human handoff.

The `python-reference/` directory still preserves the earlier home-care
reference implementation. The current public demo and resume-facing artifact
are the restoration-intake React experience in `app/`.

## Prerequisites

- Node.js `>=22.13.0`
- Python `>=3.11` for the reference implementation

## Run the interactive site

```bash
npm install
npm run dev
npm run build
```

## Run the Python reference

```powershell
cd python-reference
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:RELIABILITY_DEMO_USE_MOCK_LLM="1"
python -m uvicorn reliability_demo.app:app --port 8010
```

Run the reliability suite:

```powershell
python -m reliability_demo.evals
```

## Prototype boundaries

This is not a production restoration, claims, dispatch, or voice-agent system.
It contains no real customer data, protected information, claim data, vendor
payloads, or credentials. It does not contact anyone and does not connect to a
real CRM, dispatch calendar, phone system, carrier system, estimating platform,
or restoration company.

A production version would add authentication and authorization, tenant
isolation, encrypted data handling, durable job ownership, idempotency keys,
retry and reconciliation policies, real integration contracts, secrets
management, observability, audit retention, privacy reviews, and
deployment-specific acceptance tests.
