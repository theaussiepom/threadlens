import { NODE_STATUS_LEGEND, RECENT_WINDOW_DESCRIPTION } from "../utils/health";
import { Collapsible } from "./primitives";

export function StatusLegend() {
  return (
    <Collapsible summary="What do these statuses mean?" className="tl-status-legend" defaultOpen>
      <p className="tl-muted tl-note">{RECENT_WINDOW_DESCRIPTION}</p>
      <dl className="tl-status-legend-list">
        {NODE_STATUS_LEGEND.map((entry) => (
          <div className="tl-status-legend-item" key={entry.key}>
            <dt>{entry.label}</dt>
            <dd>{entry.description}</dd>
          </div>
        ))}
      </dl>
    </Collapsible>
  );
}
