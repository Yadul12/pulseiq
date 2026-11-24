import React, { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Bell,
  BookOpen,
  CalendarRange,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  Compass,
  Database,
  FileBarChart2,
  FolderKanban,
  LayoutDashboard,
  LogOut,
  Radio,
  Search,
  Shield,
  SlidersHorizontal,
  User as UserIcon,
  X,
} from "lucide-react";
import { apiRequest } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useWorkspace } from "../context/WorkspaceContext";
import type { AlertItem, DataSource, MonitoringTopic } from "../types";
import { EvidenceDrawer } from "./EvidenceDrawer";
import { SentimentBadge } from "./Badges";

const TIME_RANGES = [
  { label: "24h", days: 1 },
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "All", days: 365 },
];

export const Layout: React.FC = () => {
  const { user, logout } = useAuth();
  const { days, setDays, sourceId, setSourceId, openRecordInspector, toasts, dismissToast } = useWorkspace();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [collapsed, setCollapsed] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  const { data: topics = [] } = useQuery<MonitoringTopic[]>({
    queryKey: ["topics-sidebar"],
    queryFn: () => apiRequest<MonitoringTopic[]>("/topics?status=active"),
  });

  const { data: sources = [] } = useQuery<DataSource[]>({
    queryKey: ["sources-list"],
    queryFn: () => apiRequest<DataSource[]>("/sources"),
  });

  const { data: alertsData } = useQuery<{ unread_count: number; items: AlertItem[] }>({
    queryKey: ["alerts"],
    queryFn: () => apiRequest<{ unread_count: number; items: AlertItem[] }>("/alerts"),
    refetchInterval: 30000,
  });

  const { data: searchResults } = useQuery<{
    topics: Array<{ id: number; name: string; category: string }>;
    events: Array<{ id: number; title: string; location: string }>;
    reports: Array<{ id: number; title: string; status: string }>;
    records: Array<{ id: number; title?: string; excerpt: string; topic: string; sentiment: string }>;
  }>({
    queryKey: ["global-search", searchTerm],
    queryFn: () => apiRequest(`/search?q=${encodeURIComponent(searchTerm.trim())}`),
    enabled: searchTerm.trim().length >= 2,
  });

  const readAllMutation = useMutation({
    mutationFn: () => apiRequest("/alerts/read-all", { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });

  const readOneMutation = useMutation({
    mutationFn: (id: number) => apiRequest(`/alerts/${id}/read`, { method: "PATCH" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setSearchOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const navGroups = [
    {
      label: "Intelligence",
      items: [
        { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
        { to: "/topics", label: "Monitoring Topics", icon: SlidersHorizontal },
        { to: "/explorer", label: "Topic Explorer", icon: Compass },
        { to: "/live", label: "Live Monitoring", icon: Radio },
        { to: "/events", label: "Event Intelligence", icon: CalendarRange },
      ],
    },
    {
      label: "Analysis & Briefing",
      items: [
        { to: "/workspace", label: "Analyst Workspace", icon: FolderKanban },
        { to: "/reports", label: "Insight Reports", icon: FileBarChart2 },
      ],
    },
    {
      label: "Pipeline & Governance",
      items: [
        { to: "/sources", label: "Data Sources", icon: Database },
        { to: "/methodology", label: "Methodology", icon: BookOpen },
        { to: "/admin", label: "Audit & Access", icon: Shield },
      ],
    },
  ];

  const initials =
    user?.full_name
      .split(" ")
      .map((s) => s[0])
      .join("")
      .slice(0, 2)
      .toUpperCase() || "AN";

  return (
    <div className="flex h-screen w-full overflow-hidden bg-workspace">
      {/* Compact Deep Navy Enterprise Sidebar */}
      <aside
        className={`flex shrink-0 flex-col bg-navy-900 text-slate-300 transition-all duration-200 ${
          collapsed ? "w-16" : "w-60"
        }`}
      >
        {/* Brand Header */}
        <div className="flex h-[52px] items-center justify-between border-b border-navy-700/70 px-3.5">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-indigo-600 text-white shadow-sm">
              <Activity className="h-4 w-4" />
            </div>
            {!collapsed && (
              <div className="leading-tight">
                <div className="text-[13px] font-semibold tracking-tight text-white">PulseIQ</div>
                <div className="text-[9px] font-medium uppercase tracking-[0.14em] text-slate-400">
                  Public Intelligence
                </div>
              </div>
            )}
          </div>
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="rounded p-1 text-slate-400 transition hover:bg-navy-800 hover:text-white"
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
          </button>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 overflow-y-auto px-2.5 py-3 space-y-4">
          {navGroups.map((group) => (
            <div key={group.label}>
              {!collapsed && (
                <div className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-[0.09em] text-slate-500">
                  {group.label}
                </div>
              )}
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end={item.end}
                      title={collapsed ? item.label : undefined}
                      className={({ isActive }) =>
                        `flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition ${
                          isActive
                            ? "bg-indigo-600/20 text-white border-l-2 border-indigo-400"
                            : "text-slate-300/90 hover:bg-navy-800/80 hover:text-white"
                        }`
                      }
                    >
                      <Icon className="h-3.5 w-3.5 shrink-0 opacity-90" />
                      {!collapsed && <span className="truncate">{item.label}</span>}
                    </NavLink>
                  );
                })}
              </div>
            </div>
          ))}

          {/* Topic Quick Navigation */}
          {!collapsed && topics.length > 0 && (
            <div className="border-t border-navy-700/70 pt-3">
              <div className="mb-1.5 flex items-center justify-between px-2">
                <span className="text-[10px] font-semibold uppercase tracking-[0.09em] text-slate-500">
                  Active Monitors
                </span>
                <span className="font-mono text-[10px] text-slate-500">{topics.length}</span>
              </div>
              <div className="space-y-0.5">
                {topics.slice(0, 6).map((t) => (
                  <button
                    key={t.id}
                    onClick={() => navigate(`/explorer?topicId=${t.id}`)}
                    className="flex w-full items-center justify-between rounded px-2 py-1 text-left text-[11px] text-slate-300/85 transition hover:bg-navy-800 hover:text-white"
                  >
                    <span className="flex items-center gap-1.5 truncate">
                      <span
                        className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                          t.has_emerging_trend ? "bg-amber-400" : "bg-indigo-400/70"
                        }`}
                      />
                      <span className="truncate">{t.name}</span>
                    </span>
                    {t.has_emerging_trend && (
                      <span className="ml-1 shrink-0 rounded bg-amber-500/20 px-1 text-[9px] font-semibold text-amber-300">
                        SPIKE
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}
        </nav>

        {/* Bottom Ethics & Provenance Footer */}
        {!collapsed && (
          <div className="border-t border-navy-700/70 px-3 py-2.5 text-[10px] text-slate-400">
            <div className="flex items-center gap-1.5 font-medium text-slate-300">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              Public-Data Governance Active
            </div>
            <p className="mt-0.5 leading-snug text-slate-500">
              Aggregate civic analytics only. Synthetic sources explicitly labelled.
            </p>
          </div>
        )}
      </aside>

      {/* Right Main Area */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {/* Top Analytical Utility Bar */}
        <header className="z-30 flex h-[52px] shrink-0 items-center justify-between gap-3 border-b border-slate-200 bg-white px-4">
          {/* Global Search */}
          <div ref={searchRef} className="relative w-full max-w-md">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchTerm}
              onFocus={() => setSearchOpen(true)}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setSearchOpen(true);
              }}
              placeholder="Search records, monitoring topics, civic events, reports..."
              className="w-full rounded-md border border-slate-200 bg-slate-50/70 py-1.5 pl-8 pr-7 text-xs text-slate-800 placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}

            {searchOpen && searchTerm.trim().length >= 2 && searchResults && (
              <div className="absolute left-0 top-full mt-1.5 w-full min-w-[420px] rounded-lg border border-slate-200 bg-white p-2 shadow-xl">
                {searchResults.topics.length === 0 &&
                searchResults.events.length === 0 &&
                searchResults.reports.length === 0 &&
                searchResults.records.length === 0 ? (
                  <div className="p-3 text-center text-xs text-slate-500">No matches for "{searchTerm}"</div>
                ) : (
                  <div className="max-h-96 overflow-y-auto space-y-2.5 p-1">
                    {searchResults.topics.length > 0 && (
                      <div>
                        <div className="micro-label px-2 pb-1">Monitoring Topics</div>
                        {searchResults.topics.map((t) => (
                          <button
                            key={t.id}
                            onClick={() => {
                              setSearchOpen(false);
                              navigate(`/explorer?topicId=${t.id}`);
                            }}
                            className="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-xs hover:bg-slate-50"
                          >
                            <span className="font-medium text-slate-800">{t.name}</span>
                            <span className="text-[10px] text-slate-500">{t.category}</span>
                          </button>
                        ))}
                      </div>
                    )}
                    {searchResults.events.length > 0 && (
                      <div>
                        <div className="micro-label px-2 pb-1">Civic Events</div>
                        {searchResults.events.map((ev) => (
                          <button
                            key={ev.id}
                            onClick={() => {
                              setSearchOpen(false);
                              navigate(`/events?eventId=${ev.id}`);
                            }}
                            className="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-xs hover:bg-slate-50"
                          >
                            <span className="font-medium text-slate-800">{ev.title}</span>
                            <span className="text-[10px] text-slate-500">{ev.location}</span>
                          </button>
                        ))}
                      </div>
                    )}
                    {searchResults.reports.length > 0 && (
                      <div>
                        <div className="micro-label px-2 pb-1">Insight Reports</div>
                        {searchResults.reports.map((rp) => (
                          <button
                            key={rp.id}
                            onClick={() => {
                              setSearchOpen(false);
                              navigate(`/reports?reportId=${rp.id}`);
                            }}
                            className="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-xs hover:bg-slate-50"
                          >
                            <span className="font-medium text-slate-800">{rp.title}</span>
                            <span className="text-[10px] uppercase text-slate-500">{rp.status}</span>
                          </button>
                        ))}
                      </div>
                    )}
                    {searchResults.records.length > 0 && (
                      <div>
                        <div className="micro-label px-2 pb-1">Source Records</div>
                        {searchResults.records.map((rec) => (
                          <button
                            key={rec.id}
                            onClick={() => {
                              setSearchOpen(false);
                              openRecordInspector(rec.id);
                            }}
                            className="block w-full rounded px-2 py-1.5 text-left hover:bg-slate-50"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-mono text-[10px] text-indigo-700">REC-{rec.id}</span>
                              <SentimentBadge sentiment={rec.sentiment} />
                            </div>
                            <p className="mt-0.5 line-clamp-1 text-xs text-slate-700">{rec.excerpt}</p>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Global Analytical Controls */}
          <div className="flex items-center gap-2.5">
            {/* Time-Range Selector */}
            <div className="hidden items-center rounded-md border border-slate-200 bg-slate-50 p-0.5 md:flex">
              {TIME_RANGES.map((tr) => (
                <button
                  key={tr.days}
                  onClick={() => setDays(tr.days)}
                  className={`rounded px-2 py-1 text-[11px] font-medium transition tabular-nums ${
                    days === tr.days
                      ? "bg-white text-indigo-700 shadow-sm"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  {tr.label}
                </button>
              ))}
            </div>

            {/* Source Filter */}
            <select
              aria-label="Global source filter"
              value={sourceId ?? ""}
              onChange={(e) => setSourceId(e.target.value ? Number(e.target.value) : null)}
              className="hidden max-w-[190px] rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-medium text-slate-700 focus:border-indigo-500 focus:outline-none lg:block"
            >
              <option value="">All Sources ({sources.length})</option>
              {sources.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>

            {/* Notification Centre */}
            <div className="relative">
              <button
                onClick={() => {
                  setNotifOpen((o) => !o);
                  setProfileOpen(false);
                }}
                className="relative rounded-md border border-slate-200 p-1.5 text-slate-600 transition hover:bg-slate-50 hover:text-slate-900"
                title="Notification Centre"
              >
                <Bell className="h-4 w-4" />
                {(alertsData?.unread_count ?? 0) > 0 && (
                  <span className="absolute -right-1 -top-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-rose-600 px-1 font-mono text-[9px] font-bold text-white">
                    {alertsData?.unread_count}
                  </span>
                )}
              </button>

              {notifOpen && (
                <div className="absolute right-0 top-full mt-2 w-80 rounded-lg border border-slate-200 bg-white shadow-xl z-40">
                  <div className="flex items-center justify-between border-b border-slate-100 px-3.5 py-2.5">
                    <span className="text-xs font-semibold text-slate-900">Notification Centre</span>
                    <button
                      onClick={() => readAllMutation.mutate()}
                      className="flex items-center gap-1 text-[11px] font-medium text-indigo-700 hover:underline"
                    >
                      <CheckCheck className="h-3 w-3" /> Mark all read
                    </button>
                  </div>
                  <div className="max-h-80 overflow-y-auto divide-y divide-slate-100">
                    {(alertsData?.items ?? []).length === 0 ? (
                      <p className="p-4 text-center text-xs text-slate-500">No active intelligence alerts.</p>
                    ) : (
                      (alertsData?.items ?? []).map((a) => (
                        <div
                          key={a.id}
                          onClick={() => {
                            if (!a.is_read) readOneMutation.mutate(a.id);
                          }}
                          className={`cursor-pointer px-3.5 py-2.5 text-xs transition hover:bg-slate-50 ${
                            a.is_read ? "opacity-65" : "bg-indigo-50/25"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-semibold text-slate-900">{a.title}</span>
                            <span
                              className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                                a.severity === "critical"
                                  ? "bg-rose-500"
                                  : a.severity === "warning"
                                  ? "bg-amber-500"
                                  : "bg-indigo-500"
                              }`}
                            />
                          </div>
                          <p className="mt-0.5 text-[11px] leading-snug text-slate-600">{a.message}</p>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Analyst Profile Menu */}
            <div className="relative">
              <button
                onClick={() => {
                  setProfileOpen((o) => !o);
                  setNotifOpen(false);
                }}
                className="flex items-center gap-2 rounded-md border border-slate-200 bg-white px-2 py-1 text-left transition hover:bg-slate-50"
              >
                <span className="flex h-6 w-6 items-center justify-center rounded bg-navy-900 font-mono text-[11px] font-semibold text-white">
                  {initials}
                </span>
                <div className="hidden leading-tight sm:block">
                  <div className="text-[11px] font-semibold text-slate-800">{user?.full_name}</div>
                  <div className="font-mono text-[9px] uppercase tracking-wide text-indigo-700">
                    {user?.role.replace("_", " ")}
                  </div>
                </div>
              </button>

              {profileOpen && (
                <div className="absolute right-0 top-full mt-2 w-64 rounded-lg border border-slate-200 bg-white p-3 shadow-xl z-40">
                  <div className="flex items-start gap-2.5 border-b border-slate-100 pb-2.5">
                    <div className="flex h-8 w-8 items-center justify-center rounded bg-indigo-50 text-indigo-700">
                      <UserIcon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-xs font-semibold text-slate-900">{user?.full_name}</p>
                      <p className="truncate text-[11px] text-slate-500">{user?.email}</p>
                      <p className="mt-0.5 text-[10px] font-medium text-indigo-700">{user?.department}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      logout();
                      navigate("/login");
                    }}
                    className="mt-2 flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-xs font-medium text-rose-700 transition hover:bg-rose-50"
                  >
                    <LogOut className="h-3.5 w-3.5" />
                    Sign Out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Scrollable Workspace Content */}
        <main className="flex-1 overflow-y-auto px-5 py-4">
          <Outlet />
        </main>
      </div>

      {/* Global Record Evidence & Override Drawer */}
      <EvidenceDrawer />

      {/* Toast Notifications */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`flex max-w-sm items-start justify-between gap-3 rounded-lg border px-3.5 py-2.5 text-xs shadow-lg ${
              t.type === "error"
                ? "border-rose-200 bg-rose-50 text-rose-900"
                : t.type === "success"
                ? "border-emerald-200 bg-white text-slate-900"
                : "border-indigo-200 bg-white text-slate-900"
            }`}
          >
            <div>
              <p className="font-semibold">{t.title}</p>
              {t.detail && <p className="mt-0.5 text-[11px] text-slate-600">{t.detail}</p>}
            </div>
            <button onClick={() => dismissToast(t.id)} className="text-slate-400 hover:text-slate-700">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};
