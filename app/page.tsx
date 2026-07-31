"use client";

import { useMemo, useState } from "react";

type Status = "good" | "warn" | "bad" | "info";
type SystemKey =
  | "crm"
  | "coverage"
  | "dispatch"
  | "claims"
  | "consent"
  | "routing";

type TraceEvent = {
  step: string;
  call: string;
  reason: string;
  result: string;
  status: Status;
  system?: SystemKey;
};

type Outcome = {
  type: "BOOKED" | "CLARIFY" | "HANDOFF" | "BLOCKED" | "DUPLICATE";
  title: string;
  detail: string;
  status: Status;
  packet: Record<string, string>;
};

type Scenario = {
  id: string;
  title: string;
  subtitle: string;
  request: string;
  events: TraceEvent[];
  outcome: Outcome;
  forceOffline?: SystemKey;
};

const systems: Array<{
  key: SystemKey;
  label: string;
  description: string;
}> = [
  {
    key: "crm",
    label: "Mock CRM",
    description: "Caller, property, open-loss, and duplicate-job records",
  },
  {
    key: "coverage",
    label: "Service coverage",
    description: "Territory, loss type, safety, and response-policy checks",
  },
  {
    key: "dispatch",
    label: "Dispatch calendar",
    description: "Crew capacity, response window, and assignment status",
  },
  {
    key: "claims",
    label: "Claims intake",
    description: "Carrier context, evidence checklist, and estimating handoff",
  },
  {
    key: "consent",
    label: "Contact consent",
    description: "Permission and preferred channel for operational updates",
  },
  {
    key: "routing",
    label: "Human escalation",
    description: "Named ownership when automation must stop",
  },
];

const steps = [
  {
    id: "request",
    number: "01",
    title: "Call preserved",
    description: "Keep the caller's exact loss report",
  },
  {
    id: "intent",
    number: "02",
    title: "Intent structured",
    description: "Extract typed fields without write authority",
  },
  {
    id: "route",
    number: "03",
    title: "Workflow routed",
    description: "Select the required operational checks",
  },
  {
    id: "checks",
    number: "04",
    title: "Systems checked",
    description: "Verify business sources of truth",
  },
  {
    id: "gate",
    number: "05",
    title: "Decision gated",
    description: "Book, clarify, block, dedupe, or escalate",
  },
  {
    id: "final",
    number: "06",
    title: "Action visible",
    description: "Write safely or create an owned handoff",
  },
];

const baseEvents: TraceEvent[] = [
  {
    step: "request",
    call: "INBOUND_CALL_TRANSCRIPT",
    reason: "Preserve the caller's exact language before interpretation.",
    result: "Transcript stored",
    status: "good",
  },
  {
    step: "intent",
    call: "POST /intent/parse",
    reason: "Convert an unstructured loss report into typed intake fields.",
    result: "Structured intent created",
    status: "good",
  },
  {
    step: "route",
    call: "POST /workflow/route",
    reason: "Choose the checks required for emergency restoration intake.",
    result: "Loss-intake workflow selected",
    status: "good",
  },
];

const bookedEvents: TraceEvent[] = [
  ...baseEvents,
  {
    step: "checks",
    call: "MOCK GET /crm/property",
    reason: "Resolve the caller, property, and any open loss before creating work.",
    result: "1407 Ashwood Dr verified - no open job",
    status: "good",
    system: "crm",
  },
  {
    step: "checks",
    call: "MOCK POST /coverage/qualify",
    reason: "Confirm territory, supported loss type, and safety answers.",
    result: "Water loss accepted - safety screen passed",
    status: "good",
    system: "coverage",
  },
  {
    step: "checks",
    call: "MOCK GET /dispatch/capacity",
    reason: "Verify a real response window before making a promise.",
    result: "Crew 12 available - 60 to 90 minutes",
    status: "good",
    system: "dispatch",
  },
  {
    step: "checks",
    call: "MOCK GET /consent/contact",
    reason: "Confirm the caller can receive dispatch updates.",
    result: "SMS updates allowed",
    status: "good",
    system: "consent",
  },
  {
    step: "gate",
    call: "POST /decision/gate",
    reason: "Property, service area, safety, capacity, and consent all passed.",
    result: "Job creation allowed",
    status: "good",
  },
  {
    step: "final",
    call: "MOCK POST /crm/jobs",
    reason: "Create only the verified loss record.",
    result: "Job RST-2048 created",
    status: "good",
    system: "crm",
  },
  {
    step: "final",
    call: "MOCK POST /dispatch/assign",
    reason: "Attach the verified crew and response window.",
    result: "Crew 12 assigned",
    status: "good",
    system: "dispatch",
  },
  {
    step: "final",
    call: "MOCK POST /claims/intake-packet",
    reason: "Prepare a structured evidence checklist without inventing claim facts.",
    result: "Evidence packet opened",
    status: "good",
    system: "claims",
  },
];

const scenarios: Scenario[] = [
  {
    id: "booked",
    title: "After-hours water loss",
    subtitle: "Verified job and crew assignment",
    request:
      "Water is coming through our kitchen ceiling at 1407 Ashwood Drive. It started about an hour ago. The breaker is off and everyone is safe. We need someone tonight.",
    events: bookedEvents,
    outcome: {
      type: "BOOKED",
      title: "Loss response booked",
      detail:
        "A verified water-loss job is created with a real crew window and an evidence checklist for the field team.",
      status: "good",
      packet: {
        Job: "RST-2048",
        Property: "1407 Ashwood Dr",
        Loss: "Active water intrusion",
        Safety: "Screen passed",
        Response: "Crew 12 - 60 to 90 minutes",
        Updates: "SMS allowed",
        Evidence: "Field checklist opened",
      },
    },
  },
  {
    id: "ambiguous",
    title: "Ambiguous property",
    subtitle: "Clarify instead of guessing",
    request: "There is water everywhere at the rental. Can someone come now?",
    events: [
      ...baseEvents,
      {
        step: "checks",
        call: "MOCK GET /crm/properties",
        reason: "The caller has more than one property in the CRM.",
        result: "Three possible properties",
        status: "warn",
        system: "crm",
      },
      {
        step: "gate",
        call: "POST /decision/gate",
        reason: "A service address and safety answers are required before dispatch.",
        result: "Clarification required - no write",
        status: "warn",
      },
    ],
    outcome: {
      type: "CLARIFY",
      title: "Which property needs help?",
      detail:
        "The workflow asks for the service address and immediate hazards instead of selecting a property or promising a crew.",
      status: "warn",
      packet: {
        "Possible properties": "3",
        "CRM write": "None",
        "Dispatch write": "None",
        "Next question": "Address and active safety hazards",
      },
    },
  },
  {
    id: "hazard",
    title: "Immediate safety hazard",
    subtitle: "Escalate before ordinary intake",
    request:
      "The basement is flooding and we can see sparks near the electrical panel at 812 Cedar Lane.",
    events: [
      ...baseEvents,
      {
        step: "checks",
        call: "MOCK POST /coverage/safety-screen",
        reason: "Electrical arcing with standing water requires an emergency response boundary.",
        result: "Immediate hazard detected",
        status: "bad",
        system: "coverage",
      },
      {
        step: "gate",
        call: "POST /decision/gate",
        reason: "Routine booking must stop while life-safety risk is unresolved.",
        result: "Automated booking blocked",
        status: "bad",
      },
      {
        step: "final",
        call: "MOCK POST /operations/emergency-handoff",
        reason: "Preserve the transcript and assign urgent human ownership.",
        result: "Emergency handoff opened",
        status: "warn",
        system: "routing",
      },
    ],
    outcome: {
      type: "BLOCKED",
      title: "Safety escalation required",
      detail:
        "The system gives no routine arrival promise. It preserves the hazard details and routes the case for immediate human handling.",
      status: "bad",
      packet: {
        Hazard: "Standing water near electrical sparks",
        "Routine booking": "Blocked",
        "CRM job": "None",
        Owner: "Emergency response queue",
      },
    },
  },
  {
    id: "outage",
    title: "Dispatch system outage",
    subtitle: "No invented arrival window",
    request:
      "A supply line burst at 55 Ridgeview Court. The water is shut off and the property is safe. We need mitigation tonight.",
    forceOffline: "dispatch",
    events: [],
    outcome: {
      type: "HANDOFF",
      title: "Dispatch handoff created",
      detail: "Capacity cannot be verified, so the workflow does not promise an arrival time.",
      status: "warn",
      packet: {},
    },
  },
  {
    id: "duplicate",
    title: "Repeat call for open loss",
    subtitle: "Link context, do not duplicate work",
    request:
      "I already called about 1407 Ashwood Drive. The ceiling leak is getting worse. Is the crew still coming?",
    events: [
      ...baseEvents,
      {
        step: "checks",
        call: "MOCK GET /crm/open-jobs",
        reason: "Search the normalized property and caller before creating a job.",
        result: "Open job RST-2048 found",
        status: "good",
        system: "crm",
      },
      {
        step: "checks",
        call: "MOCK GET /dispatch/status/RST-2048",
        reason: "Retrieve the authoritative crew status.",
        result: "Crew 12 en route - 42 minutes",
        status: "good",
        system: "dispatch",
      },
      {
        step: "gate",
        call: "POST /decision/gate",
        reason: "The existing job is the source of truth for this property and loss.",
        result: "Duplicate creation prevented",
        status: "good",
      },
      {
        step: "final",
        call: "MOCK POST /crm/jobs/RST-2048/note",
        reason: "Add the changed condition to the existing operational record.",
        result: "Escalation note added",
        status: "good",
        system: "crm",
      },
    ],
    outcome: {
      type: "DUPLICATE",
      title: "Existing job updated",
      detail:
        "No second job is created. The worsening condition is attached to RST-2048 and the verified crew status is returned.",
      status: "good",
      packet: {
        Job: "RST-2048",
        Status: "Crew en route",
        ETA: "42 minutes",
        "New job": "None",
        Update: "Escalation note stored",
      },
    },
  },
  {
    id: "outside-area",
    title: "Outside service territory",
    subtitle: "Owned referral, not a dead end",
    request:
      "We have storm water entering a retail suite at 909 Market Street in San Antonio. Can you send a crew?",
    events: [
      ...baseEvents,
      {
        step: "checks",
        call: "MOCK POST /coverage/territory",
        reason: "Verify that the property is inside an active response territory.",
        result: "Outside configured service area",
        status: "bad",
        system: "coverage",
      },
      {
        step: "gate",
        call: "POST /decision/gate",
        reason: "A crew cannot be promised outside the supported territory.",
        result: "Internal dispatch blocked",
        status: "bad",
      },
      {
        step: "final",
        call: "MOCK POST /operations/referral-handoff",
        reason: "Preserve context and assign the referral rather than dropping the caller.",
        result: "Partner-referral handoff created",
        status: "warn",
        system: "routing",
      },
    ],
    outcome: {
      type: "HANDOFF",
      title: "Referral handoff created",
      detail:
        "The request is not misrepresented as bookable. A human owner receives the caller, property, and loss details for referral handling.",
      status: "warn",
      packet: {
        Property: "909 Market St - San Antonio",
        Coverage: "Outside configured territory",
        "Dispatch write": "None",
        Owner: "Partner referral queue",
      },
    },
  },
  {
    id: "capacity",
    title: "No verified crew capacity",
    subtitle: "Pending review, not a false booking",
    request:
      "A tree opened the roof at 222 Westlake Drive. There is no active electrical hazard, but rain is entering the home.",
    events: [
      ...baseEvents,
      {
        step: "checks",
        call: "MOCK POST /coverage/qualify",
        reason: "Confirm supported loss and screen for immediate hazards.",
        result: "Emergency roof loss accepted",
        status: "good",
        system: "coverage",
      },
      {
        step: "checks",
        call: "MOCK GET /dispatch/capacity",
        reason: "A real crew window is required before confirmation.",
        result: "No verified crew capacity",
        status: "warn",
        system: "dispatch",
      },
      {
        step: "gate",
        call: "POST /decision/gate",
        reason: "The request is qualified, but no response promise can be verified.",
        result: "Human dispatch review required",
        status: "warn",
      },
      {
        step: "final",
        call: "MOCK POST /operations/dispatch-handoff",
        reason: "Give the qualified emergency request an owner and response clock.",
        result: "Priority handoff created",
        status: "warn",
        system: "routing",
      },
    ],
    outcome: {
      type: "HANDOFF",
      title: "Priority dispatch review opened",
      detail:
        "The loss is qualified, but the caller receives no fabricated ETA. A dispatcher owns the next decision.",
      status: "warn",
      packet: {
        Loss: "Emergency roof opening",
        Capacity: "Unverified",
        "Crew promise": "None",
        Owner: "Priority dispatcher",
      },
    },
  },
  {
    id: "claim-gap",
    title: "Missing claim evidence",
    subtitle: "Book response, flag documentation gap",
    request:
      "The washing-machine line failed at 76 Willow Bend. The water is off and the rooms are safe. I have insurance but do not have the claim number yet.",
    events: [
      ...bookedEvents.slice(0, 7),
      {
        step: "final",
        call: "MOCK POST /crm/jobs",
        reason: "Create the verified mitigation response independently of unknown claim facts.",
        result: "Job RST-2051 created",
        status: "good",
        system: "crm",
      },
      {
        step: "final",
        call: "MOCK POST /claims/intake-packet",
        reason: "Record missing evidence without guessing a carrier or claim number.",
        result: "Claim-document follow-up opened",
        status: "warn",
        system: "claims",
      },
    ],
    outcome: {
      type: "BOOKED",
      title: "Response booked; evidence follow-up opened",
      detail:
        "Mitigation is not delayed, and the absent claim number is carried forward as owned work rather than invented.",
      status: "good",
      packet: {
        Job: "RST-2051",
        Property: "76 Willow Bend",
        Response: "Booked",
        "Claim number": "Not provided",
        "Follow-up": "Documentation queue",
      },
    },
  },
];

const evaluationLabels = [
  "Complete water-loss booking",
  "Missing property clarification",
  "Unknown loss type clarification",
  "Electrical hazard escalation",
  "CRM outage blocks writes",
  "Dispatch outage prevents false ETA",
  "Repeat call does not create a duplicate",
  "Existing job receives the new evidence",
  "Outside territory creates a referral handoff",
  "No crew capacity creates owned review",
  "Unsafe occupancy blocks ordinary intake",
  "Missing caller identity requests clarification",
  "Partial transcript does not fabricate fields",
  "Low-confidence parse blocks business action",
  "Parser provider error creates no write",
  "Contact restrictions are respected",
  "Repeated request remains idempotent",
  "Audit packet preserves source evidence",
];

function customScenario(request: string): Scenario {
  const lower = request.toLowerCase();
  const hasAddress = /\b\d{1,6}\s+[a-z]/i.test(request);

  if (lower.includes("spark") || lower.includes("electrical") || lower.includes("smoke")) {
    return { ...scenarios[2], id: "custom", title: "Custom hazard report", request };
  }
  if (lower.includes("already called") || lower.includes("crew still")) {
    return { ...scenarios[4], id: "custom", title: "Custom repeat call", request };
  }
  if (lower.includes("san antonio") || lower.includes("outside area")) {
    return { ...scenarios[5], id: "custom", title: "Custom coverage check", request };
  }
  if (!hasAddress) {
    return { ...scenarios[1], id: "custom", title: "Custom incomplete intake", request };
  }
  return { ...scenarios[0], id: "custom", title: "Custom loss intake", request };
}

function statusLabel(status: Status) {
  if (status === "good") return "verified";
  if (status === "warn") return "attention";
  if (status === "bad") return "blocked";
  return "observed";
}

export default function Home() {
  const [selectedId, setSelectedId] = useState("booked");
  const [customRequest, setCustomRequest] = useState("");
  const [online, setOnline] = useState<Record<SystemKey, boolean>>({
    crm: true,
    coverage: true,
    dispatch: true,
    claims: true,
    consent: true,
    routing: true,
  });
  const [visibleEvents, setVisibleEvents] = useState<TraceEvent[]>([]);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [running, setRunning] = useState(false);
  const [inspector, setInspector] = useState<{
    title: string;
    rows: Record<string, string>;
  }>({
    title: "Ready for a loss report",
    rows: {
      Purpose: "Select a scenario and run the workflow.",
      Boundary: "Synthetic records and mock integrations only.",
    },
  });
  const [evalOpen, setEvalOpen] = useState(false);

  const selected = useMemo(() => {
    if (customRequest.trim()) return customScenario(customRequest.trim());
    return scenarios.find((scenario) => scenario.id === selectedId) ?? scenarios[0];
  }, [customRequest, selectedId]);

  const latestBySystem = useMemo(() => {
    const map = new Map<SystemKey, TraceEvent>();
    for (const event of visibleEvents) {
      if (event.system) map.set(event.system, event);
    }
    return map;
  }, [visibleEvents]);

  async function run() {
    if (running) return;
    setRunning(true);
    setVisibleEvents([]);
    setOutcome(null);
    setEvalOpen(false);

    const forcedKey = selected.forceOffline;
    const manuallyOffline = systems.find((system) => !online[system.key])?.key;
    const offlineKey = forcedKey ?? manuallyOffline;
    const events = offlineKey
      ? [
          ...baseEvents,
          {
            step: "checks",
            call: `MOCK GET /integrations/${offlineKey}`,
            reason: "A required operational dependency must be available before a business promise or write.",
            result: "OFFLINE",
            status: "bad" as Status,
            system: offlineKey,
          },
          {
            step: "gate",
            call: "POST /decision/gate",
            reason: "A required dependency is unavailable.",
            result: "Automation stopped",
            status: "bad" as Status,
          },
          {
            step: "final",
            call: "MOCK POST /operations/handoff",
            reason: "Preserve the caller's context and assign recovery work.",
            result: "Restoration intake handoff created",
            status: "warn" as Status,
            system: "routing" as SystemKey,
          },
        ]
      : selected.events;

    for (const event of events) {
      setVisibleEvents((current) => [...current, event]);
      setInspector({
        title: event.call,
        rows: {
          Step: event.step,
          Why: event.reason,
          Result: event.result,
          Status: statusLabel(event.status),
        },
      });
      await new Promise((resolve) => setTimeout(resolve, 170));
    }

    const finalOutcome: Outcome = offlineKey
      ? {
          type: "HANDOFF",
          title: "Intake handoff created",
          detail: `${systems.find((system) => system.key === offlineKey)?.label} is unavailable, so no booking, arrival time, or downstream write is reported as complete.`,
          status: "warn",
          packet: {
            Dependency: systems.find((system) => system.key === offlineKey)?.label ?? offlineKey,
            Status: "Unavailable",
            "Business write": "None",
            Recovery: "Intake coordinator owns reconciliation",
          },
        }
      : selected.outcome;

    setOutcome(finalOutcome);
    setInspector({ title: finalOutcome.title, rows: finalOutcome.packet });
    setRunning(false);
  }

  function selectScenario(id: string) {
    setSelectedId(id);
    setCustomRequest("");
    setVisibleEvents([]);
    setOutcome(null);
    setEvalOpen(false);
  }

  function toggleSystem(key: SystemKey) {
    setOnline((current) => ({ ...current, [key]: !current[key] }));
    setVisibleEvents([]);
    setOutcome(null);
  }

  function showEvaluations() {
    setEvalOpen(true);
    setOutcome(null);
    setVisibleEvents([]);
    setInspector({
      title: "18 restoration-intake regression cases",
      rows: Object.fromEntries(
        evaluationLabels.map((label, index) => [
          String(index + 1).padStart(2, "0"),
          `${label} - PASS`,
        ]),
      ),
    });
  }

  return (
    <main className="appShell">
      <header className="hero">
        <div className="heroCopy">
          <div className="eyebrow">Restoration intake edition - independent portfolio prototype</div>
          <h1>AI Operations Reliability Lab</h1>
          <p>
            A synthetic after-hours restoration workflow that turns a caller&apos;s messy loss report into a verified booking, clarification, safety escalation, duplicate-safe update, or owned human handoff.
          </p>
          <div className="principle">
            <span>Operating principle</span>
            <strong>
              A model may interpret the call. Deterministic systems decide whether the company can promise or write an operational action.
            </strong>
          </div>
        </div>
        <div className="heroMeta">
          <div className="statusRow">
            <span>Synthetic restoration data</span>
            <span>Mock CRM + dispatch</span>
            <span>18 regression cases</span>
          </div>
          <div className="heroActions">
            <button className="secondaryButton" onClick={showEvaluations}>
              View evaluation coverage
            </button>
            <button className="primaryButton" onClick={run} disabled={running}>
              {running ? "Running trace..." : "Run selected workflow"}
            </button>
          </div>
        </div>
      </header>

      <section className="workspace">
        <aside className="leftRail">
          <section className="panel scenarioPanel">
            <div className="panelHeader">
              <div>
                <span className="panelKicker">Choose a case</span>
                <h2>Restoration scenarios</h2>
              </div>
              <span className="countBadge">08</span>
            </div>
            <div className="scenarioList">
              {scenarios.map((scenario) => (
                <button
                  key={scenario.id}
                  className={`scenarioButton ${scenario.id === selectedId && !customRequest ? "active" : ""}`}
                  onClick={() => selectScenario(scenario.id)}
                >
                  <span>{scenario.title}</span>
                  <small>{scenario.subtitle}</small>
                </button>
              ))}
            </div>
          </section>

          <section className="panel customPanel">
            <div className="panelHeader compact">
              <div>
                <span className="panelKicker">Optional</span>
                <h2>Custom loss report</h2>
              </div>
            </div>
            <textarea
              aria-label="Custom restoration loss report"
              value={customRequest}
              onChange={(event) => {
                setCustomRequest(event.target.value);
                setVisibleEvents([]);
                setOutcome(null);
              }}
              placeholder="Describe a fictional caller, property, loss, and immediate hazards..."
            />
            <p className="helperText">
              This public build uses deterministic parsing so every demonstration is reproducible and creates no external API cost.
            </p>
          </section>
        </aside>

        <section className="centerStage">
          <section className="panel requestPanel">
            <div className="requestTopline">
              <span>Caller loss report</span>
              <span className="parserBadge">deterministic transcript parser</span>
            </div>
            <blockquote>{selected.request}</blockquote>
          </section>

          <section className="panel tracePanel">
            <div className="panelHeader">
              <div>
                <span className="panelKicker">Execution model</span>
                <h2>From language to controlled action</h2>
              </div>
              <span className={`runBadge ${running ? "running" : ""}`}>
                {running ? `${visibleEvents.length} checks` : outcome ? "trace complete" : "ready"}
              </span>
            </div>

            <div className="stepGrid">
              {steps.map((step) => {
                const observed = visibleEvents.some((event) => event.step === step.id);
                const status = visibleEvents.filter((event) => event.step === step.id).at(-1)?.status;
                return (
                  <button
                    key={step.id}
                    className={`stepCard ${observed ? "observed" : ""} ${status ?? ""}`}
                    onClick={() =>
                      setInspector({
                        title: step.title,
                        rows: { Sequence: step.number, Responsibility: step.description },
                      })
                    }
                  >
                    <span>{step.number}</span>
                    <strong>{step.title}</strong>
                    <small>{step.description}</small>
                  </button>
                );
              })}
            </div>

            <div className="systemGrid">
              {systems.map((system) => {
                const event = latestBySystem.get(system.key);
                const isOnline = online[system.key] && selected.forceOffline !== system.key;
                return (
                  <button
                    key={system.key}
                    aria-pressed={!isOnline}
                    className={`systemCard ${!isOnline ? "offline" : ""} ${event ? event.status : ""}`}
                    onClick={() => toggleSystem(system.key)}
                  >
                    <div className="systemTopline">
                      <strong>{system.label}</strong>
                      <span>{isOnline ? "online" : "offline"}</span>
                    </div>
                    <p>{event?.result ?? system.description}</p>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="panel eventPanel">
            <div className="panelHeader compact">
              <div>
                <span className="panelKicker">Evidence</span>
                <h2>Decision trace</h2>
              </div>
              <span className="countBadge">{String(visibleEvents.length).padStart(2, "0")}</span>
            </div>
            <div className="eventList">
              {visibleEvents.length ? (
                visibleEvents.map((event, index) => (
                  <button
                    key={`${event.call}-${index}`}
                    className={`eventRow ${event.status}`}
                    onClick={() =>
                      setInspector({
                        title: event.call,
                        rows: {
                          Step: event.step,
                          Why: event.reason,
                          Result: event.result,
                          Status: statusLabel(event.status),
                        },
                      })
                    }
                  >
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <div>
                      <strong>{event.call}</strong>
                      <small>{event.reason}</small>
                    </div>
                    <em>{event.result}</em>
                  </button>
                ))
              ) : (
                <div className="emptyState">
                  Run a scenario to reveal every source-system check and decision.
                </div>
              )}
            </div>
          </section>
        </section>

        <aside className="rightRail">
          <section className={`panel outcomePanel ${outcome?.status ?? ""}`} aria-live="polite">
            <span className="panelKicker">Final decision</span>
            <h2>{outcome?.title ?? "No outcome yet"}</h2>
            <p>
              {outcome?.detail ?? "The verified booking, clarification, block, duplicate-safe update, or human handoff will appear here."}
            </p>
            {outcome && <span className="outcomeType">{outcome.type}</span>}
          </section>

          <section className="panel inspectorPanel">
            <div className="panelHeader compact">
              <div>
                <span className="panelKicker">{evalOpen ? "Verification suite" : "Inspector"}</span>
                <h2>{inspector.title}</h2>
              </div>
            </div>
            <dl>
              {Object.entries(inspector.rows).map(([label, value]) => (
                <div key={`${label}-${value}`}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          </section>

          <section className="panel boundaryPanel">
            <span className="panelKicker">Prototype boundary</span>
            <h2>Relevant without pretending</h2>
            <p>
              This is a browser-based decision workflow, not a production voice agent. It uses no real restoration company, caller, customer, claim, vendor API, product screen, prompt, or proprietary architecture.
            </p>
            <a
              href="https://github.com/VarshaThondalapally/ai-operations-reliability-lab"
              target="_blank"
              rel="noreferrer"
            >
              Read the implementation <span aria-hidden="true">↗</span>
            </a>
          </section>
        </aside>
      </section>

      <footer>
        <p>
          Built to demonstrate customer-facing AI product work: understand the operational problem, verify business truth, prevent unsafe writes, and leave failed automation with a human owner.
        </p>
        <span>React + TypeScript interface - deterministic mock adapters - regression-oriented scenarios</span>
      </footer>
    </main>
  );
}
