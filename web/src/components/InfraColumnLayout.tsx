import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  balanceIntoTwoColumns,
  defaultColumnSplit,
  type BalanceItem,
} from "../utils/balanceColumns";

const DESKTOP_MEDIA = "(min-width: 960px)";
const COLUMN_GAP_PX = 16;

export type InfraLayoutItem = {
  id: string;
  mobileOrder: number;
  node: ReactNode;
};

function useDesktopLayout(): boolean {
  const [desktop, setDesktop] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia(DESKTOP_MEDIA).matches : false,
  );

  useEffect(() => {
    const mq = window.matchMedia(DESKTOP_MEDIA);
    const onChange = () => setDesktop(mq.matches);
    onChange();
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return desktop;
}

export function InfraColumnLayout({ items }: { items: InfraLayoutItem[] }) {
  const desktop = useDesktopLayout();
  const layoutRef = useRef<HTMLDivElement>(null);
  const measureRef = useRef<HTMLDivElement>(null);
  const [columns, setColumns] = useState<[string[], string[]] | null>(null);

  const byId = useMemo(() => new Map(items.map((item) => [item.id, item])), [items]);
  const mobileOrders = useMemo(
    () => new Map(items.map((item) => [item.id, item.mobileOrder])),
    [items],
  );
  const mobileSorted = useMemo(
    () => [...items].sort((a, b) => a.mobileOrder - b.mobileOrder),
    [items],
  );

  const rebalance = useCallback(() => {
    if (!desktop || !measureRef.current) {
      setColumns(null);
      return;
    }

    const measured: BalanceItem[] = Array.from(
      measureRef.current.querySelectorAll<HTMLElement>("[data-infra-id]"),
    ).map((el) => ({
      id: el.dataset.infraId ?? "",
      mobileOrder: Number(el.dataset.mobileOrder ?? 0),
      height: el.getBoundingClientRect().height,
    }));

    if (!measured.length || measured.some((item) => item.height <= 0)) {
      return;
    }

    setColumns(balanceIntoTwoColumns(measured, COLUMN_GAP_PX));
  }, [desktop]);

  useEffect(() => {
    rebalance();
  }, [rebalance, items]);

  useEffect(() => {
    if (!desktop || !measureRef.current) {
      return;
    }

    const observer = new ResizeObserver(() => rebalance());
    const slots = measureRef.current.querySelectorAll("[data-infra-id]");
    slots.forEach((slot) => observer.observe(slot));
    observer.observe(measureRef.current);
    rebalance();

    return () => observer.disconnect();
  }, [desktop, rebalance, items]);

  if (!desktop) {
    return (
      <div className="tl-infra-layout">
        {mobileSorted.map((item) => (
          <div key={item.id} className={`tl-infra-slot tl-infra-slot-${item.id}`}>
            {item.node}
          </div>
        ))}
      </div>
    );
  }

  const [leftIds, rightIds] =
    columns ?? defaultColumnSplit(items.map((item) => item.id), mobileOrders);

  return (
    <div className="tl-infra-layout tl-infra-layout-balanced" ref={layoutRef}>
      <div className="tl-infra-measure" aria-hidden="true" ref={measureRef}>
        {items.map((item) => (
          <div
            key={item.id}
            data-infra-id={item.id}
            data-mobile-order={item.mobileOrder}
            className="tl-infra-measure-slot"
          >
            {item.node}
          </div>
        ))}
      </div>
      <div className="tl-infra-col">
        {leftIds.map((id) => (
          <div key={id} className={`tl-infra-slot tl-infra-slot-${id}`}>
            {byId.get(id)?.node}
          </div>
        ))}
      </div>
      <div className="tl-infra-col">
        {rightIds.map((id) => (
          <div key={id} className={`tl-infra-slot tl-infra-slot-${id}`}>
            {byId.get(id)?.node}
          </div>
        ))}
      </div>
    </div>
  );
}
