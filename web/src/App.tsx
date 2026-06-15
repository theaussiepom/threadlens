import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import { DashboardProvider } from "@/context/DashboardContext";
import { detectRouterBasename } from "@/lib/base";
import { DeviceDetailPage } from "@/pages/DeviceDetailPage";
import { DevicesPage } from "@/pages/DevicesPage";
import { DiagnosticsPage } from "@/pages/DiagnosticsPage";
import { InfrastructurePage } from "@/pages/InfrastructurePage";
import { OverviewPage } from "@/pages/OverviewPage";
import { ReportsPage } from "@/pages/ReportsPage";
import { TimelinePage } from "@/pages/TimelinePage";

export default function App() {
  const basename = detectRouterBasename();

  return (
    <BrowserRouter basename={basename}>
      <DashboardProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<OverviewPage />} />
            <Route path="devices" element={<DevicesPage />} />
            <Route path="devices/:serverId/:nodeId" element={<DeviceDetailPage />} />
            <Route path="infrastructure" element={<InfrastructurePage />} />
            <Route path="timeline" element={<TimelinePage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="diagnostics" element={<DiagnosticsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </DashboardProvider>
    </BrowserRouter>
  );
}
