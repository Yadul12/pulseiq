import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarRange, Eye, MapPin, Plus, TrendingUp, X } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiRequest } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useWorkspace } from "../context/WorkspaceContext";
import type { CivicEvent, MonitoringTopic, SentimentBreakdown } from "../types";
import { ProvenanceBadge, SENTIMENT_COLORS, SentimentBadge } from "../components/Badges";

interface EventAnalysis {
  event: CivicEvent;
  comparison: {
    before: { count: number; daily_rate: number; avg_sentiment: number; sentiment_breakdown: SentimentBreakdown };
    during: { count: number; daily_rate: number; avg_sentiment: number; sentiment_breakdown: SentimentBreakdown };
    after: { count: number; daily_rate: number; avg_sentiment: number; sentiment_breakdown: SentimentBreakdown };
    volume_change_pct: number;
    sentiment_delta: number;
  };
  topic_changes: Array<{
    topic: string;
    before_daily_rate: number;
    during_daily_rate: number;
    after_daily_rate: number;
    change_pct: number;
  }>;
  emerging_themes: Array<{ term: string; during_count: number; before_count: number; lift_ratio: number }>;
  timeline: Array<{
    date: string;
    phase: "before" | "during" | "after";
    volume: number;
    avg_sentiment: number;
  }>;
  representative_evidence: Array<{
    processed_record_id: number;
    published_at: string;
    source_name: string;
    is_synthetic: boolean;
    provenance_label: string;
    title?: string;
    original_text: string;
    topic: string;
    sentiment: string;
    sentiment_confidence: number;
    language: string;
  }>;
  analytical_disclaimer: string;
}

export const EventIntelligencePage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const { canWrite } = useAuth();
  const { openRecordInspector, pushToast } = useWorkspace();
  const queryClient = useQueryClient();

  const [selectedId, setSelectedId] = useState<number | null>(
    searchParams.get("eventId") ? Number(searchParams.get("eventId")) : null
  );
  const [modalOpen, setModalOpen] = useState(false);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [eventType, setEventType] = useState("Infrastructure Incident");
  const [location, setLocation] = useState("Metro Area");
  const [startDate, setStartDate] = useState(
    new Date(Date.now() - 4 * 86400000).toISOString().slice(0, 10)
  );
  const [endDate, setEndDate] = useState(new Date().toISOString().slice(0, 10));
  const [baselineDays, setBaselineDays] = useState(7);
  const [keywordsText, setKeywordsText] = useState("");
  const [topicIds, setTopicIds] = useState<number[]>([]);

  const { data: events = [], isLoading: loadingList } = useQuery<CivicEvent[]>({
    queryKey: ["events-list"],
    queryFn: () => apiRequest<CivicEvent[]>("/events"),
  });

  const { data: topics = [] } = useQuery<MonitoringTopic[]>({
    queryKey: ["topics-all"],
    queryFn: () => apiRequest<MonitoringTopic[]>("/topics"),
  });

  useEffect(() => {
    if (!selectedId && events.length > 0) {
      setSelectedId(events[0].id);
    }
  }, [events, selectedId]);

  const { data: analysis, isLoading: loadingAnalysis } = useQuery<EventAnalysis>({
    queryKey: ["event-analysis", selectedId],
    queryFn: () => apiRequest<EventAnalysis>(`/events/${selectedId}/analysis`),
    enabled: selectedId !== null,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      apiRequest<CivicEvent>("/events", {
        method: "POST",
        body: JSON.stringify({
          title,
          description,
          event_type: eventType,
          location,
          start_time: new Date(`${startDate}T00:00:00Z`).toISOString(),
          end_time: new Date(`${endDate}T23:59:59Z`).toISOString(),
          baseline_days: baselineDays,
          monitoring_topic_ids: topicIds,
          keywords: keywordsText
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        }),
      }),
    onSuccess: (created) => {
      pushToast("success", "Civic event created", `Before-and-after window analysis computed for "${created.title}".`);
      queryClient.invalidateQueries({ queryKey: ["events-list"] });
      setSelectedId(created.id);
      setModalOpen(false);
      setTitle("");
      setDescription("");
      setKeywordsText("");
    },
    onError: (err: Error) => pushToast("error", "Could not create event", err.message),
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-base font-semibold tracking-tight text-slate-900">Event Intelligence</h1>
          <p className="text-xs text-slate-500">
            Define civic event windows to evaluate before-and-after volume shifts, tone changes, emerging themes, and primary evidence
          </p>
        </div>
        {canWrite && (
          <button onClick={() => setModalOpen(true)} className="btn-primary">
            <Plus className="h-3.5 w-3.5" /> Create Event Window
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* Events Selector Column */}
        <div className="surface-panel overflow-hidden lg:col-span-3">
          <div className="border-b border-slate-200 px-3.5 py-2.5">
            <span className="micro-label">Tracked Civic Events ({events.length})</span>
          </div>
          <div className="divide-y divide-slate-100">
            {loadingList ? (
              <div className="p-4 text-xs text-slate-400">Loading events...</div>
            ) : (
              events.map((ev) => (
                <button
                  key={ev.id}
                  onClick={() => setSelectedId(ev.id)}
                  className={`block w-full px-3.5 py-3 text-left transition ${
                    selectedId === ev.id
                      ? "bg-indigo-50/70 border-l-2 border-indigo-700"
                      : "hover:bg-slate-50"
                  }`}
                >
                  <div className="text-xs font-semibold text-slate-900">{ev.title}</div>
                  <div className="mt-1 flex items-center gap-1 text-[11px] text-slate-500">
                    <MapPin className="h-3 w-3 shrink-0" />
                    <span className="truncate">{ev.location}</span>
                  </div>
                  <div className="mt-1 font-mono text-[10px] text-slate-400 tabular-nums">
                    {ev.start_time.slice(0, 10)} &rarr; {ev.end_time.slice(0, 10)}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Event Analysis Workspace */}
        <div className="space-y-4 lg:col-span-9">
          {loadingAnalysis || !analysis ? (
            <div className="surface-panel h-96 animate-pulse" />
          ) : (
            <>
              {/* Event Banner + Before / During / After Telemetry */}
              <div className="surface-panel overflow-hidden">
                <div className="border-b border-slate-200 px-4 py-3.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-sm font-semibold text-slate-900">{analysis.event.title}</h2>
                        <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-600">
                          {analysis.event.event_type}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-600">{analysis.event.description}</p>
                    </div>
                    <div className="flex items-center gap-1.5 font-mono text-[11px] text-slate-600">
                      <CalendarRange className="h-3.5 w-3.5 text-indigo-600" />
                      {analysis.event.start_time.slice(0, 10)} to {analysis.event.end_time.slice(0, 10)} (
                      &plusmn;{analysis.event.baseline_days}d baseline)
                    </div>
                  </div>
                </div>

                {/* Before / During / After Quantitative Strip */}
                <div className="grid grid-cols-2 divide-y divide-slate-200 sm:grid-cols-5 sm:divide-x sm:divide-y-0">
                  <div className="px-4 py-3">
                    <div className="micro-label">Before Rate</div>
                    <div className="mt-1 font-mono text-lg font-semibold text-slate-800 tabular-nums">
                      {analysis.comparison.before.daily_rate}/d
                    </div>
                    <div className="text-[10px] text-slate-500">
                      {analysis.comparison.before.count.toLocaleString()} total · tone{" "}
                      {analysis.comparison.before.avg_sentiment.toFixed(2)}
                    </div>
                  </div>
                  <div className="bg-indigo-50/35 px-4 py-3">
                    <div className="micro-label text-indigo-800">During Event</div>
                    <div className="mt-1 font-mono text-lg font-semibold text-indigo-900 tabular-nums">
                      {analysis.comparison.during.daily_rate}/d
                    </div>
                    <div className="text-[10px] text-indigo-700">
                      {analysis.comparison.during.count.toLocaleString()} total · tone{" "}
                      {analysis.comparison.during.avg_sentiment.toFixed(2)}
                    </div>
                  </div>
                  <div className="px-4 py-3">
                    <div className="micro-label">After Rate</div>
                    <div className="mt-1 font-mono text-lg font-semibold text-slate-800 tabular-nums">
                      {analysis.comparison.after.daily_rate}/d
                    </div>
                    <div className="text-[10px] text-slate-500">
                      {analysis.comparison.after.count.toLocaleString()} total · tone{" "}
                      {analysis.comparison.after.avg_sentiment.toFixed(2)}
                    </div>
                  </div>
                  <div className="px-4 py-3">
                    <div className="micro-label">Volume Lift</div>
                    <div
                      className={`mt-1 font-mono text-lg font-semibold tabular-nums ${
                        analysis.comparison.volume_change_pct >= 0 ? "text-indigo-700" : "text-slate-700"
                      }`}
                    >
                      {analysis.comparison.volume_change_pct >= 0 ? "+" : ""}
                      {analysis.comparison.volume_change_pct}%
                    </div>
                    <div className="text-[10px] text-slate-500">Event vs Pre-Baseline</div>
                  </div>
                  <div className="px-4 py-3">
                    <div className="micro-label">Sentiment Shift</div>
                    <div
                      className={`mt-1 font-mono text-lg font-semibold tabular-nums ${
                        analysis.comparison.sentiment_delta < -0.05
                          ? "text-[#99353C]"
                          : analysis.comparison.sentiment_delta > 0.05
                          ? "text-[#23634D]"
                          : "text-slate-700"
                      }`}
                    >
                      {analysis.comparison.sentiment_delta >= 0 ? "+" : ""}
                      {analysis.comparison.sentiment_delta.toFixed(2)}
                    </div>
                    <div className="text-[10px] text-slate-500">Polarity Delta</div>
                  </div>
                </div>
              </div>

              {/* Timeline Chart + Emerging Event Themes */}
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
                <div className="surface-panel p-4 lg:col-span-7">
                  <div className="mb-2 flex items-center justify-between">
                    <div>
                      <h3 className="section-heading">Before / During / After Daily Volume</h3>
                      <p className="text-[11px] text-slate-500">
                        Indigo bars denote the active event window; slate bars indicate baseline & recovery
                      </p>
                    </div>
                  </div>
                  <div className="h-56 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={analysis.timeline} margin={{ top: 6, right: 8, left: -16, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
                        <XAxis
                          dataKey="date"
                          tick={{ fontSize: 10, fill: "#64748B" }}
                          tickFormatter={(v: string) => v.slice(5)}
                        />
                        <YAxis tick={{ fontSize: 10, fill: "#64748B" }} />
                        <Tooltip contentStyle={{ fontSize: "11px", borderRadius: "6px" }} />
                        <Bar dataKey="volume" radius={[3, 3, 0, 0]}>
                          {analysis.timeline.map((entry, idx) => (
                            <Cell
                              key={idx}
                              fill={
                                entry.phase === "during"
                                  ? "#3730A3"
                                  : entry.phase === "before"
                                  ? "#94A3B8"
                                  : "#64748B"
                              }
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Emerging Themes & Sentiment Comparison */}
                <div className="surface-panel p-4 lg:col-span-5 space-y-4">
                  <div>
                    <h3 className="section-heading flex items-center gap-1.5">
                      <TrendingUp className="h-3.5 w-3.5 text-indigo-700" />
                      Emerging Event Themes (Lift vs Baseline)
                    </h3>
                    <div className="mt-2.5 space-y-1.5">
                      {analysis.emerging_themes.length === 0 ? (
                        <p className="text-xs text-slate-400">No high-lift keywords detected in window.</p>
                      ) : (
                        analysis.emerging_themes.slice(0, 7).map((th) => (
                          <div key={th.term} className="flex items-center justify-between text-xs">
                            <span className="font-mono text-slate-800">{th.term}</span>
                            <div className="flex items-center gap-2 font-mono text-[11px] tabular-nums">
                              <span className="text-slate-400">
                                {th.before_count} &rarr; {th.during_count}
                              </span>
                              <span className="rounded bg-indigo-50 px-1.5 py-0.5 font-semibold text-indigo-800">
                                {th.lift_ratio.toFixed(1)}x
                              </span>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Sentiment Before vs During */}
                  <div className="border-t border-slate-100 pt-3">
                    <div className="micro-label mb-2">Sentiment Mix Shift (Before vs During)</div>
                    {(["before", "during"] as const).map((phase) => {
                      const b = analysis.comparison[phase].sentiment_breakdown;
                      const tot = Math.max(analysis.comparison[phase].count, 1);
                      return (
                        <div key={phase} className="mb-2">
                          <div className="mb-1 flex justify-between text-[10px] uppercase text-slate-500">
                            <span>{phase}</span>
                            <span className="font-mono tabular-nums">
                              Neg {((b.negative / tot) * 100).toFixed(0)}% · Pos{" "}
                              {((b.positive / tot) * 100).toFixed(0)}%
                            </span>
                          </div>
                          <div className="flex h-2 w-full overflow-hidden rounded-full bg-slate-100">
                            {(["positive", "neutral", "mixed", "negative"] as const).map((s) => (
                              <div
                                key={s}
                                style={{
                                  width: `${((b[s] || 0) / tot) * 100}%`,
                                  backgroundColor: SENTIMENT_COLORS[s],
                                }}
                              />
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Representative Event Evidence */}
              <div className="surface-panel overflow-hidden">
                <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
                  <div>
                    <h3 className="section-heading">Representative Event Evidence</h3>
                    <p className="text-[11px] text-slate-500">{analysis.analytical_disclaimer}</p>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-slate-200 bg-slate-50/80 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                      <tr>
                        <th className="px-4 py-2">Evidence Quote</th>
                        <th className="px-3 py-2">Source & Provenance</th>
                        <th className="px-3 py-2">Sentiment</th>
                        <th className="px-3 py-2 text-right">Date</th>
                        <th className="px-3 py-2 text-right">Inspect</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {analysis.representative_evidence.map((ev) => (
                        <tr
                          key={ev.processed_record_id}
                          onClick={() => openRecordInspector(ev.processed_record_id)}
                          className="cursor-pointer hover:bg-slate-50"
                        >
                          <td className="max-w-md px-4 py-2.5">
                            <span className="font-mono text-[10px] font-semibold text-indigo-700">
                              REC-{ev.processed_record_id}
                            </span>
                            <p className="mt-0.5 line-clamp-2 text-slate-800">{ev.original_text}</p>
                          </td>
                          <td className="px-3 py-2.5">
                            <div className="text-[11px] text-slate-700">{ev.source_name}</div>
                            <ProvenanceBadge isSynthetic={ev.is_synthetic} label={ev.provenance_label} />
                          </td>
                          <td className="px-3 py-2.5">
                            <SentimentBadge sentiment={ev.sentiment} confidence={ev.sentiment_confidence} />
                          </td>
                          <td className="px-3 py-2.5 text-right font-mono text-[11px] text-slate-500">
                            {ev.published_at.slice(0, 10)}
                          </td>
                          <td className="px-3 py-2.5 text-right">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                openRecordInspector(ev.processed_record_id);
                              }}
                              className="rounded border border-slate-200 p-1.5 text-slate-500 hover:text-indigo-700"
                            >
                              <Eye className="h-3.5 w-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Create Event Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="w-full max-w-lg rounded-lg border border-slate-200 bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3.5">
              <h2 className="text-sm font-semibold text-slate-900">Create Event Intelligence Window</h2>
              <button onClick={() => setModalOpen(false)} className="text-slate-400 hover:text-slate-700">
                <X className="h-4 w-4" />
              </button>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                createMutation.mutate();
              }}
              className="space-y-3.5 p-5"
            >
              <div>
                <label className="micro-label block mb-1">Event Title</label>
                <input
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Transit Fare & Late-Night Corridor Hearing"
                  className="input-field"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="micro-label block mb-1">Event Type</label>
                  <input value={eventType} onChange={(e) => setEventType(e.target.value)} className="input-field" />
                </div>
                <div>
                  <label className="micro-label block mb-1">Location</label>
                  <input value={location} onChange={(e) => setLocation(e.target.value)} className="input-field" />
                </div>
              </div>
              <div>
                <label className="micro-label block mb-1">Description</label>
                <textarea
                  rows={2}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="input-field"
                />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="micro-label block mb-1">Start Date</label>
                  <input type="date" required value={startDate} onChange={(e) => setStartDate(e.target.value)} className="input-field" />
                </div>
                <div>
                  <label className="micro-label block mb-1">End Date</label>
                  <input type="date" required value={endDate} onChange={(e) => setEndDate(e.target.value)} className="input-field" />
                </div>
                <div>
                  <label className="micro-label block mb-1">Baseline (Days)</label>
                  <input
                    type="number"
                    min={1}
                    max={30}
                    value={baselineDays}
                    onChange={(e) => setBaselineDays(Number(e.target.value))}
                    className="input-field"
                  />
                </div>
              </div>
              <div>
                <label className="micro-label block mb-1">Event Keywords (comma-separated)</label>
                <input
                  value={keywordsText}
                  onChange={(e) => setKeywordsText(e.target.value)}
                  placeholder="fare, late-night bus, corridor, riders"
                  className="input-field"
                />
              </div>
              <div>
                <label className="micro-label block mb-1">Scope to Monitoring Topics (Optional)</label>
                <div className="flex flex-wrap gap-1.5">
                  {topics.map((t) => {
                    const active = topicIds.includes(t.id);
                    return (
                      <button
                        type="button"
                        key={t.id}
                        onClick={() =>
                          setTopicIds((prev) =>
                            prev.includes(t.id) ? prev.filter((x) => x !== t.id) : [...prev, t.id]
                          )
                        }
                        className={`rounded border px-2 py-1 text-[11px] ${
                          active
                            ? "border-indigo-600 bg-indigo-50 text-indigo-800"
                            : "border-slate-200 text-slate-600"
                        }`}
                      >
                        {t.name}
                      </button>
                    );
                  })}
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setModalOpen(false)} className="btn-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={createMutation.isPending} className="btn-primary">
                  {createMutation.isPending ? "Analyzing..." : "Create & Analyze Window"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
