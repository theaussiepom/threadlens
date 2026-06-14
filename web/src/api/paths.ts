/**
 * Path-safe URL resolution for ThreadLens Core.
 *
 * All API and report links are resolved relative to the current document
 * location, so the dashboard works unchanged when served from the root, from a
 * reverse-proxy subpath, or under a Home Assistant Ingress path prefix. We
 * never hard-code an absolute `/api/...` path, because that would break
 * path-prefixed deployments.
 */

/** Base directory of the current document (always ends with `/`). */
export function documentBase(): string {
  return new URL(".", window.location.href).href;
}

/**
 * Resolve a relative API/report path against the document base.
 * A leading slash is stripped so the path stays relative to the base.
 */
export function resolveUrl(path: string): string {
  const normalized = path.startsWith("/") ? path.slice(1) : path;
  return new URL(normalized, documentBase()).href;
}

export const DASHBOARD_PATH = "api/v1/dashboard";
export const REPORT_YAML_PATH = "api/v1/report.yaml";
export const REPORT_JSON_PATH = "api/v1/report.json";

export function dashboardUrl(): string {
  return resolveUrl(DASHBOARD_PATH);
}
