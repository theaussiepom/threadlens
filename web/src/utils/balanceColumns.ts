export type BalanceItem = {
  id: string;
  mobileOrder: number;
  height: number;
};

/** Greedy shortest-column assignment; preserves mobile order as tie-breaker. */
export function balanceIntoTwoColumns(items: BalanceItem[], gap = 16): [string[], string[]] {
  const sorted = [...items].sort((a, b) => a.mobileOrder - b.mobileOrder);
  const colHeights: [number, number] = [0, 0];
  const left: string[] = [];
  const right: string[] = [];

  for (const item of sorted) {
    const col: 0 | 1 = colHeights[0] <= colHeights[1] ? 0 : 1;
    if (col === 0) {
      left.push(item.id);
    } else {
      right.push(item.id);
    }
    colHeights[col] += item.height + gap;
  }

  return [left, right];
}

export function defaultColumnSplit(ids: string[], mobileOrders: Map<string, number>): [string[], string[]] {
  const sorted = [...ids].sort((a, b) => (mobileOrders.get(a) ?? 0) - (mobileOrders.get(b) ?? 0));
  const left: string[] = [];
  const right: string[] = [];
  sorted.forEach((id, index) => {
    if (index % 2 === 0) {
      left.push(id);
    } else {
      right.push(id);
    }
  });
  return [left, right];
}
