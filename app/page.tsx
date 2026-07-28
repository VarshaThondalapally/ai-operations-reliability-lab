"use client";

import { useMemo, useState } from "react";

type Status = "good" | "warn" | "bad" | "info";
type SystemKey =
  | "workforce"
  | "scheduler"
  | "carePlan"
  | "compliance"
  | "emr"
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
  type: "REASSIGNED" | "CLARIFY" | "HANDOFF" | "BLOCKED" | "DUPLICATE";
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
    key: "workforce",
    label: "Caregiver directory",
    description: "Identity, qualifications, zones, and contact permission",
  },
  {
    key: "scheduler",
    label: "Shift scheduler",
    description: "Assigned visits, availability, and conflicts",
  },
  {
    key: "carePlan",
    label: "Client care plan",
    description: "Service needs and qualification constraints",
  },
  {
    key: "compliance",
    label: "Qualification rules",
    description: "Deterministic eligibility before reassignment",
  },
  {
    key: "emr",
    label: "Mock EMR",
    description: "Assignment and operational-note updates",
  },
  {
    key: "routing",
    label: "Operations escalation",
    description: "Human ownership when automation stops",
  },
];

const steps = [
  {
    id: "request",
    number: "01",
    title: "Request received",
    description: "Preserve raw operations language",
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
    description: "Select the evidence required",
  },
  {
    id: "checks",
    number: "04",
    title: "Systems checked",
    description: "Verify operational sources of truth",
  },
  {
    id: "gate",
    number: "05",
    title: "Decision gate",
    description: "Complete, clarify, block, or escalate",
  },
  {
    id: "final",
    number: "06",
    title: "Action + visibility",
    description: "Write safely or create an owned handoff",
  },
];

const baseEvents: TraceEvent[] = [
  {
    step: "request",
    call: "INBOUND_OPERATION",
    reason: "Preserve the exact coordinator or caregiver language.",
    result: "Request stored",
    status: "good",
  },
  {
    step: "intent",
    call: "POST /intent/parse",
    reason: "Convert unstructured language into typed operational fields.",
    result: "Structured intent created",
    status: "good",
  },
  {
    step: "route",
    call: "POST /workflow/route",
    reason: "Choose the shift-coverage checks required for this request.",
    result: "Coverage workflow selected",
    status: "good",
  },
];

const verifiedEvents: TraceEvent[] = [
  ...baseEvents,
  {
    step: "checks",
    call: "MOCK GET /workforce/caregiver",
    reason: "Resolve the original caregiver.",
    result: "Maya Patel verified",
    status: "good",
    system: "workforce",
  },
  {
    step: "checks",
    call: "MOCK GET /care-plan/client",
    reason: "Resolve the client and required service.",
    result: "Eleanor Price · personal care",
    status: "good",
    system: "carePlan",
  },
  {
    step: "checks",
    call: "MOCK GET /scheduler/shift",
    reason: "Identify the exact assigned visit.",
    result: "Tomorrow · 2:00 PM",
    status: "good",
    system: "scheduler",
  },
  {
    step: "checks",
    call: "MOCK GET /workforce/replacement",
    reason: "Resolve the proposed replacement.",
    result: "Devon Brooks verified",
    status: "good",
    system: "workforce",
  },
  {
    step: "checks",
    call: "MOCK POST /compliance/eligibility",
    reason: "Check qualifications and service zone.",
    result: "Eligible",
    status: "good",
    system: "compliance",
  },
  {
    step: "checks",
    call: "MOCK GET /scheduler/conflicts",
    reason: "Prevent overlapping assignments.",
    result: "Available",
    status: "good",
    system: "scheduler",
  },
  {
    step: "gate",
    call: "POST /decision/gate",
    reason: "Identity, shift, eligibility, availability, and acceptance passed.",
    result: "Reassignment allowed",
    status: "good",
  },
  {
    step: "final",
    call: "MOCK POST /emr/shift-assignment",
    reason: "Write only the verified assignment.",
    result: "Reassignment #2 completed",
    status: "good",
    system: "emr",
  },
  {
    step: "final",
    call: "MOCK POST /operations/audit-log",
    reason: "Preserve the inputs and final action.",
    result: "Audit record stored",
    status: "good",
    system: "emr",
  },
];

const scenarios: Scenario[] = [
  {
    id: "coverage",
    title: "Shift covered safely",
    subtitle: "Verified reassignment",
    request:
      "Maya called out of Eleanor's personal-care visit tomorrow at 2 PM. Devon accepted the replacement.",
    events: verifiedEvents,
    outcome: {
      type: "REASSIGNED",
      title: "Shift reassigned safely",
      detail:
        "Devon Brooks is assigned to Eleanor Price's personal-care visit tomorrow at 2:00 PM.",
      status: "good",
      packet: {
        Client: "Eleanor Price",
        Shift: "Tomorrow · 2:00 PM",
        Service: "Personal care",
        Previous: "Maya Patel",
        Replacement: "Devon Brooks",
        Qualification: "Verified",
        Conflict: "None",
        Acceptance: "Confirmed",
      },
    },
  },
  {
    id: "ambiguous",
    title: "Ambiguous call-out",
    subtitle: "Clarify instead of guessing",
    request: "Maya called out tomorrow.",
    events: [
      ...baseEvents,
      {
        step: "checks",
        call: "MOCK GET /workforce/caregiver",
        reason: "Resolve the caregiver before searching assigned visits.",
        result: "Maya Patel verified",
        status: "good",
        system: "workforce",
      },
      {
        step: "gate",
        call: "POST /decision/gate",
        reason: "More than one visit matches the incomplete request.",
        result: "Clarification required · no write",
        status: "warn",
      },
    ],
    outcome: {
      type: "CLARIFY",
      title: "Which client visit is affected?",
      detail:
        "Maya has multiple visits tomorrow. The workflow presents the matching shifts instead of choosing one.",
      status: "warn",
      packet: {
        Caregiver: "Maya Patel",
        "Matching shifts": "3",
        "Schedule write": "None",
        "Next action": "Ask for client and time",
      },
    },
  },
  {
    id: "outage",
    title: "Scheduler outage",
    subtitle: "Failure becomes owned work",
    request:
      "Maya called out of Eleanor's personal-care visit tomorrow at 2 PM. Devon accepted the replacement.",
    forceOffline: "scheduler",
    events: [
      ...baseEvents,
      {
        step: "checks",
        call: "MOCK GET /integrations/scheduler",
        reason: "The schedule must be readable before any change is reported.",
        result: "OFFLINE",
        status: "bad",
        system: "scheduler",
      },
      {
        step: "gate",
        call: "POST /decision/gate",
        reason: "A required dependency is unavailable.",
        result: "Automation stopped",
        status: "bad",
      },
      {
        step: "final",
        call: "MOCK POST /operations/handoff",
        reason: "Preserve context and assign recovery work.",
        result: "Care-coordination handoff created",
        status: "warn",
        system: "routing",
      },
    ],
    outcome: {
      type: "HANDOFF",
      title: "Operations handoff created",
      detail:
        "The scheduler is unavailable, so the workflow does not claim that the shift was reassigned.",
      status: "warn",
      packet: {
        Queue: "Care coordination",
        Reason: "Shift scheduler unavailable",
        "Schedule write": "None",
        Context: "Original request preserved",
      },
    },
  },
  {
    id: "qualification",
    title: "Qualification mismatch",
    subtitle: "Unsafe replacement is blocked",
    request:
      "Maya called out of Robert's medication-reminder visit tomorrow at 10 AM. Jordan accepted the replacement.",
    events: [
      ...baseEvents,
      {
        step: "checks",
        call: "MOCK GET /scheduler/shift",
        reason: "Verify the exact visit.",
        result: "Robert Chen · medication reminder",
        status: "good",
        system: "scheduler",
      },
      {
        step: "checks",
        call: "MOCK POST /compliance/eligibility",
        reason: "Compare required and verified qualifications.",
        result: "Missing medication-reminder qualification",
        status: "bad",
        system: "compliance",
      },
      {
        step: "gate",
        call: "POST /decision/gate",
        reason: "Care-plan requirements are not satisfied.",
        result: "Assignment blocked",
        status: "bad",
      },
      {
        step: "final",
        call: "MOCK POST /operations/handoff",
        reason: "Give the blocked coverage request an owner.",
        result: "Coordinator handoff created",
        status: "warn",
        system: "routing",
      },
    ],
    outcome: {
      type: "BLOCKED",
      title: "Replacement blocked",
      detail:
        "Jordan Lee cannot cover this visit because the required medication-reminder qualification is missing.",
      status: "bad",
      packet: {
        Client: "Robert Chen",
        Requirement: "Medication reminder",
        Replacement: "Jordan Lee",
        Eligibility: "Failed",
        "Schedule write": "None",
      },
    },
  },
  {
    id: "conflict",
    title: "Schedule conflict",
    subtitle: "No double assignment",
    request:
      "Maya called out of Robert's medication-reminder visit tomorrow at 10 AM. Devon accepted the replacement.",
    events: [
      ...baseEvents,
      {
        step: "checks",
        call: "MOCK POST /compliance/eligibility",
        reason: "Verify required qualifications.",
        result: "Eligible",
        status: "good",
        system: "compliance",
      },
      {
        step: "checks",
        call: "MOCK GET /scheduler/conflicts",
        reason: "Prevent overlapping assignments.",
        result: "Conflict at 10:00 AM",
        status: "bad",
        system: "scheduler",
      },
      {
        step: "gate",
        call: "POST /decision/gate",
        reason: "The replacement is already scheduled.",
        result: "Assignment blocked",
        status: "bad",
      },
    ],
    outcome: {
      type: "BLOCKED",
      title: "Schedule conflict detected",
      detail:
        "Devon Brooks is qualified but already assigned to another visit at 10:00 AM.",
      status: "bad",
      packet: {
        Replacement: "Devon Brooks",
        Qualification: "Verified",
        Availability: "Conflict",
        "Schedule write": "None",
      },
    },
  },
  {
    id: "candidates",
    title: "Coverage candidates",
    subtitle: "Filter without false assignment",
    request:
      "Maya called out of Eleanor's personal-care visit tomorrow at 2 PM. Find a qualified replacement.",
    events: [
      ...baseEvents,
      {
        step: "checks",
        call: "MOCK POST /coverage/candidates",
        reason:
          "Filter by qualifications, zone, availability, and outreach permission.",
        result: "Devon Brooks",
        status: "good",
        system: "compliance",
      },
      {
        step: "gate",
        call: "POST /decision/gate",
        reason: "Eligibility does not prove acceptance.",
        result: "Human confirmation required",
        status: "warn",
      },
      {
        step: "final",
        call: "MOCK POST /operations/handoff",
        reason: "Provide candidates and preserve human confirmation.",
        result: "Coverage handoff created",
        status: "warn",
        system: "routing",
      },
    ],
    outcome: {
      type: "HANDOFF",
      title: "Qualified candidate prepared",
      detail:
        "Devon Brooks matches the visit, but no assignment is written until acceptance is confirmed.",
      status: "warn",
      packet: {
        Client: "Eleanor Price",
        Candidate: "Devon Brooks",
        Qualification: "Verified",
        Acceptance: "Pending",
        "Schedule write": "None",
      },
    },
  },
  {
    id: "duplicate",
    title: "Duplicate update",
    subtitle: "Existing state is reused",
    request:
      "Maya called out of Eleanor's personal-care visit tomorrow at 4 PM. Devon accepted the replacement.",
    events: [
      ...baseEvents,
      {
        step: "checks",
        call: "MOCK GET /scheduler/reassignments",
        reason: "Detect completed matching work before retrying.",
        result: "Existing reassignment #1",
        status: "good",
        system: "scheduler",
      },
      {
        step: "gate",
        call: "POST /decision/gate",
        reason: "The requested final state already exists.",
        result: "Duplicate write prevented",
        status: "good",
      },
    ],
    outcome: {
      type: "DUPLICATE",
      title: "Existing reassignment confirmed",
      detail:
        "Devon Brooks is already assigned to the visit. No duplicate record is created.",
      status: "good",
      packet: {
        Client: "Eleanor Price",
        Replacement: "Devon Brooks",
        Existing: "Reassignment #1",
        "New write": "None",
      },
    },
  },
  {
    id: "emr",
    title: "EMR unavailable",
    subtitle: "No false completion",
    request:
      "Maya called out of Eleanor's personal-care visit tomorrow at 2 PM. Devon accepted the replacement.",
    forceOffline: "emr",
    events: [
      ...baseEvents,
      {
        step: "checks",
        call: "MOCK GET /integrations/emr",
        reason: "The final source system must accept the write.",
        result: "OFFLINE",
        status: "bad",
        system: "emr",
      },
      {
        step: "gate",
        call: "POST /decision/gate",
        reason: "The assignment cannot be durably recorded.",
        result: "Automation stopped",
        status: "bad",
      },
      {
        step: "final",
        call: "MOCK POST /operations/handoff",
        reason: "Route the unresolved write with complete context.",
        result: "EMR recovery handoff created",
        status: "warn",
        system: "routing",
      },
    ],
    outcome: {
      type: "HANDOFF",
      title: "EMR recovery handoff created",
      detail:
        "The workflow does not report success while the system of record is unavailable.",
      status: "warn",
      packet: {
        Dependency: "Mock EMR",
        Status: "Unavailable",
        "Schedule write": "None",
        Recovery: "Coordinator owns reconciliation",
      },
    },
  },
  {
    id: "urgent",
    title: "Urgent escalation",
    subtitle: "Human ownership first",
    request:
      "Urgent: Maya called out of Eleanor's visit tomorrow at 2 PM. The family mentioned a hospital risk.",
    events: [
      ...baseEvents,
      {
        step: "gate",
        call: "POST /decision/gate",
        reason: "The request contains a high-risk signal.",
        result: "Automation stopped",
        status: "bad",
      },
      {
        step: "final",
        call: "MOCK POST /operations/handoff",
        reason: "Escalate immediately with the original context.",
        result: "Urgent coordinator handoff created",
        status: "warn",
        system: "routing",
      },
    ],
    outcome: {
      type: "HANDOFF",
      title: "Urgent human escalation",
      detail:
        "The workflow preserves the request and routes it to a coordinator before attempting automation.",
      status: "warn",
      packet: {
        Priority: "Urgent",
        Queue: "Care coordination",
        Context: "Original request preserved",
        "Schedule write": "None",
      },
    },
  },
];

const evaluationLabels = [
  "Verified reassignment",
  "Ambiguous call-out",
  "Scheduler outage",
  "Qualification mismatch",
  "Replacement conflict",
  "Candidate filtering",
  "Seeded duplicate",
  "EMR outage",
  "Urgent escalation",
  "Missing caregiver",
  "Unknown caregiver",
  "Unknown client",
  "Missing shift time",
  "Unknown replacement",
  "Acceptance missing",
  "Low-confidence parse",
  "Parser outage",
  "Repeated request",
];

function customScenario(request: string): Scenario {
  const lower = request.toLowerCase();
  if (!lower.includes("maya")) {
    return {
      id: "custom",
      title: "Custom request",
      subtitle: "Missing identity",
      request,
      events: [
        ...baseEvents,
        {
          step: "gate",
          call: "POST /decision/gate",
          reason: "The original caregiver is not uniquely identified.",
          result: "Clarification required",
          status: "warn",
        },
      ],
      outcome: {
        type: "CLARIFY",
        title: "Which caregiver called out?",
        detail: "Caregiver identity is required before assigned shifts can be searched.",
        status: "warn",
        packet: { "Schedule write": "None", "Next action": "Ask for caregiver" },
      },
    };
  }
  if (!lower.includes("eleanor") && !lower.includes("robert")) {
    return scenarios[1];
  }
  if (lower.includes("jordan") && lower.includes("medication")) {
    return { ...scenarios[3], request };
  }
  if (lower.includes("devon") && lower.includes("10 am")) {
    return { ...scenarios[4], request };
  }
  if (lower.includes("devon") && lower.includes("accepted")) {
    return { ...scenarios[0], request };
  }
  return { ...scenarios[5], request };
}

function statusLabel(status: Status) {
  if (status === "good") return "verified";
  if (status === "warn") return "attention";
  if (status === "bad") return "blocked";
  return "observed";
}

export default function Home() {
  const [selectedId, setSelectedId] = useState("coverage");
  const [customRequest, setCustomRequest] = useState("");
  const [online, setOnline] = useState<Record<SystemKey, boolean>>({
    workforce: true,
    scheduler: true,
    carePlan: true,
    compliance: true,
    emr: true,
    routing: true,
  });
  const [visibleEvents, setVisibleEvents] = useState<TraceEvent[]>([]);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [running, setRunning] = useState(false);
  const [inspector, setInspector] = useState<{
    title: string;
    rows: Record<string, string>;
  }>({
    title: "Ready for a request",
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
            reason:
              "A required operational dependency must be available before a schedule write.",
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
            reason: "Preserve context and assign recovery work.",
            result: "Operations handoff created",
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
      await new Promise((resolve) => setTimeout(resolve, 190));
    }

    const finalOutcome: Outcome = offlineKey
      ? {
          type: "HANDOFF",
          title: "Operations handoff created",
          detail: `${systems.find((system) => system.key === offlineKey)?.label} is unavailable, so no schedule change is reported as complete.`,
          status: "warn",
          packet: {
            Dependency:
              systems.find((system) => system.key === offlineKey)?.label ??
              offlineKey,
            Status: "Unavailable",
            "Schedule write": "None",
            Recovery: "Coordinator owns reconciliation",
          },
        }
      : selected.outcome;

    setOutcome(finalOutcome);
    setInspector({
      title: finalOutcome.title,
      rows: finalOutcome.packet,
    });
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
      title: "18 regression cases",
      rows: Object.fromEntries(
        evaluationLabels.map((label, index) => [
          `${String(index + 1).padStart(2, "0")}`,
          `${label} · PASS`,
        ]),
      ),
    });
  }

  return (
    <main className="appShell">
      <header className="hero">
        <div className="heroCopy">
          <div className="eyebrow">Independent portfolio prototype</div>
          <h1>AI Operations Reliability Lab</h1>
          <p>
            A fictional home-care shift-coverage workflow that turns messy
            operational language into a verified action—or stops safely when the
            evidence is incomplete.
          </p>
          <div className="principle">
            <span>Operating principle</span>
            <strong>
              The model interprets language. The application decides whether a
              real-world action is allowed.
            </strong>
          </div>
        </div>
        <div className="heroMeta">
          <div className="statusRow">
            <span>Synthetic data</span>
            <span>Mock integrations</span>
            <span>18 regression cases</span>
          </div>
          <div className="heroActions">
            <button className="secondaryButton" onClick={showEvaluations}>
              View evaluation coverage
            </button>
            <button className="primaryButton" onClick={run} disabled={running}>
              {running ? "Running trace…" : "Run selected workflow"}
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
                <h2>Operational scenarios</h2>
              </div>
              <span className="countBadge">09</span>
            </div>
            <div className="scenarioList">
              {scenarios.map((scenario) => (
                <button
                  key={scenario.id}
                  className={`scenarioButton ${
                    scenario.id === selectedId && !customRequest ? "active" : ""
                  }`}
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
                <h2>Custom request</h2>
              </div>
            </div>
            <textarea
              aria-label="Custom operations request"
              value={customRequest}
              onChange={(event) => {
                setCustomRequest(event.target.value);
                setVisibleEvents([]);
                setOutcome(null);
              }}
              placeholder="Describe a fictional caregiver call-out or replacement…"
            />
            <p className="helperText">
              The public build uses a deterministic parser so every demonstration
              is reproducible.
            </p>
          </section>
        </aside>

        <section className="centerStage">
          <section className="panel requestPanel">
            <div className="requestTopline">
              <span>Operations request</span>
              <span className="parserBadge">deterministic parser</span>
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
                {running
                  ? `${visibleEvents.length} checks`
                  : outcome
                    ? "trace complete"
                    : "ready"}
              </span>
            </div>

            <div className="stepGrid">
              {steps.map((step) => {
                const observed = visibleEvents.some(
                  (event) => event.step === step.id,
                );
                const status = visibleEvents
                  .filter((event) => event.step === step.id)
                  .at(-1)?.status;
                return (
                  <button
                    key={step.id}
                    className={`stepCard ${observed ? "observed" : ""} ${
                      status ?? ""
                    }`}
                    onClick={() =>
                      setInspector({
                        title: step.title,
                        rows: {
                          Sequence: step.number,
                          Responsibility: step.description,
                        },
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
                const isOnline =
                  online[system.key] && selected.forceOffline !== system.key;
                return (
                  <button
                    key={system.key}
                    aria-pressed={!isOnline}
                    className={`systemCard ${!isOnline ? "offline" : ""} ${
                      event ? event.status : ""
                    }`}
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
              <span className="countBadge">
                {String(visibleEvents.length).padStart(2, "0")}
              </span>
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
          <section
            className={`panel outcomePanel ${outcome?.status ?? ""}`}
            aria-live="polite"
          >
            <span className="panelKicker">Final decision</span>
            <h2>{outcome?.title ?? "No outcome yet"}</h2>
            <p>
              {outcome?.detail ??
                "The verified action, clarification, block, or human handoff will appear here."}
            </p>
            {outcome && (
              <span className="outcomeType">{outcome.type.replace("_", " ")}</span>
            )}
          </section>

          <section className="panel inspectorPanel">
            <div className="panelHeader compact">
              <div>
                <span className="panelKicker">
                  {evalOpen ? "Verification suite" : "Inspector"}
                </span>
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
            <h2>Deliberately synthetic</h2>
            <p>
              No real agency, patient, caregiver, EMR, phone system, customer
              data, or proprietary architecture is used.
            </p>
            <a
              href="https://github.com/VarshaThondalapally/ai-operations-reliability-lab"
              target="_blank"
              rel="noreferrer"
            >
              Read the implementation
              <span aria-hidden="true">↗</span>
            </a>
          </section>
        </aside>
      </section>

      <footer>
        <p>
          Built to demonstrate production-minded AI integration work: translate
          ambiguity, verify operational truth, make failure visible, and preserve
          human control.
        </p>
        <span>TypeScript interface · Python reference engine · SQL-backed tests</span>
      </footer>
    </main>
  );
}
