import { Link } from "react-router-dom";
import { Card, SectionHeading } from "@/components/ui";
import { NODE_STATUS_LEGEND, RECENT_WINDOW_DESCRIPTION } from "@/utils/health";

const DATA_SOURCES = [
  {
    title: "OTBR REST",
    detail:
      "Read-only polling of configured OpenThread Border Routers. Role, network name, device inventory, and reachability. Thread stack state is shown explicitly — REST reachability does not mean the Thread radio is active.",
  },
  {
    title: "Matter Server websocket",
    detail:
      "Passive observer of python-matter-server inventory and availability. ThreadLens only sends read-only commands (listen, get nodes, read attribute, ping). It never commissions, commands, or mutates nodes.",
  },
  {
    title: "mDNS / DNS-SD",
    detail:
      "Observes configured service types (_trel._udp, _meshcop._udp, _matter._tcp, _matterc._udp). Requires host networking on Linux for reliable LAN visibility from Docker.",
  },
  {
    title: "TREL services",
    detail:
      "Extracted from mDNS TREL records. Foreign or observed-other Extended PAN IDs are informational — ThreadLens does not call them competing networks.",
  },
  {
    title: "Optional ThreadLens agents",
    detail:
      "Remote agents can expose additional read-only observations from other hosts. Agents never mutate Thread or Matter state.",
  },
];

const LIMITATIONS = [
  "Subscription, CASE, and command diagnostics are unavailable unless structured Matter Server events expose them.",
  "ThreadLens never infers subscription flaps from availability flaps.",
  "mDNS/TREL visibility does not prove device parentage or mesh topology.",
  "Initial mDNS discovery after startup is baseline observation, not service flapping.",
  "Unavailable metrics are reported as null or explicit capability flags — never inferred as zero.",
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
  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">How it works</h1>
        <p className="mt-1 text-zl-muted">
          Read-only Thread and Matter-over-Thread observability — what ThreadLens watches, how health is
          classified, and what it will never claim.
        </p>
      </div>

      <Card title="What ThreadLens is">
        <p className="text-sm leading-relaxed text-zl-muted">
          ThreadLens collects observations from your LAN, stores them in local SQLite, classifies health,
          and surfaces evidence on this dashboard and in redacted reports. It is designed for Home Assistant
          environments but is not hard-coupled to Home Assistant Core.
        </p>
        <p className="mt-3 text-sm leading-relaxed text-zl-muted">
          The guiding question on the{" "}
          <Link to="/" className="text-zl-accent hover:underline">
            Overview
          </Link>{" "}
          page: <em>Is anything broken, where, and what does the evidence say?</em>
        </p>
      </Card>

      <section className="space-y-3">
        <SectionHeading>What we observe</SectionHeading>
        <div className="space-y-3">
          {DATA_SOURCES.map((item) => (
            <Card key={item.title} title={item.title}>
              <p className="text-sm leading-relaxed text-zl-muted">{item.detail}</p>
            </Card>
          ))}
        </div>
      </section>

      <Card title="How Matter node health is classified" subtitle={RECENT_WINDOW_DESCRIPTION}>
        <dl className="grid gap-4">
          {NODE_STATUS_LEGEND.map((entry) => (
            <div key={entry.key}>
              <dt className="text-sm font-medium text-zl-text">{entry.label}</dt>
              <dd className="mt-1 text-sm text-zl-muted">{entry.description}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-4 text-sm text-zl-muted">
          See live classifications on the{" "}
          <Link to="/devices" className="text-zl-accent hover:underline">
            Devices
          </Link>{" "}
          page and status legend on{" "}
          <Link to="/" className="text-zl-accent hover:underline">
            Overview
          </Link>
          .
        </p>
      </Card>

      <Card title="What ThreadLens does not infer">
        <ul className="list-disc space-y-2 pl-5 text-sm text-zl-muted">
          {LIMITATIONS.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </Card>

      <Card title="Read-only guarantee">
        <p className="text-sm leading-relaxed text-zl-muted">
          ThreadLens never commissions Thread devices, changes datasets, sends Matter control commands,
          or runs mutating OTBR actions. Read probes are safe read-only Matter attribute checks — they do
          not move blinds or change device state. ThreadLens does not use SSH, Docker socket access, or log
          scraping in normal operation.
        </p>
      </Card>

      <section className="space-y-3">
        <SectionHeading>Home Assistant paths</SectionHeading>
        <div className="space-y-3">
          {HA_PATHS.map((item) => (
            <Card key={item.title} title={item.title}>
              <p className="text-sm leading-relaxed text-zl-muted">{item.detail}</p>
            </Card>
          ))}
        </div>
      </section>

      <Card title="Live updates">
        <p className="text-sm leading-relaxed text-zl-muted">
          This dashboard prefers a Server-Sent Events (SSE) stream from Core for near-real-time refresh.
          When SSE is unavailable — for example behind a reverse proxy that buffers event streams — the UI
          falls back to 30-second polling. Use the header refresh button for an immediate manual update.
        </p>
      </Card>

      <Card title="Reports and diagnostics">
        <p className="text-sm leading-relaxed text-zl-muted">
          Factual YAML and JSON reports are generated from the same stored observations as this dashboard.
          Reports redact secrets defensively. Raw payload sections for support are on the{" "}
          <Link to="/diagnostics" className="text-zl-accent hover:underline">
            Diagnostics
          </Link>{" "}
          page; downloadable reports are on{" "}
          <Link to="/reports" className="text-zl-accent hover:underline">
            Reports
          </Link>
          .
        </p>
      </Card>
    </div>
  );
}
