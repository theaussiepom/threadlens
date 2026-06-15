import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchHealth,
  fetchStatus,
  type CollectorMatterStatus,
  type CollectorOtbrStatus,
  type HealthPayload,
  type StatusPayload,
} from "@/api/status";
import { Badge, Card, ErrorState, LoadingState } from "@/components/ui";
import { boolText, fmtRelative, orDash } from "@/utils/format";

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-zl-muted">{label}</dt>
      <dd className={mono ? "break-all text-right font-mono" : "text-right"}>{value}</dd>
    </div>
  );
}

function buildWarnings(
  status: StatusPayload,
  health: HealthPayload | null
): Array<{ text: string; severity: "incident" | "watch" }> {
  const out: Array<{ text: string; severity: "incident" | "watch" }> = [];
  const otbr = status.collectors.otbr;
  const matter = status.collectors.matter;
  const mdns = status.collectors.mdns;
  const mqtt = status.collectors.mqtt;

  if (!status.storage.ready) {
    out.push({ text: "Storage is not ready yet.", severity: "watch" });
  }
  if (otbr.configured === 0 && matter.configured === 0) {
    out.push({ text: "No OTBR or Matter servers are configured.", severity: "watch" });
  }
  if (otbr.configured > 0 && otbr.reachable === 0) {
    out.push({ text: "All configured OTBR collectors are unreachable.", severity: "incident" });
  }
  if (matter.configured > 0 && matter.connected === 0) {
    out.push({ text: "No Matter servers are connected.", severity: "incident" });
  }
  if (mdns.enabled && !mdns.observer_running) {
    out.push({ text: "mDNS observation is enabled but the observer is not running.", severity: "watch" });
  }
  if (mqtt.enabled && !mqtt.connected) {
    out.push({ text: "MQTT publishing is enabled but not connected.", severity: "incident" });
  }
  if (health?.overall.state === "critical" || health?.overall.state === "degraded") {
    out.push({
      text: `Overall health is ${health.overall.state}.`,
      severity: health.overall.state === "critical" ? "incident" : "watch",
    });
  }
  return out;
}

export function SettingsPage() {
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statusPayload, healthPayload] = await Promise.all([
        fetchStatus(),
        fetchHealth().catch(() => null),
      ]);
      setStatus(statusPayload);
      setHealth(healthPayload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading && !status) return <LoadingState label="Loading settings…" />;
  if (error && !status) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!status) return null;

  const warnings = buildWarnings(status, health);
  const otbr = status.collectors.otbr;
  const matter = status.collectors.matter;
  const mdns = status.collectors.mdns;
  const mqtt = status.collectors.mqtt;
  const config = status.configuration;
  const otbrs = status.configured_otbrs ?? [];
  const matterServers = status.configured_matter_servers ?? [];

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Settings &amp; status</h1>
        <p className="text-sm leading-relaxed text-zl-muted">
          Core, collector, and configuration health. Secrets are never shown. For a full explanation
          of health rules and incidents, see{" "}
          <Link to="/how-it-works" className="text-zl-accent hover:underline">
            How it works
          </Link>
          .
        </p>
      </div>

      {warnings.length > 0 && (
        <Card title="Warnings">
          <ul className="space-y-2">
            {warnings.map((w) => (
              <li key={w.text} className="flex items-center gap-2 text-sm">
                <Badge severity={w.severity === "incident" ? "incident" : "watch"}>
                  {w.severity === "incident" ? "warning" : "note"}
                </Badge>
                <span className="text-zl-text">{w.text}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card
        title="Core status"
        actions={
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            className="min-h-11 rounded-lg border border-zl-border px-4 py-2 text-sm hover:bg-zl-surface-2 active:bg-zl-surface-2 disabled:opacity-60"
          >
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        }
      >
        <dl className="space-y-3 text-sm">
          <Row label="Version" value={orDash(status.version)} />
          <Row label="Service" value={status.service} />
          <Row label="Mode" value={status.mode} />
          <Row label="Site" value={status.site.name} />
          <Row label="Overall health" value={orDash(health?.overall.state)} />
          <Row label="Environment health" value={orDash(health?.environment.state)} />
          <Row label="Storage" value={status.storage.ready ? "ready" : "not ready"} />
        </dl>
      </Card>

      <Card title="OTBR collector">
        <CollectorRows collector={otbr} kind="otbr" />
      </Card>

      <Card title="Matter collector">
        <CollectorRows collector={matter} kind="matter" />
      </Card>

      <Card title="mDNS observer">
        <dl className="space-y-3 text-sm">
          <Row label="Enabled" value={boolText(mdns.enabled, "yes", "no")} />
          <Row label="Observer running" value={boolText(mdns.observer_running, "yes", "no")} />
          <Row label="Services configured" value={String(mdns.services_configured)} />
          <Row
            label="Observation degraded"
            value={
              mdns.observation_degraded === null
                ? "unknown"
                : mdns.observation_degraded
                  ? "yes"
                  : "no"
            }
          />
        </dl>
      </Card>

      <Card title="MQTT Discovery">
        <dl className="space-y-3 text-sm">
          <Row label="Enabled" value={boolText(mqtt.enabled, "yes", "no")} />
          <Row label="Publisher connected" value={boolText(mqtt.connected, "yes", "no")} />
          <Row
            label="Home Assistant discovery"
            value={boolText(mqtt.homeassistant_discovery_enabled, "yes", "no")}
          />
          <Row
            label="Last publish"
            value={mqtt.last_publish_at ? fmtRelative(mqtt.last_publish_at) : "never"}
          />
          <Row label="Last error" value={mqtt.last_error ?? "none"} />
        </dl>
        {config && (
          <dl className="mt-4 space-y-3 border-t border-zl-border/40 pt-4 text-sm">
            <Row label="MQTT host" value={orDash(config.mqtt_host)} mono />
            <Row label="Topic prefix" value={config.mqtt_topic_prefix} mono />
            <Row label="Discovery prefix" value={config.mqtt_discovery_prefix} mono />
          </dl>
        )}
      </Card>

      <Card title="Configuration">
        <dl className="space-y-3 text-sm">
          <Row label="Storage path" value={status.storage.sqlite_path} mono />
          <Row
            label="Event retention"
            value={`${status.storage.event_retention_days} days`}
          />
          <Row label="Matter probe mode" value={orDash(config?.matter_probe_mode)} />
        </dl>

        <h3 className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-zl-muted">
          Configured OTBRs
        </h3>
        <ul className="space-y-2 text-sm">
          {otbrs.length === 0 ? (
            <li className="text-zl-muted">No OTBRs configured.</li>
          ) : (
            otbrs.map((item) => (
              <li key={item.id} className="rounded-lg border border-zl-border px-3 py-2">
                <div className="font-medium">{item.name}</div>
                <div className="break-all font-mono text-xs text-zl-muted">{item.id}</div>
              </li>
            ))
          )}
        </ul>

        <h3 className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-zl-muted">
          Configured Matter servers
        </h3>
        <ul className="space-y-2 text-sm">
          {matterServers.length === 0 ? (
            <li className="text-zl-muted">No Matter servers configured.</li>
          ) : (
            matterServers.map((item) => (
              <li key={item.id} className="rounded-lg border border-zl-border px-3 py-2">
                <div className="font-medium">{item.name}</div>
                <div className="break-all font-mono text-xs text-zl-muted">{item.id}</div>
              </li>
            ))
          )}
        </ul>
      </Card>

      {status.features && Object.keys(status.features).length > 0 && (
        <Card title="Features">
          <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
            {Object.entries(status.features).map(([key, value]) => (
              <div
                key={key}
                className="flex flex-col gap-1 border-b border-zl-border/40 py-2 sm:flex-row sm:justify-between"
              >
                <dt className="text-zl-muted">{key.replace(/_/g, " ")}</dt>
                <dd>{value ? "enabled" : "disabled"}</dd>
              </div>
            ))}
          </dl>
        </Card>
      )}

      {status.diagnostics && Object.keys(status.diagnostics).length > 0 && (
        <Card title="Diagnostics thresholds">
          <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
            {Object.entries(status.diagnostics).map(([key, value]) => (
              <div
                key={key}
                className="flex flex-col gap-1 border-b border-zl-border/40 py-2 sm:flex-row sm:justify-between"
              >
                <dt className="text-zl-muted">{key.replace(/_/g, " ")}</dt>
                <dd className="break-all font-mono">{String(value)}</dd>
              </div>
            ))}
          </dl>
        </Card>
      )}

      <Card title="Read-only guarantee">
        <p className="text-sm leading-relaxed text-zl-muted">
          ThreadLens never commissions Thread devices, changes datasets, sends Matter control
          commands, or runs mutating OTBR actions. Read probes are safe read-only Matter attribute
          checks — they do not move blinds or change device state.
        </p>
      </Card>
    </div>
  );
}

function CollectorRows({
  collector,
  kind,
}: {
  collector: CollectorOtbrStatus | CollectorMatterStatus;
  kind: "otbr" | "matter";
}) {
  if (kind === "otbr") {
    const otbr = collector as CollectorOtbrStatus;
    return (
      <dl className="space-y-3 text-sm">
        <Row label="Configured" value={String(otbr.configured)} />
        <Row label="Collector running" value={boolText(otbr.collector_running, "yes", "no")} />
        <Row label="Reachable" value={String(otbr.reachable)} />
        <Row label="Unreachable" value={String(otbr.unreachable)} />
        <Row
          label="Last poll"
          value={otbr.last_poll_at ? fmtRelative(otbr.last_poll_at) : "never"}
        />
      </dl>
    );
  }

  const matter = collector as CollectorMatterStatus;
  return (
    <dl className="space-y-3 text-sm">
      <Row label="Configured" value={String(matter.configured)} />
      <Row label="Collector running" value={boolText(matter.collector_running, "yes", "no")} />
      <Row label="Connected" value={String(matter.connected)} />
      <Row label="Disconnected" value={String(matter.disconnected)} />
      <Row label="Nodes seen" value={String(matter.nodes_seen)} />
      <Row label="Unavailable nodes" value={String(matter.unavailable_nodes)} />
      <Row
        label="Last event"
        value={matter.last_event_at ? fmtRelative(matter.last_event_at) : "never"}
      />
    </dl>
  );
}
