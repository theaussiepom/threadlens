import type { MatterNode } from "../api/types";

export function formatOtbrIds(ids: string[] | null | undefined): string | null {
  if (!ids?.length) return null;
  return ids.join(", ");
}

/** Subtitle parts for a node row: Matter name, vendor/product, OTBR ids. */
export function nodeSubtitleParts(node: MatterNode): string[] {
  const parts: string[] = [];
  if (node.matter_name) {
    parts.push(`Matter: ${node.matter_name}`);
  }
  const vendorProduct = [node.vendor, node.product].filter(Boolean).join(" · ");
  if (vendorProduct) {
    parts.push(vendorProduct);
  }
  const otbrs = formatOtbrIds(node.otbr_ids);
  if (otbrs) {
    parts.push(`OTBR: ${otbrs}`);
  }
  return parts;
}

export function nodeDrilldownSubtitle(node: MatterNode): string | null {
  const parts = nodeSubtitleParts(node);
  return parts.length ? parts.join(" · ") : null;
}
