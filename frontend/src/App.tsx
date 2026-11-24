import React from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { WorkspaceProvider } from "./context/WorkspaceContext";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/LoginPage";
import { OverviewPage } from "./pages/OverviewPage";
import { MonitoringTopicsPage } from "./pages/MonitoringTopicsPage";
import { TopicExplorerPage } from "./pages/TopicExplorerPage";
import { LiveMonitoringPage } from "./pages/LiveMonitoringPage";
import { EventIntelligencePage } from "./pages/EventIntelligencePage";
import { AnalystWorkspacePage } from "./pages/AnalystWorkspacePage";
import { InsightReportsPage } from "./pages/InsightReportsPage";
import { DataSourcesPage } from "./pages/DataSourcesPage";
import { MethodologyPage } from "./pages/MethodologyPage";
import { AdminAuditPage } from "./pages/AdminAuditPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 20_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-workspace text-xs text-slate-500">
        Loading PulseIQ workspace...
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <WorkspaceProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <Layout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<OverviewPage />} />
                <Route path="topics" element={<MonitoringTopicsPage />} />
                <Route path="explorer" element={<TopicExplorerPage />} />
                <Route path="live" element={<LiveMonitoringPage />} />
                <Route path="events" element={<EventIntelligencePage />} />
                <Route path="workspace" element={<AnalystWorkspacePage />} />
                <Route path="reports" element={<InsightReportsPage />} />
                <Route path="sources" element={<DataSourcesPage />} />
                <Route path="methodology" element={<MethodologyPage />} />
                <Route path="admin" element={<AdminAuditPage />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </WorkspaceProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
};

export default App;
