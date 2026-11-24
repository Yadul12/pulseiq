import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Download,
  FileText,
  Plus,
  ShieldAlert,
  X,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiRequest, downloadFile } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useWorkspace } from "../context/WorkspaceContext";
import type { CivicEvent, MonitoringTopic, ReportSummary } from "../types";
import { ProvenanceBadge, SENTIMENT_COLORS, SentimentBadge, StatusPill } from "../components/Badges";

interface ReportDetail {
  id: number;
  title: string;
  subtitle: string;
  time_range_start: string;
  time_range_end: string;
  status: "draft" | "reviewed" | "published";
  executive_summary: string;
  sections: {
    topic_overview?: {
      scope_name: string;
      description: string;
      keywords: string[];
      top_entities: string[];
      language_distribution: Record<string, number>;
      source_distribution: Record<string, number>;
    };
    discussion_trends?: {
      peak_date: string;
      peak_volume: number;
      daily_series: Array<{ date: string; volume: number; avg_sentiment: number }>;
    };
    aggregate_sentiment?: {
      avg_score: number;
      avg_confidence: number;
      breakdown: Record<string, number>;
      percentages: Record<string, number>;
      caveat: string;
    };
    key_themes?: Array<{
      cluster_id: number;
      label: string;
      record_count: number;
      trend_velocity: number;
      growth_pct: number;
      is_emerging: boolean;
      summary: string;
    }>;
    analyst_verified_findings?: Array<{
      processed_record_id: number;
      section_tag: string;
      note: string;
    }>;
  };
  key_metrics: Record<string, number>;
  evidence: Array<{
    processed_record_id: number;
    citation_tag: string;
    source_name: string;
    is_synthetic: boolean;
    provenance_label: string;
    published_at: string;
    original_text: string;
    effective_topic: string;
    effective_sentiment: string;
    sentiment_confidence: number;
    is_verified: boolean;
    is_overridden: boolean;
  }>;
  methodology_notes: string;
  data_limitations: string;
  provenance_disclosure: string;
  generated_by_name: string;
  created_at: string;
}

export const InsightReportsPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const { canWrite } = useAuth();
  const { openRecordInspector, pushToast } = useWorkspace();
  const queryClient = useQueryClient();

  const [selectedId, setSelectedId] = useState<number | null>(
    searchParams.get("reportId") ? Number(searchParams.get("reportId")) : null
  );
  const [modalOpen, setModalOpen] = useState(false);

  const [title, setTitle] = useState("");
  const [subtitle, setSubtitle] = useState("Evidence-Backed Public Discussion & Sentiment Assessment");
  const [topicId, setTopicId] = useState<string>("");
  const [eventId, setEventId] = useState<string>("");
  const [days, setDays] = useState(30);

  const { data: reports = [], isLoading: loadingList } = useQuery<ReportSummary[]>({
    queryKey: ["reports-list"],
    queryFn: () => apiRequest<ReportSummary[]>("/reports"),
  });

  const { data: topics = [] } = useQuery<MonitoringTopic[]>({
    queryKey: ["topics-all"],
    queryFn: () => apiRequest<MonitoringTopic[]>("/topics"),
  });

  const { data: events = [] } = useQuery<CivicEvent[]>({
    queryKey: ["events-list"],
    queryFn: () => apiRequest<CivicEvent[]>("/events"),
  });

  useEffect(() => {
    if (!selectedId && reports.length > 0) {
      setSelectedId(reports[0].id);
    }
  }, [reports, selectedId]);

  const { data: detail, isLoading: loadingDetail } = useQuery<ReportDetail>({
    queryKey: ["report-detail", selectedId],
    queryFn: () => apiRequest<ReportDetail>(`/reports/${selectedId}`),
    enabled: selectedId !== null,
  });

  const generateMutation = useMutation({
    mutationFn: () =>
      apiRequest<{ id: number; title: string }>("/reports/generate", {
        method: "POST",
        body: JSON.stringify({
          title,
          subtitle,
          monitoring_topic_id: topicId ? Number(topicId) : null,
          event_id: eventId ? Number(eventId) : null,
          days,
        }),
      }),
    onSuccess: (created) => {
      pushToast("success", "Grounded insight report generated", `"${created.title}" compiled from retrieved source evidence.`);
      queryClient.invalidateQueries({ queryKey: ["reports-list"] });
      setSelectedId(created.id);
      setModalOpen(false);
      setTitle("");
    },
    onError: (err: Error) => pushToast("error", "Report generation failed", err.message),
  });

  const publishMutation = useMutation({
    mutationFn: (status: "reviewed" | "published") =>
      apiRequest(`/reports/${selectedId}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
    onSuccess: (_res, status) => {
      pushToast("success", "Report status updated", `Brief marked as ${status}.`);
      queryClient.invalidateQueries({ queryKey: ["report-detail", selectedId] });
      queryClient.invalidateQueries({ queryKey: ["reports-list"] });
    },
  });

  const handleExport = async (format: "markdown" | "csv") => {
    if (!selectedId) return;
    try {
      await downloadFile(
        `/reports/${selectedId}/export?format=${format}`,
        `pulseiq_report_${selectedId}.${format === "markdown" ? "md" : "csv"}`
      );
      pushToast("success", "Report exported", `Downloaded ${format.toUpperCase()} package.`);
    } catch (err) {
      pushToast("error", "Export failed", err instanceof Error ? err.message : "Unable to export.");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-base font-semibold tracking-tight text-slate-900">Insight Reports</h1>
          <p className="text-xs text-slate-500">
            Executive intelligence briefings grounded strictly in retrieved source records, verified annotations, and transparent methodology disclosures
          </p>
        </div>
        {canWrite && (
          <button onClick={() => setModalOpen(true)} className="btn-primary">
            <Plus className="h-3.5 w-3.5" /> Generate Grounded Report
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* Reports List */}
        <div className="surface-panel overflow-hidden lg:col-span-3">
          <div className="border-b border-slate-200 px-3.5 py-2.5">
            <span className="micro-label">Saved Briefings ({reports.length})</span>
          </div>
          <div className="divide-y divide-slate-100">
            {loadingList ? (
              <div className="p-4 text-xs text-slate-400">Loading reports...</div>
            ) : (
              reports.map((rp) => (
                <button
                  key={rp.id}
                  onClick={() => setSelectedId(rp.id)}
                  className={`block w-full px-3.5 py-3 text-left transition ${
                    selectedId === rp.id
                      ? "bg-indigo-50/70 border-l-2 border-indigo-700"
                      : "hover:bg-slate-50"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-xs font-semibold text-slate-900 line-clamp-2">{rp.title}</span>
                    <StatusPill status={rp.status} />
                  </div>
                  <div className="mt-1.5 flex items-center justify-between font-mono text-[10px] text-slate-400">
                    <span>{rp.evidence_count} citations</span>
                    <span>{rp.created_at.slice(0, 10)}</span>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Full Grounded Report Document */}
        <div className="lg:col-span-9">
          {loadingDetail || !detail ? (
            <div className="surface-panel h-96 animate-pulse" />
          ) : (
            <article className="surface-panel overflow-hidden">
              {/* Document Header */}
              <div className="border-b border-slate-200 bg-navy-900 px-6 py-5 text-white">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] uppercase tracking-widest text-indigo-300">
                        PULSEIQ INTELLIGENCE BRIEF · RPT-{detail.id}
                      </span>
                      <StatusPill status={detail.status} />
                    </div>
                    <h2 className="mt-1.5 text-lg font-semibold tracking-tight">{detail.title}</h2>
                    <p className="mt-0.5 text-xs text-slate-300">{detail.subtitle}</p>
                    <div className="mt-2.5 flex flex-wrap gap-4 font-mono text-[10px] text-slate-400">
                      <span>
                        Window: {detail.time_range_start.slice(0, 10)} &rarr; {detail.time_range_end.slice(0, 10)}
                      </span>
                      <span>Author: {detail.generated_by_name}</span>
                      <span>Generated: {new Date(detail.created_at).toLocaleString()}</span>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {canWrite && detail.status !== "published" && (
                      <button
                        onClick={() => publishMutation.mutate("published")}
                        className="inline-flex items-center gap-1 rounded bg-emerald-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" /> Publish
                      </button>
                    )}
                    <button
                      onClick={() => handleExport("markdown")}
                      className="inline-flex items-center gap-1 rounded border border-navy-600 bg-navy-800 px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:bg-navy-700"
                    >
                      <FileText className="h-3.5 w-3.5" /> Export MD
                    </button>
                    <button
                      onClick={() => handleExport("csv")}
                      className="inline-flex items-center gap-1 rounded border border-navy-600 bg-navy-800 px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:bg-navy-700"
                    >
                      <Download className="h-3.5 w-3.5" /> Evidence CSV
                    </button>
                  </div>
                </div>
              </div>

              {/* Provenance Banner */}
              <div className="border-b border-amber-200/80 bg-amber-50/70 px-6 py-2 text-[11px] font-medium text-amber-900">
                {detail.provenance_disclosure}
              </div>

              <div className="space-y-6 p-6 text-xs leading-relaxed text-slate-700">
                {/* 1. Executive Summary */}
                <section>
                  <h3 className="micro-label text-indigo-800 mb-1.5">1. Executive Summary (Grounded in Source Records)</h3>
                  <p className="rounded-md border border-slate-200 bg-slate-50/60 p-4 text-[13px] leading-relaxed text-slate-800">
                    {detail.executive_summary}
                  </p>
                  <div className="mt-3 grid grid-cols-2 gap-2.5 sm:grid-cols-5">
                    {[
                      ["Records Analyzed", (detail.key_metrics.total_records ?? 0).toLocaleString()],
                      ["Active Sources", String(detail.key_metrics.unique_sources ?? 0)],
                      ["Mean Polarity", `${(detail.key_metrics.avg_sentiment ?? 0) >= 0 ? "+" : ""}${(detail.key_metrics.avg_sentiment ?? 0).toFixed(2)}`],
                      ["Analyst Overrides", String(detail.key_metrics.analyst_overrides ?? 0)],
                      ["Verified Notes", String(detail.key_metrics.verified_evidence_count ?? 0)],
                    ].map(([lbl, val]) => (
                      <div key={lbl} className="rounded border border-slate-200 bg-white px-3 py-2">
                        <div className="text-[10px] uppercase text-slate-500">{lbl}</div>
                        <div className="mt-0.5 font-mono text-sm font-semibold text-slate-900 tabular-nums">{val}</div>
                      </div>
                    ))}
                  </div>
                </section>

                {/* 2. Discussion Trends & 3. Aggregate Sentiment */}
                <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
                  <section className="lg:col-span-7">
                    <h3 className="micro-label text-indigo-800 mb-2">2. Discussion Trends</h3>
                    <div className="h-48 rounded-md border border-slate-200 p-2">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart
                          data={detail.sections.discussion_trends?.daily_series ?? []}
                          margin={{ top: 6, right: 8, left: -18, bottom: 0 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
                          <XAxis
                            dataKey="date"
                            tick={{ fontSize: 10, fill: "#64748B" }}
                            tickFormatter={(v: string) => v.slice(5)}
                          />
                          <YAxis tick={{ fontSize: 10, fill: "#64748B" }} />
                          <Tooltip contentStyle={{ fontSize: "11px" }} />
                          <Area
                            type="monotone"
                            dataKey="volume"
                            stroke="#3730A3"
                            fill="#3730A3"
                            fillOpacity={0.14}
                            strokeWidth={1.8}
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </section>

                  <section className="lg:col-span-5">
                    <h3 className="micro-label text-indigo-800 mb-2">3. Aggregate Sentiment</h3>
                    <div className="rounded-md border border-slate-200 p-3.5 space-y-2.5">
                      {(["positive", "neutral", "mixed", "negative"] as const).map((k) => {
                        const pct = detail.sections.aggregate_sentiment?.percentages?.[k] ?? 0;
                        return (
                          <div key={k}>
                            <div className="flex justify-between text-[11px]">
                              <span className="capitalize font-medium text-slate-700">{k}</span>
                              <span className="font-mono text-slate-600 tabular-nums">{pct}%</span>
                            </div>
                            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                              <div
                                className="h-full rounded-full"
                                style={{ width: `${pct}%`, backgroundColor: SENTIMENT_COLORS[k] }}
                              />
                            </div>
                          </div>
                        );
                      })}
                      <p className="pt-1 text-[10.5px] italic text-slate-500">
                        {detail.sections.aggregate_sentiment?.caveat}
                      </p>
                    </div>
                  </section>
                </div>

                {/* 4. Key Themes & Clusters */}
                {(detail.sections.key_themes ?? []).length > 0 && (
                  <section>
                    <h3 className="micro-label text-indigo-800 mb-2">4. Key Themes & Semantic Clusters</h3>
                    <div className="grid grid-cols-1 gap-2.5 md:grid-cols-2">
                      {(detail.sections.key_themes ?? []).map((th) => (
                        <div key={th.cluster_id} className="rounded-md border border-slate-200 p-3">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-slate-900">{th.label}</span>
                            <span className="font-mono text-[10px] text-indigo-700 tabular-nums">
                              {th.record_count.toLocaleString()} recs · Z={th.trend_velocity.toFixed(2)}
                            </span>
                          </div>
                          <p className="mt-1 text-[11px] text-slate-600">{th.summary}</p>
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {/* 5. Traceable Representative Source Evidence */}
                <section>
                  <h3 className="micro-label text-indigo-800 mb-2">
                    5. Representative Source Evidence ({detail.evidence.length} Traceable Citations)
                  </h3>
                  <div className="overflow-hidden rounded-md border border-slate-200">
                    <table className="w-full text-left text-xs">
                      <thead className="border-b border-slate-200 bg-slate-50 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                        <tr>
                          <th className="px-3 py-2">Citation</th>
                          <th className="px-3 py-2">Original Source Quote</th>
                          <th className="px-3 py-2">Source / Provenance</th>
                          <th className="px-3 py-2">Tone</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {detail.evidence.map((ev) => (
                          <tr
                            key={ev.processed_record_id}
                            onClick={() => openRecordInspector(ev.processed_record_id)}
                            className="cursor-pointer hover:bg-slate-50"
                          >
                            <td className="px-3 py-2 font-mono text-[11px] font-semibold text-indigo-700 whitespace-nowrap">
                              [{ev.citation_tag}]
                              {ev.is_verified && (
                                <div className="text-[9px] text-emerald-700">VERIFIED</div>
                              )}
                            </td>
                            <td className="max-w-md px-3 py-2 text-slate-800">"{ev.original_text}"</td>
                            <td className="px-3 py-2">
                              <div className="text-[11px] text-slate-700">{ev.source_name}</div>
                              <div className="mt-0.5 flex items-center gap-1">
                                <ProvenanceBadge isSynthetic={ev.is_synthetic} label={ev.provenance_label} />
                                <span className="font-mono text-[10px] text-slate-400">
                                  {ev.published_at.slice(0, 10)}
                                </span>
                              </div>
                            </td>
                            <td className="px-3 py-2">
                              <SentimentBadge
                                sentiment={ev.effective_sentiment}
                                confidence={ev.sentiment_confidence}
                                overridden={ev.is_overridden}
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>

                {/* 6. Methodology & 7. Data Limitations */}
                <div className="grid grid-cols-1 gap-4 border-t border-slate-200 pt-4 md:grid-cols-2">
                  <section>
                    <h3 className="micro-label text-slate-700 mb-1.5">6. Methodology</h3>
                    <p className="text-[11px] leading-relaxed text-slate-600">{detail.methodology_notes}</p>
                  </section>
                  <section>
                    <h3 className="micro-label text-amber-800 mb-1.5 flex items-center gap-1">
                      <ShieldAlert className="h-3.5 w-3.5" /> 7. Data Limitations
                    </h3>
                    <pre className="whitespace-pre-wrap font-sans text-[11px] leading-relaxed text-slate-600">
                      {detail.data_limitations}
                    </pre>
                  </section>
                </div>
              </div>
            </article>
          )}
        </div>
      </div>

      {/* Generate Report Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="w-full max-w-lg rounded-lg border border-slate-200 bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3.5">
              <h2 className="text-sm font-semibold text-slate-900">Generate Grounded Intelligence Report</h2>
              <button onClick={() => setModalOpen(false)} className="text-slate-400 hover:text-slate-700">
                <X className="h-4 w-4" />
              </button>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                generateMutation.mutate();
              }}
              className="space-y-3.5 p-5"
            >
              <div>
                <label className="micro-label block mb-1">Report Title</label>
                <input
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Q4 Stormwater & Transit Resilience Brief"
                  className="input-field"
                />
              </div>
              <div>
                <label className="micro-label block mb-1">Subtitle</label>
                <input value={subtitle} onChange={(e) => setSubtitle(e.target.value)} className="input-field" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="micro-label block mb-1">Monitoring Topic Scope</label>
                  <select value={topicId} onChange={(e) => setTopicId(e.target.value)} className="input-field">
                    <option value="">All Topics</option>
                    {topics.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="micro-label block mb-1">Linked Event (Optional)</label>
                  <select value={eventId} onChange={(e) => setEventId(e.target.value)} className="input-field">
                    <option value="">None</option>
                    {events.map((ev) => (
                      <option key={ev.id} value={ev.id}>
                        {ev.title}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="micro-label block mb-1">Analysis Time Window (Days)</label>
                <input
                  type="number"
                  min={1}
                  max={180}
                  value={days}
                  onChange={(e) => setDays(Number(e.target.value))}
                  className="input-field"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setModalOpen(false)} className="btn-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={generateMutation.isPending} className="btn-primary">
                  {generateMutation.isPending ? "Compiling Evidence..." : "Generate Grounded Report"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
