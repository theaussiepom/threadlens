import { useDashboardContext } from "@/context/DashboardContext";
import { TimelineEventRow } from "@/components/cards";
import { Card, EmptyState, ErrorState, LoadingState } from "@/components/ui";

export function TimelinePage() {
  const { data, hasLoaded, error, connected, refresh } = useDashboardContext();

  if (!data && !hasLoaded) return <LoadingState />;
  if (!data && hasLoaded) return <ErrorState message={error || "Cannot reach API"} onRetry={refresh} />;
  if (!connected) return <ErrorState message={error || "Disconnected"} onRetry={refresh} />;
  if (!data) return null;

  const events = data.events?.items ?? [];

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Timeline</h1>
        <p className="mt-1 text-zl-muted">
          Meaningful events in the last {data.events?.window ?? "24h"} window.
        </p>
      </div>

      <Card title="Events">
        {events.length === 0 ? (
          <EmptyState title="No events in this window" />
        ) : (
          <div className="space-y-1">
            {events.map((event, idx) => (
              <TimelineEventRow key={`${event.timestamp}-${idx}`} event={event} />
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
