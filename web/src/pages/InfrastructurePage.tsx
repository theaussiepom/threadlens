import { useDashboardContext } from "@/context/DashboardContext";
import {
  Card,
  EmptyState,
  ErrorState,
  HealthBadge,
  KeyValue,
  LoadingState,
  SectionHeading,
} from "@/components/ui";
import { boolText, fmtTime, orDash } from "@/utils/format";
import type { Otbr } from "@/api/types";

function OtbrCard({ otbr }: { otbr: Otbr }) {
  const displayHealth = otbr.display_health || otbr.health;
  const realProblem = otbr.rest_endpoint_mismatch && !otbr.mismatch_reconciled;

  return (
    <Card title={otbr.name || otbr.id || "OTBR"} actions={<HealthBadge state={displayHealth} />}>
      <KeyValue
        rows={[
          { label: "Reachable", value: boolText(otbr.reachable, "Yes", "No") },
          { label: "Effective state", value: orDash(otbr.effective_state || otbr.role) },
          { label: "Thread state", value: orDash(otbr.thread_state) },
          { label: "Network", value: orDash(otbr.network_name) },
          { label: "Extended PAN ID", value: orDash(otbr.extended_pan_id) },
          { label: "RLOC16", value: orDash(otbr.rloc16) },
        ]}
      />
      {realProblem && (
        <p className="mt-3 border-l-2 border-zl-incident/40 pl-3 text-sm text-zl-incident">
          OTBR REST endpoints disagree and could not be reconciled.
        </p>
      )}
      {otbr.mismatch_reconciled && otbr.mismatch_detail && (
        <p className="mt-3 text-sm text-zl-muted">{otbr.mismatch_detail}</p>
      )}
    </Card>
  );
}

export function InfrastructurePage() {
  const { data, hasLoaded, error, connected, refresh } = useDashboardContext();

  if (!data && !hasLoaded) return <LoadingState />;
  if (!data && hasLoaded) return <ErrorState message={error || "Cannot reach API"} onRetry={refresh} />;
  if (!connected) return <ErrorState message={error || "Disconnected"} onRetry={refresh} />;
  if (!data) return null;

  const matter = data.matter;
  const trel = data.trel;

  return (
    <div className="max-w-6xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Infrastructure</h1>
        <p className="mt-1 text-zl-muted">OTBR, Matter servers, Thread networks, mDNS, TREL, and MQTT.</p>
      </div>

      <section className="space-y-3">
        <SectionHeading>OTBRs</SectionHeading>
        {data.otbrs.length === 0 ? (
          <EmptyState title="No OTBRs configured" />
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {data.otbrs.map((otbr) => (
              <OtbrCard key={otbr.id ?? otbr.name} otbr={otbr} />
            ))}
          </div>
        )}
      </section>

      <Card
        title="Matter servers"
        actions={<HealthBadge state={matter.health} />}
      >
        <KeyValue
          rows={[
            {
              label: "Servers connected",
              value: `${matter.servers_connected || 0} / ${matter.servers || 0}`,
            },
            { label: "Total nodes", value: matter.node_count || 0 },
            { label: "Unavailable", value: matter.unavailable_count || 0 },
          ]}
        />
        {(matter.reasons ?? []).length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {(matter.reasons ?? []).map((r) => (
              <span
                key={r.code}
                className="rounded-md border border-zl-border bg-zl-bg/50 px-2 py-1 text-xs text-zl-muted"
              >
                {r.label}
              </span>
            ))}
          </div>
        )}
      </Card>

      <section className="space-y-3">
        <SectionHeading>Thread networks</SectionHeading>
        {data.networks.length === 0 ? (
          <EmptyState title="No Thread networks reported" />
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {data.networks.map((n) => (
              <Card
                key={n.extended_pan_id ?? n.name}
                title={n.name || n.extended_pan_id || "Thread network"}
                actions={<HealthBadge state={n.health} />}
              >
                <KeyValue
                  rows={[
                    { label: "Extended PAN ID", value: orDash(n.extended_pan_id) },
                    { label: "Channel", value: orDash(n.channel) },
                    { label: "Classification", value: orDash(n.classification) },
                    { label: "Border routers", value: orDash(n.border_router_count) },
                  ]}
                />
              </Card>
            ))}
          </div>
        )}
      </section>

      <Card title="mDNS / TREL" actions={<HealthBadge state={trel.health} />}>
        <KeyValue
          rows={[
            { label: "mDNS health", value: <HealthBadge state={data.mdns.health} /> },
            { label: "mDNS services", value: data.mdns.service_count || 0 },
            {
              label: "Observation degraded",
              value: boolText(data.mdns.observation_degraded, "Yes", "No"),
            },
            { label: "TREL services", value: trel.service_count || 0 },
            { label: "Foreign TREL", value: trel.foreign_service_count || 0 },
          ]}
        />
        {trel.foreign_service_count > 0 && trel.info?.message && (
          <p className="mt-3 text-sm text-zl-muted">{trel.info.message}</p>
        )}
      </Card>

      <Card title="MQTT">
        {!data.mqtt ? (
          <p className="text-sm text-zl-muted">MQTT publishing is not configured.</p>
        ) : (
          <KeyValue
            rows={[
              { label: "Enabled", value: boolText(data.mqtt.enabled, "Yes", "No") },
              { label: "Connected", value: boolText(data.mqtt.connected, "Yes", "No") },
              {
                label: "HA discovery",
                value: boolText(data.mqtt.homeassistant_discovery_enabled, "Yes", "No"),
              },
              { label: "Last publish", value: fmtTime(data.mqtt.last_publish_at) },
              { label: "Last error", value: orDash(data.mqtt.last_error) },
            ]}
          />
        )}
      </Card>
    </div>
  );
}
