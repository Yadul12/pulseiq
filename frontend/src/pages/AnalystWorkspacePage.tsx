import React, { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bookmark,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Download,
  Eye,
  Search,
  ShieldAlert,
} from "lucide-react";
import { apiRequest, downloadFile } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useWorkspace } from "../context/WorkspaceContext";
import type { MonitoringTopic, RecordListItem } from "../types";
import { ConfidenceBar, ProvenanceBadge, SentimentBadge, StatusPill } from "../components/Badges";

type WorkspaceTab = "review" | "bookmarked" | "verified" | "overridden" | "all";

export const AnalystWorkspacePage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const { canWrite } = useAuth();
  const { openRecordInspector, pushToast } = useWorkspace();
  const queryClient = useQueryClient();

  const initialTab = (searchParams.get("tab") as WorkspaceTab) || "review";
  const [tab, setTab] = useState<WorkspaceTab>(initialTab);
  const [q, setQ] = useState("");
  const [topicId, setTopicId] = useState<string>("");
  const [sentiment, setSentiment] = useState("all");
  const [language, setLanguage] = useState("all");
  const [page, setPage] = useState(1);

  const { data: topics = [] } = useQuery<MonitoringTopic[]>({
    queryKey: ["topics-all"],
    queryFn: () => apiRequest<MonitoringTopic[]>("/topics"),
  });

  const buildQueryParams = () => {
    const p = new URLSearchParams({ page: String(page), page_size: "18" });
    if (q.trim()) p.set("q", q.trim());
    if (topicId) p.set("topic_id", topicId);
    if (sentiment !== "all") p.set("sentiment", sentiment);
    if (language !== "all") p.set("language", language);
    if (tab === "review") p.set("status", "needs_review");
    if (tab === "bookmarked") p.set("bookmarked", "true");
    if (tab === "verified") p.set("verified", "true");
    if (tab === "overridden") p.set("overridden", "true");
    return p;
  };

  const qs = buildQueryParams().toString();

  const { data, isLoading } = useQuery<{
    total: number;
    page: number;
    total_pages: number;
    items: RecordListItem[];
  }>({
    queryKey: ["records", "workspace", qs],
    queryFn: () => apiRequest(`/records?${qs}`),
  });

  const quickToggle = useMutation({
    mutationFn: ({ id, is_bookmarked, is_verified }: { id: number; is_bookmarked?: boolean; is_verified?: boolean }) =>
      apiRequest(`/records/${id}/annotation`, {
        method: "PUT",
        body: JSON.stringify({ is_bookmarked, is_verified }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["records"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
    },
    onError: (err: Error) => pushToast("error", "Update failed", err.message),
  });

  const handleExportCsv = async () => {
    try {
      const exportParams = buildQueryParams();
      exportParams.delete("page");
      exportParams.delete("page_size");
      await downloadFile(`/records/export.csv?${exportParams.toString()}`, `pulseiq_workspace_${tab}.csv`);
      pushToast("success", "CSV exported", "Filtered evidence records downloaded.");
    } catch (err) {
      pushToast("error", "Export failed", err instanceof Error ? err.message : "Unable to export CSV.");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-base font-semibold tracking-tight text-slate-900">Analyst Workspace</h1>
          <p className="text-xs text-slate-500">
            Audit low-confidence predictions, verify primary evidence, apply classification overrides, tag report sections, and export findings
          </p>
        </div>
        <button onClick={handleExportCsv} className="btn-secondary">
          <Download className="h-3.5 w-3.5" />
          Export Filtered CSV
        </button>
      </div>

      {/* Queue Tabs & Filters */}
      <div className="surface-panel p-3 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2.5">
          <div className="flex flex-wrap gap-1">
            {[
              { id: "review", label: "Needs Review (<56% conf)" },
              { id: "bookmarked", label: "Bookmarked" },
              { id: "verified", label: "Verified Insights" },
              { id: "overridden", label: "Analyst Overrides" },
              { id: "all", label: "All Indexed Records" },
            ].map((t) => (
              <button
                key={t.id}
                onClick={() => {
                  setTab(t.id as WorkspaceTab);
                  setPage(1);
                }}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
                  tab === t.id
                    ? "bg-navy-900 text-white"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          <span className="font-mono text-[11px] text-slate-500 tabular-nums">
            {(data?.total ?? 0).toLocaleString()} records in view
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
            <input
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
              placeholder="Search normalized text, title, or external ID..."
              className="input-field pl-8"
            />
          </div>
          <select
            value={topicId}
            onChange={(e) => {
              setTopicId(e.target.value);
              setPage(1);
            }}
            className="input-field w-48"
          >
            <option value="">All Topics</option>
            {topics.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          <select
            value={sentiment}
            onChange={(e) => {
              setSentiment(e.target.value);
              setPage(1);
            }}
            className="input-field w-36"
          >
            <option value="all">All Sentiment</option>
            <option value="positive">Positive</option>
            <option value="neutral">Neutral</option>
            <option value="mixed">Mixed</option>
            <option value="negative">Negative</option>
          </select>
          <select
            value={language}
            onChange={(e) => {
              setLanguage(e.target.value);
              setPage(1);
            }}
            className="input-field w-32"
          >
            <option value="all">All Langs</option>
            <option value="en">EN</option>
            <option value="es">ES</option>
            <option value="fr">FR</option>
            <option value="de">DE</option>
            <option value="pt">PT</option>
          </select>
        </div>
      </div>

      {/* Review Queue Table */}
      <div className="surface-panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-200 bg-slate-50/90 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-2">Record & Content</th>
                <th className="px-3 py-2">Topic / Confidence</th>
                <th className="px-3 py-2">Sentiment</th>
                <th className="px-3 py-2">Source & Status</th>
                <th className="px-3 py-2">Section / Note</th>
                <th className="px-4 py-2 text-right">Analyst Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-slate-400">
                    Loading workspace queue...
                  </td>
                </tr>
              ) : (data?.items ?? []).length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-10 text-center text-slate-500">
                    No records in this workspace view.
                  </td>
                </tr>
              ) : (
                (data?.items ?? []).map((r) => (
                  <tr
                    key={r.id}
                    onClick={() => openRecordInspector(r.id)}
                    className="cursor-pointer hover:bg-slate-50"
                  >
                    <td className="max-w-md px-4 py-2.5">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-[10px] font-semibold text-indigo-700">REC-{r.id}</span>
                        <span className="font-mono text-[10px] uppercase text-slate-400">{r.detected_language}</span>
                        {r.processing_status === "needs_review" && (
                          <span className="inline-flex items-center gap-0.5 text-[10px] font-medium text-amber-700">
                            <ShieldAlert className="h-3 w-3" /> Low conf
                          </span>
                        )}
                      </div>
                      <p className="mt-0.5 line-clamp-2 text-slate-800">{r.original_text}</p>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="max-w-[170px] truncate font-medium text-slate-800">
                        {r.effective_topic}
                      </div>
                      <div className="mt-1">
                        <ConfidenceBar value={r.topic_confidence} />
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <SentimentBadge
                        sentiment={r.effective_sentiment}
                        confidence={r.sentiment_confidence}
                        overridden={r.sentiment_overridden}
                      />
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="max-w-[150px] truncate text-[11px] text-slate-700">{r.source_name}</div>
                      <div className="mt-0.5 flex items-center gap-1">
                        <ProvenanceBadge isSynthetic={r.is_synthetic} label={r.provenance_label} />
                        <StatusPill status={r.processing_status} />
                      </div>
                    </td>
                    <td className="max-w-[180px] px-3 py-2.5">
                      {r.report_section_tag && (
                        <span className="inline-block rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-medium text-indigo-700">
                          {r.report_section_tag}
                        </span>
                      )}
                      {r.analyst_note && (
                        <p className="mt-0.5 line-clamp-1 text-[11px] text-slate-500">{r.analyst_note}</p>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <div className="flex items-center justify-end gap-1">
                        {canWrite && (
                          <>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                quickToggle.mutate({ id: r.id, is_bookmarked: !r.is_bookmarked });
                              }}
                              title="Toggle Bookmark"
                              className={`rounded border p-1.5 transition ${
                                r.is_bookmarked
                                  ? "border-indigo-300 bg-indigo-50 text-indigo-700"
                                  : "border-slate-200 text-slate-400 hover:text-slate-700"
                              }`}
                            >
                              <Bookmark className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                quickToggle.mutate({ id: r.id, is_verified: !r.is_verified });
                              }}
                              title="Toggle Verified Insight"
                              className={`rounded border p-1.5 transition ${
                                r.is_verified
                                  ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                                  : "border-slate-200 text-slate-400 hover:text-slate-700"
                              }`}
                            >
                              <CheckCircle2 className="h-3.5 w-3.5" />
                            </button>
                          </>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            openRecordInspector(r.id);
                          }}
                          title="Inspect, Override & Annotate"
                          className="rounded border border-slate-200 p-1.5 text-slate-600 hover:bg-indigo-50 hover:text-indigo-700"
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {data && data.total_pages > 1 && (
          <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50/70 px-4 py-2 text-xs text-slate-600">
            <span className="font-mono text-[11px] tabular-nums">
              Page {data.page} of {data.total_pages}
            </span>
            <div className="flex gap-1.5">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="btn-secondary px-2 py-1"
              >
                <ChevronLeft className="h-3.5 w-3.5" /> Prev
              </button>
              <button
                disabled={page >= data.total_pages}
                onClick={() => setPage((p) => p + 1)}
                className="btn-secondary px-2 py-1"
              >
                Next <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
