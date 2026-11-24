import React from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowUpRight,
  Info,
  RefreshCw,
  TrendingUp,
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
import { apiRequest } from "../api/client";
import { useWorkspace } from "../context/WorkspaceContext";
import { ProvenanceBadge, SENTIMENT_COLORS, StatusPill } from "../components/Badges";

const TOPIC_SERIES_COLORS = [
  "#3730A3",
  "#2563EB",
  "#0F766E",
  "#64748B",
  "#B47B2B",
  "#881337",
];

interface OverviewResponse {
  window_days: number;
  kpis: {
    total_processed_posts: number;
    total_all_time_records: number;
    unique_non_duplicate_posts: number;
    unique_sources: number;
    total_configured_sources: number;
    emerging_topics_count: number;
    processing_backlog: number;
    verified_insights_count: number;
    avg_sentiment_score: number;
    synthetic_share_pct: number;
    ingestion_health: { status: string; healthy: number; degraded: number; error: number };
  };
  sentiment_distribution: { positive: number; neutral: number; mixed: number; negative: number };
  topic_names: string[];
  topic_activity_over_time: Array<Record<string, string | number>>;
  topic_totals: Array<{ topic: string; count: number }>;
  emerging_watchlist: Array<{
    id: number;
    monitoring_topic_id?: number;
    topic_name: string;
    cluster_label: string;
    record_count: number;
    recent_24h_count: number;
    baseline_daily_avg: number;
    trend_velocity: number;
    growth_pct: number;
    is_emerging: boolean;
    avg_sentiment_score: number;
    sentiment_breakdown: { positive: number; neutral: number; mixed: number; negative: number };
    top_keywords: string[];
  }>;
  ingestion_sources: Array<{
    id: number;
    name: string;
    provider_type: string;
    is_synthetic: boolean;
    is_enabled: boolean;
    health_status: string;
    total_records_ingested: number;
    error_count_24h: number;
    last_ingested_at?: string | null;
  }>;
  language_breakdown: Array<{ language: string; count: number }>;
  analytical_caveat: string;
}

export const OverviewPage: React.FC = () => {
  const { days, sourceId } = useWorkspace();
  const navigate = useNavigate();

  const params = new URLSearchParams({ days: String(days) });
  if (sourceId) params.set("source_id", String(sourceId));

  const { data, isLoading, isError, refetch, isFetching } = useQuery<OverviewResponse>({
    queryKey: ["overview", days, sourceId],
    queryFn: () => apiRequest<OverviewResponse>(`/overview?${params.toString()}`),
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-20 animate-pulse rounded-lg bg-white border border-slate-200" />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="h-80 animate-pulse rounded-lg bg-white border border-slate-200 lg:col-span-2" />
          <div className="h-80 animate-pulse rounded-lg bg-white border border-slate-200" />
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="surface-panel p-6 text-center">
        <AlertTriangle className="mx-auto h-6 w-6 text-rose-500" />
        <p className="mt-2 text-xs font-medium text-slate-800">Unable to load overview telemetry.</p>
        <button onClick={() => refetch()} className="mt-3 btn-secondary">
          Retry Connection
        </button>
      </div>
    );
  }

  const totalSent =
    data.sentiment_distribution.positive +
    data.sentiment_distribution.neutral +
    data.sentiment_distribution.mixed +
    data.sentiment_distribution.negative;

  const sentPct = (n: number) => (totalSent ? ((n / totalSent) * 100).toFixed(1) : "0.0");

  return (
    <div className="space-y-4">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-base font-semibold tracking-tight text-slate-900">
            Intelligence Overview
          </h1>
          <p className="text-xs text-slate-500">
            Trailing {data.window_days}-day public discussion telemetry ·{" "}
            <span className="font-mono">{data.kpis.total_all_time_records.toLocaleString()}</span> total indexed corpus records
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded border border-slate-200 bg-white px-2 py-1 font-mono text-[10px] text-slate-600">
            Synthetic Share: {data.kpis.synthetic_share_pct}% (Explicitly Labelled)
          </span>
          <button onClick={() => refetch()} className="btn-secondary">
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Compact High-Density Enterprise Telemetry Strip (NO oversized stat cards) */}
      <div className="surface-panel grid grid-cols-2 divide-y divide-slate-200/80 sm:grid-cols-3 lg:grid-cols-6 lg:divide-x lg:divide-y-0">
        <div className="px-4 py-3">
          <div className="micro-label">Processed Posts ({days}d)</div>
          <div className="mt-1 text-xl font-semibold tracking-tight text-slate-900 tabular-nums">
            {data.kpis.total_processed_posts.toLocaleString()}
          </div>
          <div className="mt-0.5 text-[11px] text-slate-500 tabular-nums">
            {data.kpis.unique_non_duplicate_posts.toLocaleString()} deduplicated
          </div>
        </div>

        <div className="px-4 py-3">
          <div className="micro-label">Unique Sources</div>
          <div className="mt-1 text-xl font-semibold tracking-tight text-slate-900 tabular-nums">
            {data.kpis.unique_sources}
            <span className="text-xs font-normal text-slate-400"> / {data.kpis.total_configured_sources}</span>
          </div>
          <div className="mt-0.5 text-[11px] text-slate-500">CSV, RSS, API & Stream</div>
        </div>

        <div className="px-4 py-3">
          <div className="micro-label">Emerging Clusters</div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-xl font-semibold tracking-tight text-indigo-700 tabular-nums">
              {data.kpis.emerging_topics_count}
            </span>
            {data.kpis.emerging_topics_count > 0 && (
              <span className="rounded bg-amber-50 border border-amber-200 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800">
                Z &ge; 1.75
              </span>
            )}
          </div>
          <div className="mt-0.5 text-[11px] text-slate-500">72h vs 27d rolling baseline</div>
        </div>

        <div className="px-4 py-3">
          <div className="micro-label">Aggregate Tone</div>
          <div className="mt-1 text-xl font-semibold tracking-tight text-slate-900 tabular-nums">
            {data.kpis.avg_sentiment_score >= 0 ? "+" : ""}
            {data.kpis.avg_sentiment_score.toFixed(2)}
          </div>
          <div className="mt-0.5 text-[11px] text-slate-500 tabular-nums">
            {sentPct(data.sentiment_distribution.negative)}% neg · {sentPct(data.sentiment_distribution.positive)}% pos
          </div>
        </div>

        <div className="px-4 py-3">
          <div className="micro-label">Review Backlog</div>
          <div className="mt-1 text-xl font-semibold tracking-tight text-slate-900 tabular-nums">
            {data.kpis.processing_backlog.toLocaleString()}
          </div>
          <button
            onClick={() => navigate("/workspace?tab=review")}
            className="mt-0.5 text-[11px] font-medium text-indigo-700 hover:underline"
          >
            Low-conf queue &rarr;
          </button>
        </div>

        <div className="px-4 py-3">
          <div className="micro-label">Ingestion Health</div>
          <div className="mt-1.5 flex items-center gap-2">
            <StatusPill status={data.kpis.ingestion_health.status} />
            <span className="font-mono text-xs text-slate-600 tabular-nums">
              {data.kpis.ingestion_health.healthy}/{data.kpis.total_configured_sources} OK
            </span>
          </div>
          <div className="mt-1 text-[11px] text-slate-500">
            {data.kpis.verified_insights_count} verified records
          </div>
        </div>
      </div>

      {/* Main Analytics Row: Topic Activity Over Time + Sentiment & Language Breakdown */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* Topic Activity Over Time */}
        <div className="surface-panel p-4 lg:col-span-8">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="section-heading">Topic Activity Over Time</h2>
              <p className="text-[11px] text-slate-500">
                Daily deduplicated discussion volume across monitored civic domains
              </p>
            </div>
            <button
              onClick={() => navigate("/explorer")}
              className="inline-flex items-center gap-1 text-[11px] font-medium text-indigo-700 hover:underline"
            >
              Open Topic Explorer <ArrowUpRight className="h-3 w-3" />
            </button>
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.topic_activity_over_time} margin={{ top: 6, right: 10, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: "#64748B" }}
                  tickFormatter={(v: string) => v.slice(5)}
                  axisLine={{ stroke: "#CBD5E1" }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "#64748B" }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    fontSize: "11px",
                    borderRadius: "6px",
                    borderColor: "#CBD5E1",
                    boxShadow: "0 4px 12px rgba(15,23,42,0.08)",
                  }}
                />
                {data.topic_names.map((tname, idx) => (
                  <Area
                    key={tname}
                    type="monotone"
                    dataKey={tname}
                    stackId="1"
                    stroke={TOPIC_SERIES_COLORS[idx % TOPIC_SERIES_COLORS.length]}
                    fill={TOPIC_SERIES_COLORS[idx % TOPIC_SERIES_COLORS.length]}
                    fillOpacity={0.18}
                    strokeWidth={1.6}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 border-t border-slate-100 pt-2.5">
            {data.topic_names.map((tname, idx) => (
              <div key={tname} className="flex items-center gap-1.5 text-[11px] text-slate-600">
                <span
                  className="h-2 w-2 rounded-sm"
                  style={{ backgroundColor: TOPIC_SERIES_COLORS[idx % TOPIC_SERIES_COLORS.length] }}
                />
                <span>{tname}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Aggregate Sentiment Distribution & Language Coverage */}
        <div className="surface-panel flex flex-col justify-between p-4 lg:col-span-4">
          <div>
            <h2 className="section-heading">Aggregate Sentiment Distribution</h2>
            <p className="text-[11px] text-slate-500">
              Classifier estimates incorporating analyst overrides
            </p>

            {/* Horizontal Stacked Bar */}
            <div className="mt-3.5 flex h-3 w-full overflow-hidden rounded-full bg-slate-100">
              {(["positive", "neutral", "mixed", "negative"] as const).map((k) => {
                const val = data.sentiment_distribution[k];
                const w = totalSent ? (val / totalSent) * 100 : 0;
                return (
                  <div
                    key={k}
                    style={{ width: `${w}%`, backgroundColor: SENTIMENT_COLORS[k] }}
                    title={`${k}: ${val.toLocaleString()} (${w.toFixed(1)}%)`}
                  />
                );
              })}
            </div>

            <div className="mt-3.5 space-y-2">
              {(["positive", "neutral", "mixed", "negative"] as const).map((k) => {
                const cnt = data.sentiment_distribution[k];
                return (
                  <div key={k} className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-2 capitalize text-slate-700">
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ backgroundColor: SENTIMENT_COLORS[k] }}
                      />
                      {k}
                    </span>
                    <span className="font-mono text-[11px] text-slate-600 tabular-nums">
                      {cnt.toLocaleString()} <span className="text-slate-400">({sentPct(cnt)}%)</span>
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Language Mix */}
            <div className="mt-4 border-t border-slate-100 pt-3">
              <div className="micro-label mb-1.5">Detected Languages</div>
              <div className="flex flex-wrap gap-1.5">
                {data.language_breakdown.map((l) => (
                  <span
                    key={l.language}
                    className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 font-mono text-[10px] uppercase text-slate-700 tabular-nums"
                  >
                    {l.language}: {l.count.toLocaleString()}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-4 flex items-start gap-2 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-2 text-[10.5px] leading-snug text-slate-600">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
            <span>{data.analytical_caveat}</span>
          </div>
        </div>
      </div>

      {/* Bottom Row: Emerging Topic Clusters Watchlist + Ingestion Source Health */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* Emerging Watchlist */}
        <div className="surface-panel overflow-hidden lg:col-span-7">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-indigo-700" />
              <div>
                <h2 className="section-heading">Emerging Topic Clusters & Velocity</h2>
                <p className="text-[11px] text-slate-500">Ranked by 72-hour burst Z-score vs rolling 27-day baseline</p>
              </div>
            </div>
            <button onClick={() => navigate("/explorer")} className="btn-secondary text-[11px]">
              Explore All
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200 bg-slate-50/80 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-4 py-2">Cluster & Domain</th>
                  <th className="px-3 py-2 text-right">24h / Base</th>
                  <th className="px-3 py-2 text-right">Velocity</th>
                  <th className="px-3 py-2 text-right">Tone</th>
                  <th className="px-3 py-2 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.emerging_watchlist.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => navigate(`/explorer?topicId=${c.monitoring_topic_id ?? ""}&clusterId=${c.id}`)}
                    className="cursor-pointer transition hover:bg-slate-50"
                  >
                    <td className="px-4 py-2.5">
                      <div className="font-medium text-slate-900">{c.cluster_label}</div>
                      <div className="text-[11px] text-slate-500">{c.topic_name}</div>
                    </td>
                    <td className="px-3 py-2.5 text-right font-mono text-[11px] text-slate-700 tabular-nums">
                      {c.recent_24h_count} <span className="text-slate-400">/ {c.baseline_daily_avg.toFixed(1)}</span>
                    </td>
                    <td className="px-3 py-2.5 text-right font-mono text-[11px] tabular-nums">
                      <span className={c.growth_pct > 25 ? "font-semibold text-indigo-700" : "text-slate-600"}>
                        {c.growth_pct >= 0 ? "+" : ""}
                        {c.growth_pct.toFixed(0)}%
                      </span>
                      <div className="text-[10px] text-slate-400">Z={c.trend_velocity.toFixed(2)}</div>
                    </td>
                    <td className="px-3 py-2.5 text-right font-mono text-[11px] tabular-nums">
                      <span
                        className={
                          c.avg_sentiment_score < -0.15
                            ? "text-[#99353C]"
                            : c.avg_sentiment_score > 0.15
                            ? "text-[#23634D]"
                            : "text-slate-600"
                        }
                      >
                        {c.avg_sentiment_score >= 0 ? "+" : ""}
                        {c.avg_sentiment_score.toFixed(2)}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      {c.is_emerging ? (
                        <span className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800">
                          EMERGING
                        </span>
                      ) : (
                        <span className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-500">
                          STEADY
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Ingestion & Source Health */}
        <div className="surface-panel overflow-hidden lg:col-span-5">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <div>
              <h2 className="section-heading">Ingestion Pipeline Health</h2>
              <p className="text-[11px] text-slate-500">Modular adapters, sync status & provenance</p>
            </div>
            <button onClick={() => navigate("/sources")} className="btn-secondary text-[11px]">
              Manage Sources
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200 bg-slate-50/80 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-4 py-2">Source Adapter</th>
                  <th className="px-2 py-2 text-right">Records</th>
                  <th className="px-3 py-2 text-right">Health</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.ingestion_sources.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-2">
                      <div className="font-medium text-slate-800 line-clamp-1">{s.name}</div>
                      <div className="mt-0.5 flex items-center gap-1.5">
                        <span className="font-mono text-[10px] uppercase text-slate-500">{s.provider_type}</span>
                        <ProvenanceBadge isSynthetic={s.is_synthetic} />
                      </div>
                    </td>
                    <td className="px-2 py-2 text-right font-mono text-[11px] text-slate-700 tabular-nums">
                      {s.total_records_ingested.toLocaleString()}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <StatusPill status={s.health_status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
