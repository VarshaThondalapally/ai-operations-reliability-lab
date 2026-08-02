# Restoration AI Operations Reliability Lab

Live demo:
<https://ai-operations-reliability-lab.varsha143225.chatgpt.site/>

An interactive, fully synthetic portfolio prototype showing how an AI-assisted
restoration-intake workflow can turn a messy after-hours loss report into a
verified booking, clarification, safety escalation, duplicate-safe update, or
owned human handoff.

The restoration company, callers, properties, claims, integrations, crews, and
outcomes are fictional. This independent engineering demonstration does not
reproduce an employer's private product, customer data, prompts, vendor
payloads, contracts, or architecture.

The core principle is simple:

> A model may interpret the call. Deterministic systems decide whether the
> company can promise or write an operational action.

## What this demonstrates

- Structured intent extraction from messy operational language
- Deterministic source-of-truth checks before any business action
- Clarification instead of guessing when required evidence is ambiguous
- Safety escalation before ordinary intake when hazards are present
- No-write failure handling when CRM or dispatch dependencies are unavailable
- Duplicate-safe updates for repeat calls on an open loss
- Human-owned referral or dispatch handoffs when automation must stop
- Decision traces, visible evidence, and auditable outcomes
- Eighteen regression scenarios covering valid actions and prevented writes

## Interactive scenarios

1. After-hours water loss - verified job and crew assignment
2. Ambiguous property - clarify instead of guessing
3. Immediate safety hazard - escalate before ordinary intake
4. Dispatch system outage - no invented arrival window
5. Repeat call for open loss - link context instead of duplicating work
6. Outside service territory - create an owned referral
7. No verified crew capacity - request human dispatch review
8. Missing claim evidence - book the response and preserve the documentation gap

## Repository structure

- `app/` - interactive TypeScript/React experience deployed with OpenAI Sites
- `tests/` - rendered-output checks for the restoration experience

## Prerequisites

- Node.js `>=22.13.0`

## Run locally

```bash
npm install
npm run dev
npm run build
npm test
```

## Prototype boundaries

This is not a production restoration, claims, dispatch, or voice-agent system.
It contains no real customer or claim data, protected information, vendor
payloads, or credentials. It does not contact anyone or connect to a real CRM,
dispatch calendar, phone system, carrier system, estimating platform, or
restoration company.

A production version would add authentication and authorization, tenant
isolation, encrypted data handling, durable job ownership, idempotency keys,
retry and reconciliation policies, real integration contracts, secrets
management, observability, audit retention, privacy reviews, and
deployment-specific acceptance tests.
