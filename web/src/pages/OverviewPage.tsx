import { Link } from "react-router-dom";
import { useDashboardContext } from "@/context/DashboardContext";
import { CurrentFindingCard, MatterNodeCard, TimelineEventRow } from "@/components/cards";
import {
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  SectionHeading,
  SeverityBadge,
  StaleBanner,
  StatTile,
} from "@/components/ui";
import { incidentToSeverity } from "@/lib/severity";
import { NODE_STATUS_LEGEND, RECENT_WINDOW_DESCRIPTION } from "@/utils/health";

function topAffected(nodes: import("@/api/types").MatterNode[]) {
  const order = ["unavailable", "needs_attention", "recently_unstable", "diagnostics_limited", "unknown"];
  return [...nodes]
    .filter((n) => n.classification !== "healthy")
    .sort((a, b) => order.indexOf(a.classification) - order.indexOf(b.classification))
    .slice(0, 6);
}

export function OverviewPage() {
  const { data, error, hasLoaded, connected, refresh } = useDashboardContext();

  if (!data && !hasLoaded) return <LoadingState />;
  if (!data && hasLoaded) return <ErrorState message={error || "Cannot reach ThreadLens API"} onRetry={refresh} />;
  if (!connected) {
    return (
      <ErrorState
        message={error || data?.error || "ThreadLens API disconnected"}
        onRetry={refresh}
      />
    );
  }
  if (!data) return null;

  const matter = data.matter;
  const incident = data.incident;

  return (
    <div className="max-w-7xl space-y-6">
      {error && <StaleBanner message={error} onRetry={refresh} />}

      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
          <p className="mt-1 text-zl-muted">Is anything broken, where, and what does the evidence say?</p>
        </div>
        <SeverityBadge severity={incidentToSeverity(incident.state)} />
      </header>

      <div className="grid grid-cols-1 gap-3 min-[400px]:grid-cols-2 sm:grid-cols-3 lg:grid-cols-5">
        <StatTile
          label="Unavailable"
          value={matter.unavailable_count || 0}
          severity={matter.unavailable_count ? "incident" : "healthy"}
        />
        <StatTile
          label="Unstable"
          value={matter.unstable_count || 0}
          severity={matter.unstable_count ? "watch" : "healthy"}
        />
        <StatTile label="Healthy" value={matter.healthy_count || 0} severity="healthy" />
        <StatTile label="Matter nodes" value={matter.node_count || 0} />
        <StatTile label="OTBRs" value={data.otbrs.length} />
        <StatTile
          label="mDNS services"
          value={data.mdns.service_count || 0}
          severity={data.mdns.observation_degraded ? "watch" : "healthy"}
        />
        <StatTile
          label="Foreign TREL"
          value={data.trel.foreign_service_count || 0}
          severity={data.trel.foreign_service_count ? "watch" : "healthy"}
        />
        <StatTile
          label="MQTT"
          value={data.mqtt?.connected ? "On" : "Off"}
          severity={data.mqtt?.connected ? "healthy" : "watch"}
        />
        <StatTile label="Networks" value={data.networks.length} />
        <StatTile label="Unknown" value={matter.unknown_count || 0} />
      </div>

      <CurrentFindingCard incident={incident} />

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <SectionHeading>Top affected Matter nodes</SectionHeading>
          <Link to="/devices" className="text-sm text-zl-accent hover:underline">
            All devices →
          </Link>
        </div>
        {topAffected(matter.nodes ?? []).length === 0 ? (
          <EmptyState title="No current Matter node health concerns" />
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {topAffected(matter.nodes ?? []).map((node) => (
              <MatterNodeCard key={node.subject_id ?? `${node.server_id}:${node.node_id}`} node={node} />
            ))}
          </div>
        )}
      </section>

      <Card title="Status legend" subtitle={RECENT_WINDOW_DESCRIPTION}>
        <dl className="grid gap-3 sm:grid-cols-2">
          {NODE_STATUS_LEGEND.map((entry) => (
            <div key={entry.key}>
              <dt className="text-sm font-medium text-zl-text">{entry.label}</dt>
              <dd className="mt-1 text-sm text-zl-muted">{entry.description}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <Card
        title="Recent timeline"
        subtitle="Latest meaningful events (24h window)"
        actions={
          <Link to="/timeline" className="text-sm text-zl-accent hover:underline">
            Full timeline →
          </Link>
        }
      >
        {(data.events?.items ?? []).length === 0 ? (
          <p className="text-sm text-zl-muted">No recent events.</p>
        ) : (
          <div className="space-y-1">
            {(data.events?.items ?? []).slice(0, 10).map((event, idx) => (
              <TimelineEventRow key={`${event.timestamp}-${idx}`} event={event} />
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
