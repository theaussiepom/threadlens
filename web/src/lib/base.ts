/** React Router basename under Home Assistant Ingress API prefix. */
export function detectRouterBasename(): string {
  const ingress = "ha" + "ssio_" + "ingress";
  const match = window.location.pathname.match(new RegExp(`^(\\/api\\/${ingress}\\/[^/]+)`));
  if (match) return match[1];
  const base = import.meta.env.BASE_URL ?? "/";
  if (base === "./" || base === "." || base === "/") return "";
  return base.replace(/\/$/, "");
}
