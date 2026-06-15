import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { fetchStatus } from "@/api/status";
import { useDashboardContext } from "@/context/DashboardContext";
import { Badge, Card, SectionHeading } from "@/components/ui";
import {
  classificationPriority,
  DASHBOARD_LABELS,
  incidentRules,
  LIMITATIONS,
  networkHealthRows,
  nodeClassificationRows,
  OBSERVATION_SOURCES,
  otbrHealthRows,
  SEVERITY_ROWS,
  thresholdRows,
  type DiagnosticsConfig,
  type GuideSeverity,
} from "@/lib/monitoringGuide";
import { severityLabel } from "@/lib/severity";

function SeverityBadge({ severity }: { severity: GuideSeverity }) {
  return <Badge severity={severity}>{severityLabel(severity)}</Badge>;
}

function GuideTable({
  headers,
  rows,
}: {
  headers: string[];
  rows: ReactNode[][];
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-zl-border">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead className="border-b border-zl-border bg-zl-surface-2/80">
          <tr>
            {headers.map((h) => (
              <th key={h} className="px-3 py-2.5 font-semibold text-zl-text">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-zl-border/60">
          {rows.map((cells, i) => (
            <tr key={i} className="align-top hover:bg-zl-surface-2/40">
              {cells.map((cell, j) => (
                <td key={j} className="px-3 py-3 text-zl-text">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const SECTIONS = [
  { id: "pipeline", label: "Pipeline" },
  { id: "severity", label: "Severity levels" },
  { id: "sources", label: "What we observe" },
  { id: "devices", label: "Node classification" },
  { id: "otbr", label: "OTBR health" },
  { id: "networks", label: "Network health" },
  { id: "incidents", label: "Incidents" },
  { id: "dashboard", label: "Dashboard labels" },
  { id: "thresholds", label: "Your thresholds" },
  { id: "homeassistant", label: "Home Assistant" },
  { id: "live", label: "Live updates" },
  { id: "limits", label: "Limitations" },
];

const HA_PATHS = [
  {
    title: "Core dashboard (this UI)",
    detail:
      "Canonical multi-page React dashboard served by ThreadLens Core. Open directly at your Core URL or through a reverse proxy.",
  },
  {
    title: "MQTT Discovery",
    detail:
      "Optional Home Assistant entities published by Core when MQTT is enabled. The dashboard does not depend on MQTT.",
  },
  {
    title: "HACS integration",
    detail:
      "Native companion sidebar panel, helper entities, diagnostics, and HA Matter device name push to Core. Open Full Dashboard always works; embedded view auto-loads when HA and Core use the same protocol.",
  },
  {
    title: "HAOS add-on Ingress",
    detail:
      "Home Assistant OS add-on path for same-origin embedded full dashboard through Supervisor Ingress.",
  },
];

export function HowItWorksPage() {
  const { data, liveState } = useDashboardContext();
  const [diagnostics, setDiagnostics] = useState<DiagnosticsConfig>({});

  useEffect(() => {
    const controller = new AbortController();
    void fetchStatus(controller.signal)
      .then((status) => setDiagnostics(status.diagnostics ?? {}))
      .catch(() => {});
    return () => controller.abort();
  }, []);

  const nodes = nodeClassificationRows(diagnostics);
  const otbrs = otbrHealthRows(diagnostics);
  const incidents = incidentRules(diagnostics);
  const liveLabel =
    liveState === "open" ? "Live (SSE)" : liveState === "connecting" ? "Connecting" : "Polling (30s)";

  return (
    <div className="max-w-5xl space-y-8">
      <header className="space-y-3">
        <h1 className="text-2xl font-semibold tracking-tight">How monitoring works</h1>
        <p className="max-w-3xl text-zl-muted leading-relaxed">
          ThreadLens watches OTBR REST, Matter Server, and mDNS/TREL on your LAN, classifies health,
          and shows evidence with explicit limitations. Nothing here mutates your Thread or Matter
          network — this page documents exactly what is observed and how decisions are made.
        </p>
        <nav className="flex flex-wrap gap-2 pt-1" aria-label="On this page">
          {SECTIONS.map((s) => (
            <a
              key={s.id}
              href={`#${s.id}`}
              className="rounded-full border border-zl-border px-3 py-1 text-xs text-zl-muted hover:border-zl-accent/40 hover:text-zl-accent"
            >
              {s.label}
            </a>
          ))}
        </nav>
      </header>

      <section id="pipeline">
        <Card title="Monitoring pipeline" subtitle="What happens after each observation cycle">
          <ol className="space-y-3 text-sm leading-relaxed text-zl-text">
            <li>
              <strong className="font-medium">Collect</strong> — Core polls OTBR REST, listens on
              Matter Server websockets, and observes mDNS/TREL (all read-only).
            </li>
            <li>
              <strong className="font-medium">Normalize &amp; store</strong> — Observations update
              SQLite (inventory, availability, probes, bridge state, events).
            </li>
            <li>
              <strong className="font-medium">Classify health</strong> — Per-node, OTBR, network, and
              collector rules run (thresholds below).
            </li>
            <li>
              <strong className="font-medium">Assess incidents</strong> — Overview incident summary
              combines unavailable nodes, needs-attention signals, and infrastructure health.
            </li>
            <li>
              <strong className="font-medium">Present</strong> — Dashboard, devices, infrastructure,
              timeline, and reports show conclusions with evidence and limitations.
            </li>
          </ol>
          <p className="mt-4 text-sm text-zl-muted">
            The dashboard refreshes via SSE when available ({liveLabel}
            {data?.threadlens?.version ? ` · Core ${data.threadlens.version}` : ""}). Health
            recalculates after collector updates and probe results.
          </p>
        </Card>
      </section>

      <section id="severity" className="space-y-3">
        <SectionHeading>Severity levels</SectionHeading>
        <GuideTable
          headers={["Severity", "UI label", "Meaning"]}
          rows={SEVERITY_ROWS.map((r) => [
            <SeverityBadge key="s" severity={r.severity} />,
            r.label,
            r.meaning,
          ])}
        />
      </section>

      <section id="sources" className="space-y-3">
        <SectionHeading>What we observe (read-only)</SectionHeading>
        <GuideTable
          headers={["Source", "Used for"]}
          rows={OBSERVATION_SOURCES.map((r) => [r.source, r.use])}
        />
      </section>

      <section id="devices" className="space-y-4">
        <SectionHeading>Matter node classification</SectionHeading>
        <p className="text-sm text-zl-muted">
          Each node gets one dashboard classification (first match wins). Classification order:
        </p>
        <ol className="list-decimal space-y-1 pl-5 text-sm text-zl-muted">
          {classificationPriority().map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
        <GuideTable
          headers={["Classification", "When it applies", "Effect", "Typical severity", "UI label"]}
          rows={nodes.map((r) => [
            <code key="f" className="font-mono text-xs">
              {r.label}
            </code>,
            r.condition,
            r.result,
            <SeverityBadge key="s" severity={r.severity} />,
            r.uiLabel,
          ])}
        />
        <p className="text-sm text-zl-muted">
          See live groups on{" "}
          <Link to="/devices" className="text-zl-accent hover:underline">
            Devices
          </Link>{" "}
          and the status legend on{" "}
          <Link to="/" className="text-zl-accent hover:underline">
            Overview
          </Link>
          .
        </p>
      </section>

      <section id="otbr" className="space-y-3">
        <SectionHeading>OTBR health</SectionHeading>
        <GuideTable
          headers={["Signal", "When it applies", "Effect", "Severity", "UI wording"]}
          rows={otbrs.map((r) => [
            <code key="f" className="font-mono text-xs">
              {r.label}
            </code>,
            r.condition,
            r.result,
            <SeverityBadge key="s" severity={r.severity} />,
            r.uiLabel,
          ])}
        />
      </section>

      <section id="networks" className="space-y-3">
        <SectionHeading>Thread network health</SectionHeading>
        <GuideTable
          headers={["State", "Condition", "Effect", "Severity"]}
          rows={networkHealthRows().map((r) => [
            r.label,
            r.condition,
            r.result,
            <SeverityBadge key="s" severity={r.severity} />,
          ])}
        />
      </section>

      <section id="incidents" className="space-y-3">
        <SectionHeading>Incident assessment</SectionHeading>
        <p className="text-sm text-zl-muted">
          Overview incident state is conservative: unavailable nodes and real infrastructure problems
          open an incident; needs-attention and unstable nodes contribute watch-level findings.
        </p>
        <GuideTable
          headers={["Type", "Title", "Opens when", "Severity", "Scope", "Notes"]}
          rows={incidents.map((r) => [
            r.type,
            r.title,
            r.trigger,
            <SeverityBadge key="s" severity={r.severity} />,
            r.scope,
            r.notes ?? "—",
          ])}
        />
      </section>

      <section id="dashboard" className="space-y-3">
        <SectionHeading>Where dashboard labels come from</SectionHeading>
        <GuideTable
          headers={["UI surface", "Source"]}
          rows={DASHBOARD_LABELS.map((r) => [r.surface, r.source])}
        />
      </section>

      <section id="thresholds" className="space-y-3">
        <SectionHeading>Your active thresholds</SectionHeading>
        {Object.keys(diagnostics).length === 0 ? (
          <p className="text-sm text-zl-muted">
            Thresholds load from Core config via{" "}
            <code className="rounded bg-zl-surface-2 px-1 font-mono text-xs">/api/v1/status</code>.
            Refresh this page if the section is empty.
          </p>
        ) : (
          <>
            <p className="text-sm text-zl-muted">
              Values below are from this Core instance&apos;s{" "}
              <code className="rounded bg-zl-surface-2 px-1 font-mono text-xs">config.yaml</code>.
              Edit config and restart Core to change them.
            </p>
            <GuideTable
              headers={["Config key", "Value", "Used for"]}
              rows={thresholdRows(diagnostics).map(([key, value, used]) => [
                <code key="k" className="font-mono text-xs">
                  {key}
                </code>,
                String(value),
                used,
              ])}
            />
          </>
        )}
      </section>

      <section id="homeassistant" className="space-y-3">
        <SectionHeading>Home Assistant paths</SectionHeading>
        <div className="space-y-3">
          {HA_PATHS.map((item) => (
            <Card key={item.title} title={item.title}>
              <p className="text-sm leading-relaxed text-zl-muted">{item.detail}</p>
            </Card>
          ))}
        </div>
      </section>

      <section id="live">
        <Card title="Live updates">
          <p className="text-sm leading-relaxed text-zl-muted">
            This dashboard prefers a Server-Sent Events (SSE) stream from Core for near-real-time
            refresh. When SSE is unavailable — for example behind a reverse proxy that buffers event
            streams — the UI falls back to 30-second polling. Use the header refresh button for an
            immediate manual update.
          </p>
        </Card>
      </section>

      <section id="limits" className="space-y-3">
        <SectionHeading>What ThreadLens does not claim</SectionHeading>
        <Card title="Read-only guarantee">
          <p className="mb-4 text-sm leading-relaxed text-zl-muted">
            ThreadLens never commissions Thread devices, changes datasets, sends Matter control
            commands, or runs mutating OTBR actions. Read probes are safe read-only Matter attribute
            checks — they do not move blinds or change device state.
          </p>
          <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-zl-muted">
            {LIMITATIONS.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Card>
        <p className="text-sm text-zl-muted">
          Raw payload sections for support are on{" "}
          <Link to="/diagnostics" className="text-zl-accent hover:underline">
            Diagnostics
          </Link>
          ; downloadable reports are on{" "}
          <Link to="/reports" className="text-zl-accent hover:underline">
            Reports
          </Link>
          .
        </p>
      </section>
    </div>
  );
}
