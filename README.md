# AI Operations Reliability Lab

An interactive, fully synthetic portfolio prototype showing how an AI-assisted
home-care workflow can turn an informal caregiver call-out into a verified
schedule change—or stop safely when evidence is missing.

The agency, caregivers, clients, visits, integrations, and outcomes are
fictional. This project is an independent engineering demonstration and does
not reproduce any employer's private product, customer data, prompts, or
architecture.

## What this demonstrates

- Structured intent extraction from messy operational language
- Deterministic identity, shift, qualification, zone, availability, and
  acceptance checks
- Clarification instead of guessing when a caregiver, client, or visit is
  ambiguous
- Safe blocking for qualification or schedule conflicts
- Idempotency protection for repeated reassignment requests
- Owned human escalation when an operational dependency is unavailable
- Decision traces, visible evidence, and auditable outcomes
- Eighteen Python regression scenarios covering outcomes and no-write side
  effects

The language model is never treated as the source of scheduling or compliance
truth.

## Repository structure

- `app/` — interactive TypeScript/React experience deployed with OpenAI Sites
- `python-reference/` — FastAPI, SQLite, mock adapters, and the 18-scenario
  reliability suite
- `tests/` — rendered-output checks for the deployed experience

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

This is not a production healthcare or home-care system. It contains no real
protected health information, does not contact anyone, and does not connect to
a real EMR, scheduler, phone system, or workforce platform.

A production version would add authentication and authorization, tenant
isolation, encrypted data handling, durable job ownership, retry and
reconciliation policies, real integration contracts, secrets management,
observability, audit retention, privacy reviews, and deployment-specific
acceptance tests.
