import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Eye,
  GitCompare,
  Layers,
  Network,
  Search,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiRequest } from "../api/client";
import { useWorkspace } from "../context/WorkspaceContext";
import type { ClusterItem, MonitoringTopic, RecordListItem, SentimentBreakdown } from "../types";
import { ConfidenceBar, ProvenanceBadge, SENTIMENT_COLORS, SentimentBadge } from "../components/Badges";

interface ExplorerOverview {
  clusters: ClusterItem[];
  volume_trends: Array<{
    date: string;
    volume: number;
    positive: number;
    neutral: number;
    mixed: number;
    negative: number;
    avg_sentiment: number;
  }>;
  sentiment_distribution: SentimentBreakdown;
  keyword_nodes: Array<{ term: string; count: number }>;
  keyword_relationships: Array<{ source: string; target: string; co_occurrences: number }>;
  top_entities: Array<{ text: string; type: string; count: number }>;
}

interface CompareResponse {
  days: number;
  topic_names: string[];
  summaries: Array<{
    topic_id: number;
    name: string;
    category: string;
    volume: number;
    unique_sources: number;
    avg_sentiment: number;
    sentiment_pct: SentimentBreakdown;
    top_keywords: string[];
  }>;
  daily_comparison: Array<Record<string, string | number>>;
}

const COMPARE_COLORS = ["#3730A3", "#0F766E", "#B4434A", "#B47B2B"];

export const TopicExplorerPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const { days, sourceId, openRecordInspector } = useWorkspace();

  const initialTopicId = searchParams.get("topicId") ? Number(searchParams.get("topicId")) : null;
  const initialClusterId = searchParams.get("clusterId") ? Number(searchParams.get("clusterId")) : null;

  const [mode, setMode] = useState<"explore" | "compare">("explore");
  const [selectedTopicId, setSelectedTopicId] = useState<number | null>(initialTopicId);
  const [selectedClusterId, setSelectedClusterId] = useState<number | null>(initialClusterId);
  const [compareIds, setCompareIds] = useState<number[]>([]);

  const [recSearch, setRecSearch] = useState("");
  const [recSentiment, setRecSentiment] = useState("all");
  const [recPage, setRecPage] = useState(1);

  const { data: topics = [] } = useQuery<MonitoringTopic[]>({
    queryKey: ["topics-all"],
    queryFn: () => apiRequest<MonitoringTopic[]>("/topics"),
  });

  useEffect(() => {
    if (topics.length >= 2 && compareIds.length === 0) {
      setCompareIds([topics[0].id, topics[1].id]);
    }
  }, [topics, compareIds.length]);

  useEffect(() => {
    const tid = searchParams.get("topicId");
    const cid = searchParams.get("clusterId");
    if (tid !== null) setSelectedTopicId(tid ? Number(tid) : null);
    if (cid !== null) setSelectedClusterId(cid ? Number(cid) : null);
  }, [searchParams]);

  const expParams = new URLSearchParams({ days: String(days) });
  if (selectedTopicId) expParams.set("topic_id", String(selectedTopicId));
  if (sourceId) expParams.set("source_id", String(sourceId));

  const { data: explorer, isLoading: loadingExplorer } = useQuery<ExplorerOverview>({
    queryKey: ["explorer", selectedTopicId, days, sourceId],
    queryFn: () => apiRequest<ExplorerOverview>(`/explorer/overview?${expParams.toString()}`),
    enabled: mode === "explore",
  });

  const { data: comparison, isLoading: loadingCompare } = useQuery<CompareResponse>({
    queryKey: ["explorer-compare", compareIds.join(","), days],
    queryFn: () =>
      apiRequest<CompareResponse>(
        `/explorer/compare?topic_ids=${compareIds.join(",")}&days=${days}`
      ),
    enabled: mode === "compare" && compareIds.length > 0,
  });

  const recParams = new URLSearchParams({
    page: String(recPage),
    page_size: "12",
    days: String(days),
  });
  if (selectedTopicId) recParams.set("topic_id", String(selectedTopicId));
  if (selectedClusterId) recParams.set("cluster_id", String(selectedClusterId));
  if (sourceId) recParams.set("source_id", String(sourceId));
  if (recSentiment !== "all") recParams.set("sentiment", recSentiment);
  if (recSearch.trim()) recParams.set("q", recSearch.trim());

  const { data: recordsData, isLoading: loadingRecords } = useQuery<{
    total: number;
    page: number;
    total_pages: number;
    items: RecordListItem[];
  }>({
    queryKey: ["records", "explorer", recParams.toString()],
    queryFn: () => apiRequest(`/records?${recParams.toString()}`),
    enabled: mode === "explore",
  });

  const toggleCompareTopic = (id: number) => {
    setCompareIds((prev) => {
      if (prev.includes(id)) return prev.length > 1 ? prev.filter((x) => x !== id) : prev;
      if (prev.length >= 4) return [...prev.slice(1), id];
      return [...prev, id];
    });
  };

  return (
    <div className="space-y-4">
      {/* Header & Mode Toggle */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-base font-semibold tracking-tight text-slate-900">Topic Explorer</h1>
          <p className="text-xs text-slate-500">
            Semantic sub-theme clusters, keyword co-occurrence relationships, volume trends, and primary source posts
          </p>
        </div>
        <div className="flex items-center gap-2">
          {mode === "explore" && (
            <select
              value={selectedTopicId ?? ""}
              onChange={(e) => {
                const v = e.target.value ? Number(e.target.value) : null;
                setSelectedTopicId(v);
                setSelectedClusterId(null);
                setRecPage(1);
                setSearchParams(v ? { topicId: String(v) } : {});
              }}
              className="input-field w-56"
            >
              <option value="">All Monitoring Topics</option>
              {topics.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          )}
          <div className="flex rounded-md border border-slate-200 bg-white p-0.5">
            <button
              onClick={() => setMode("explore")}
              className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition ${
                mode === "explore" ? "bg-navy-900 text-white" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Layers className="h-3.5 w-3.5" /> Explore
            </button>
            <button
              onClick={() => setMode("compare")}
              className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition ${
                mode === "compare" ? "bg-navy-900 text-white" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <GitCompare className="h-3.5 w-3.5" /> Compare Topics
            </button>
          </div>
        </div>
      </div>

      {/* TOPIC COMPARISON MODE */}
      {mode === "compare" && (
        <div className="space-y-4">
          <div className="surface-panel p-4">
            <div className="micro-label mb-2">Select 2 to 4 Monitoring Topics to Compare ({days}d Window)</div>
            <div className="flex flex-wrap gap-2">
              {topics.map((t) => {
                const active = compareIds.includes(t.id);
                return (
                  <button
                    key={t.id}
                    onClick={() => toggleCompareTopic(t.id)}
                    className={`rounded-md border px-3 py-1.5 text-xs font-medium transition ${
                      active
                        ? "border-indigo-600 bg-indigo-50 text-indigo-900"
                        : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    {t.name}
                  </button>
                );
              })}
            </div>
          </div>

          {loadingCompare ? (
            <div className="h-72 animate-pulse rounded-lg border border-slate-200 bg-white" />
          ) : (
            comparison && (
              <>
                <div className="surface-panel p-4">
                  <h2 className="section-heading mb-3">Comparative Daily Volume Trajectories</h2>
                  <div className="h-64 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={comparison.daily_comparison} margin={{ top: 5, right: 16, left: -16, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
                        <XAxis
                          dataKey="date"
                          tick={{ fontSize: 10, fill: "#64748B" }}
                          tickFormatter={(v: string) => v.slice(5)}
                        />
                        <YAxis tick={{ fontSize: 10, fill: "#64748B" }} />
                        <Tooltip contentStyle={{ fontSize: "11px", borderRadius: "6px" }} />
                        {comparison.topic_names.map((tn, idx) => (
                          <Line
                            key={tn}
                            type="monotone"
                            dataKey={tn}
                            stroke={COMPARE_COLORS[idx % COMPARE_COLORS.length]}
                            strokeWidth={2}
                            dot={false}
                          />
                        ))}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
                  {comparison.summaries.map((s, idx) => (
                    <div key={s.topic_id} className="surface-panel p-4">
                      <div className="flex items-center gap-2">
                        <span
                          className="h-2.5 w-2.5 rounded-sm"
                          style={{ backgroundColor: COMPARE_COLORS[idx % COMPARE_COLORS.length] }}
                        />
                        <h3 className="truncate text-xs font-semibold text-slate-900">{s.name}</h3>
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-2 border-y border-slate-100 py-2.5 text-xs">
                        <div>
                          <div className="micro-label">Volume</div>
                          <div className="font-mono font-semibold text-slate-900 tabular-nums">
                            {s.volume.toLocaleString()}
                          </div>
                        </div>
                        <div>
                          <div className="micro-label">Avg Tone</div>
                          <div className="font-mono font-semibold text-slate-900 tabular-nums">
                            {s.avg_sentiment >= 0 ? "+" : ""}
                            {s.avg_sentiment.toFixed(2)}
                          </div>
                        </div>
                      </div>
                      <div className="mt-2.5 space-y-1 text-[11px]">
                        <div className="flex justify-between">
                          <span className="text-[#23634D]">Positive</span>
                          <span className="font-mono tabular-nums">{s.sentiment_pct.positive}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-600">Neutral / Mixed</span>
                          <span className="font-mono tabular-nums">
                            {(s.sentiment_pct.neutral + s.sentiment_pct.mixed).toFixed(1)}%
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[#99353C]">Negative</span>
                          <span className="font-mono tabular-nums">{s.sentiment_pct.negative}%</span>
                        </div>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-1">
                        {s.top_keywords.slice(0, 4).map((kw) => (
                          <span key={kw} className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-700">
                            {kw}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )
          )}
        </div>
      )}

      {/* EXPLORE MODE */}
      {mode === "explore" && (
        <>
          {/* Semantic Topic Clusters */}
          <div className="surface-panel p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="section-heading">Semantic Topic Clusters (MiniBatchKMeans + c-TF-IDF)</h2>
                <p className="text-[11px] text-slate-500">
                  Click any cluster to filter representative source records below
                </p>
              </div>
              {selectedClusterId && (
                <button
                  onClick={() => {
                    setSelectedClusterId(null);
                    setRecPage(1);
                  }}
                  className="btn-secondary text-[11px]"
                >
                  Clear Cluster Filter
                </button>
              )}
            </div>

            {loadingExplorer ? (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-32 animate-pulse rounded bg-slate-100" />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                {(explorer?.clusters ?? []).slice(0, 9).map((c) => {
                  const isSel = selectedClusterId === c.id;
                  const totalC = Math.max(c.record_count, 1);
                  return (
                    <button
                      key={c.id}
                      onClick={() => {
                        setSelectedClusterId(isSel ? null : c.id);
                        setRecPage(1);
                      }}
                      className={`rounded-md border p-3.5 text-left transition ${
                        isSel
                          ? "border-indigo-600 bg-indigo-50/40 ring-1 ring-indigo-500"
                          : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="truncate text-xs font-semibold text-slate-900">
                            {c.cluster_label}
                          </div>
                          <div className="truncate text-[10px] text-slate-500">{c.topic_name}</div>
                        </div>
                        {c.is_emerging ? (
                          <span className="shrink-0 rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 font-mono text-[9px] font-semibold text-amber-800">
                            Z={c.trend_velocity.toFixed(1)}
                          </span>
                        ) : (
                          <span className="shrink-0 font-mono text-[10px] text-slate-400">
                            Coh {c.coherence_score.toFixed(2)}
                          </span>
                        )}
                      </div>

                      <div className="mt-2 flex flex-wrap gap-1">
                        {c.top_keywords.slice(0, 5).map((k) => (
                          <span
                            key={k}
                            className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-700"
                          >
                            {k}
                          </span>
                        ))}
                      </div>

                      {/* Mini sentiment bar */}
                      <div className="mt-3 flex h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                        {(["positive", "neutral", "mixed", "negative"] as const).map((k) => (
                          <div
                            key={k}
                            style={{
                              width: `${((c.sentiment_breakdown[k] || 0) / totalC) * 100}%`,
                              backgroundColor: SENTIMENT_COLORS[k],
                            }}
                          />
                        ))}
                      </div>
                      <div className="mt-1.5 flex items-center justify-between font-mono text-[10px] text-slate-500 tabular-nums">
                        <span>{c.record_count.toLocaleString()} recs</span>
                        <span>
                          {c.growth_pct >= 0 ? "+" : ""}
                          {c.growth_pct.toFixed(0)}% vs base
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Volume Trends + Keyword Relationships */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
            <div className="surface-panel p-4 lg:col-span-7">
              <h2 className="section-heading">Volume & Sentiment Composition Trend</h2>
              <p className="mb-3 text-[11px] text-slate-500">Stacked daily sentiment volume in selected scope</p>
              <div className="h-56 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={explorer?.volume_trends ?? []} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 10, fill: "#64748B" }}
                      tickFormatter={(v: string) => v.slice(5)}
                    />
                    <YAxis tick={{ fontSize: 10, fill: "#64748B" }} />
                    <Tooltip contentStyle={{ fontSize: "11px", borderRadius: "6px" }} />
                    <Bar dataKey="positive" stackId="s" fill={SENTIMENT_COLORS.positive} />
                    <Bar dataKey="neutral" stackId="s" fill={SENTIMENT_COLORS.neutral} />
                    <Bar dataKey="mixed" stackId="s" fill={SENTIMENT_COLORS.mixed} />
                    <Bar dataKey="negative" stackId="s" fill={SENTIMENT_COLORS.negative} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="surface-panel p-4 lg:col-span-5">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <h2 className="section-heading flex items-center gap-1.5">
                    <Network className="h-3.5 w-3.5 text-indigo-700" />
                    Keyword Co-Occurrence Relationships
                  </h2>
                  <p className="text-[11px] text-slate-500">Strongest term pairs & civic entities in scope</p>
                </div>
              </div>
              <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
                {(explorer?.keyword_relationships ?? []).slice(0, 10).map((edge, idx) => {
                  const maxC = explorer?.keyword_relationships?.[0]?.co_occurrences || 1;
                  const widthPct = Math.max(12, Math.round((edge.co_occurrences / maxC) * 100));
                  return (
                    <div key={idx} className="flex items-center gap-2 text-[11px]">
                      <span className="w-44 truncate font-mono text-slate-700">
                        {edge.source} <span className="text-slate-400">&harr;</span> {edge.target}
                      </span>
                      <div className="flex-1 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                        <div className="h-full rounded-full bg-indigo-600/80" style={{ width: `${widthPct}%` }} />
                      </div>
                      <span className="w-10 text-right font-mono text-[10px] text-slate-500 tabular-nums">
                        {edge.co_occurrences}
                      </span>
                    </div>
                  );
                })}
              </div>
              <div className="mt-3 border-t border-slate-100 pt-2.5">
                <div className="micro-label mb-1.5">Top Extracted Civic Entities</div>
                <div className="flex flex-wrap gap-1">
                  {(explorer?.top_entities ?? []).slice(0, 8).map((ent) => (
                    <span
                      key={`${ent.text}-${ent.type}`}
                      className="inline-flex items-center gap-1 rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] text-slate-700"
                    >
                      <span className="font-medium">{ent.text}</span>
                      <span className="font-mono text-[9px] text-indigo-700">{ent.count}</span>
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Representative Source Posts Table */}
          <div className="surface-panel overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
              <div>
                <h2 className="section-heading">
                  Representative Source Posts{" "}
                  {selectedClusterId ? `(Cluster #${selectedClusterId})` : ""}
                </h2>
                <p className="text-[11px] text-slate-500">
                  {recordsData?.total.toLocaleString() ?? 0} matching deduplicated records · click any row to inspect raw vs processed text
                </p>
              </div>
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                  <input
                    value={recSearch}
                    onChange={(e) => {
                      setRecSearch(e.target.value);
                      setRecPage(1);
                    }}
                    placeholder="Filter text..."
                    className="input-field w-44 pl-8"
                  />
                </div>
                <select
                  value={recSentiment}
                  onChange={(e) => {
                    setRecSentiment(e.target.value);
                    setRecPage(1);
                  }}
                  className="input-field w-32"
                >
                  <option value="all">All Sentiment</option>
                  <option value="positive">Positive</option>
                  <option value="neutral">Neutral</option>
                  <option value="mixed">Mixed</option>
                  <option value="negative">Negative</option>
                </select>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-200 bg-slate-50/80 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  <tr>
                    <th className="px-4 py-2">Record & Source Excerpt</th>
                    <th className="px-3 py-2">Topic & Confidence</th>
                    <th className="px-3 py-2">Sentiment</th>
                    <th className="px-3 py-2">Source & Provenance</th>
                    <th className="px-3 py-2 text-right">Published</th>
                    <th className="px-3 py-2 text-right">Inspect</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {loadingRecords ? (
                    <tr>
                      <td colSpan={6} className="p-6 text-center text-slate-400">
                        Loading source evidence...
                      </td>
                    </tr>
                  ) : (recordsData?.items ?? []).length === 0 ? (
                    <tr>
                      <td colSpan={6} className="p-8 text-center text-slate-500">
                        No source records match these filters.
                      </td>
                    </tr>
                  ) : (
                    (recordsData?.items ?? []).map((r) => (
                      <tr
                        key={r.id}
                        onClick={() => openRecordInspector(r.id)}
                        className="cursor-pointer hover:bg-slate-50"
                      >
                        <td className="max-w-md px-4 py-2.5">
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono text-[10px] font-medium text-indigo-700">
                              REC-{r.id}
                            </span>
                            <span className="font-mono text-[10px] uppercase text-slate-400">
                              {r.detected_language}
                            </span>
                            {r.is_verified && (
                              <span className="rounded bg-emerald-50 px-1 text-[9px] font-semibold text-emerald-700">
                                VERIFIED
                              </span>
                            )}
                          </div>
                          <p className="mt-0.5 line-clamp-2 text-xs text-slate-800">{r.original_text}</p>
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="max-w-[180px] truncate font-medium text-slate-800">
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
                          <div className="max-w-[160px] truncate text-[11px] text-slate-700">
                            {r.source_name}
                          </div>
                          <div className="mt-0.5">
                            <ProvenanceBadge isSynthetic={r.is_synthetic} label={r.provenance_label} />
                          </div>
                        </td>
                        <td className="px-3 py-2.5 text-right font-mono text-[11px] text-slate-500 tabular-nums whitespace-nowrap">
                          {new Date(r.published_at).toLocaleDateString()}
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              openRecordInspector(r.id);
                            }}
                            className="rounded border border-slate-200 p-1.5 text-slate-500 hover:bg-indigo-50 hover:text-indigo-700"
                          >
                            <Eye className="h-3.5 w-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {recordsData && recordsData.total_pages > 1 && (
              <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50/70 px-4 py-2 text-xs text-slate-600">
                <span className="font-mono text-[11px] tabular-nums">
                  Page {recordsData.page} of {recordsData.total_pages} ({recordsData.total.toLocaleString()} records)
                </span>
                <div className="flex items-center gap-1.5">
                  <button
                    disabled={recPage <= 1}
                    onClick={() => setRecPage((p) => Math.max(1, p - 1))}
                    className="btn-secondary px-2 py-1"
                  >
                    <ChevronLeft className="h-3.5 w-3.5" /> Prev
                  </button>
                  <button
                    disabled={recPage >= recordsData.total_pages}
                    onClick={() => setRecPage((p) => p + 1)}
                    className="btn-secondary px-2 py-1"
                  >
                    Next <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};
