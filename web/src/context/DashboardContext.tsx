import { createContext, useContext, type ReactNode } from "react";
import { useDashboard, type DashboardStatus } from "@/hooks/useDashboard";

const DashboardContext = createContext<DashboardStatus | null>(null);

export function DashboardProvider({ children }: { children: ReactNode }) {
  const status = useDashboard();
  return <DashboardContext.Provider value={status}>{children}</DashboardContext.Provider>;
}

export function useDashboardContext(): DashboardStatus {
  const ctx = useContext(DashboardContext);
  if (!ctx) {
    throw new Error("useDashboardContext must be used within DashboardProvider");
  }
  return ctx;
}
