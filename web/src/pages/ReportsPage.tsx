import { useState } from "react";
import { useDashboardContext } from "@/context/DashboardContext";
import { REPORT_JSON_PATH, REPORT_YAML_PATH, resolveUrl } from "@/api/paths";
import { Card, ErrorState, KeyValue, LoadingState } from "@/components/ui";
import { fmtTime } from "@/utils/format";

export function ReportsPage() {
  const { data, hasLoaded, error, connected, refresh } = useDashboardContext();
  const [copied, setCopied] = useState(false);

  if (!data && !hasLoaded) return <LoadingState />;
  if (!data && hasLoaded) return <ErrorState message={error || "Cannot reach API"} onRetry={refresh} />;
  if (!connected) return <ErrorState message={error || "Disconnected"} onRetry={refresh} />;
  if (!data) return null;

  const report = data.report;
  const yamlPath = report.report_url || REPORT_YAML_PATH;
  const jsonPath = report.report_url_json || REPORT_JSON_PATH;

  const copyPath = async () => {
    try {
      await navigator.clipboard?.writeText(resolveUrl(yamlPath));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Reports</h1>
        <p className="mt-1 text-zl-muted">Factual YAML and JSON diagnostic reports from ThreadLens Core.</p>
      </div>

      <Card title="Diagnostic reports">
        <KeyValue
          rows={[
            {
              label: "Last generated",
              value: report.last_generated_at ? fmtTime(report.last_generated_at) : "never",
            },
          ]}
        />
        <div className="mt-4 flex flex-wrap gap-2">
          <a
            href={resolveUrl(yamlPath)}
            target="_blank"
            rel="noopener"
            className="min-h-11 rounded-lg border border-zl-accent/40 bg-zl-accent/15 px-4 py-2 text-sm text-zl-accent hover:bg-zl-accent/25"
          >
            Open YAML
          </a>
          <a
            href={resolveUrl(jsonPath)}
            target="_blank"
            rel="noopener"
            className="min-h-11 rounded-lg border border-zl-border bg-zl-bg px-4 py-2 text-sm text-zl-text hover:bg-zl-surface-2"
          >
            Open JSON
          </a>
          <button
            type="button"
            onClick={() => void copyPath()}
            className="min-h-11 rounded-lg border border-zl-border bg-zl-bg px-4 py-2 text-sm text-zl-text hover:bg-zl-surface-2"
          >
            {copied ? "Copied" : "Copy YAML link"}
          </button>
        </div>
      </Card>
    </div>
  );
}
