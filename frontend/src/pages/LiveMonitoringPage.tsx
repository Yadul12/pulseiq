import React, { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Eye,
  Pause,
  Play,
  Radio,
  Wifi,
  WifiOff,
  Zap,
} from "lucide-react";
import { apiRequest, getStoredToken } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useWorkspace } from "../context/WorkspaceContext";
import type { DataSource, LiveEventRecord, MonitoringTopic } from "../types";
import { ProvenanceBadge, SentimentBadge, StatusPill } from "../components/Badges";

export const LiveMonitoringPage: React.FC = () => {
  const { canWrite } = useAuth();
  const { openRecordInspector, pushToast } = useWorkspace();

  const [streamItems, setStreamItems] = useState<LiveEventRecord[]>([]);
  const [paused, setPaused] = useState(false);
  const [transport, setTransport] = useState<"connecting" | "websocket" | "sse" | "offline">("connecting");
  const [topicFilter, setTopicFilter] = useState<string>("all");
  const [sentimentFilter, setSentimentFilter] = useState<string>("all");
  const [selectedSourceId, setSelectedSourceId] = useState<number | null>(null);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  const { data: topics = [] } = useQuery<MonitoringTopic[]>({
    queryKey: ["topics-all"],
    queryFn: () => apiRequest<MonitoringTopic[]>("/topics"),
  });

  const { data: sources = [] } = useQuery<DataSource[]>({
    queryKey: ["sources-list"],
    queryFn: () => apiRequest<DataSource[]>("/sources"),
  });

  // Bootstrap initial recent feed from PostgreSQL
  const { data: recentBootstrap } = useQuery<LiveEventRecord[]>({
    queryKey: ["live-recent"],
    queryFn: () => apiRequest<LiveEventRecord[]>("/live/recent?limit=35"),
  });

  useEffect(() => {
    if (recentBootstrap && streamItems.length === 0) {
      setStreamItems(recentBootstrap);
    }
  }, [recentBootstrap, streamItems.length]);

  // Connect real WebSocket with graceful SSE fallback
  useEffect(() => {
    const token = getStoredToken();
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${proto}//${window.location.host}/ws/live${token ? `?token=${encodeURIComponent(token)}` : ""}`;

    let ws: WebSocket | null = null;
    let sse: EventSource | null = null;
    let closedByCleanup = false;

    const pushIncoming = (rec: LiveEventRecord) => {
      if (pausedRef.current) return;
      if (rec.type !== "record.processed") return;
      setStreamItems((prev) => {
        if (prev.some((x) => x.processed_record_id === rec.processed_record_id)) return prev;
        return [rec, ...prev].slice(0, 120);
      });
    };

    const connectSSE = () => {
      if (closedByCleanup) return;
      const sseUrl = `/api/v1/live/stream${token ? `?token=${encodeURIComponent(token)}` : ""}`;
      sse = new EventSource(sseUrl);
      sse.addEventListener("ready", () => setTransport("sse"));
      sse.addEventListener("record", (ev) => {
        try {
          pushIncoming(JSON.parse((ev as MessageEvent).data));
        } catch {
          // ignore malformed frames
        }
      });
      sse.onerror = () => {
        setTransport("offline");
      };
    };

    try {
      ws = new WebSocket(wsUrl);
      ws.onopen = () => setTransport("websocket");
      ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          if (parsed.type === "record.processed") {
            pushIncoming(parsed);
          }
        } catch {
          // ignore non-json
        }
      };
      ws.onerror = () => {
        ws?.close();
      };
      ws.onclose = () => {
        if (!closedByCleanup) {
          connectSSE();
        }
      };
    } catch {
      connectSSE();
    }

    return () => {
      closedByCleanup = true;
      ws?.close();
      sse?.close();
    };
  }, []);

  const triggerLiveBatch = useMutation({
    mutationFn: () => {
      const targetSrcId = selectedSourceId || sources.find((s) => s.is_enabled)?.id;
      if (!targetSrcId) throw new Error("No enabled source found.");
      return apiRequest<{ records_inserted: number; records_duplicated: number }>(
        `/sources/${targetSrcId}/run`,
        {
          method: "POST",
          body: JSON.stringify({ batch_size: 12, use_celery: false }),
        }
      );
    },
    onSuccess: (res) => {
      pushToast(
        "success",
        "Live ingestion batch pushed",
        `${res.records_inserted} records processed and broadcast over live stream (${res.records_duplicated} duplicates).`
      );
    },
    onError: (err: Error) => pushToast("error", "Live batch failed", err.message),
  });

  const filtered = streamItems.filter((item) => {
    if (topicFilter !== "all" && item.topic !== topicFilter) return false;
    if (sentimentFilter !== "all" && item.sentiment !== sentimentFilter) return false;
    return true;
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-semibold tracking-tight text-slate-900">Live Monitoring Feed</h1>
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[10px] font-semibold uppercase ${
                transport === "websocket" || transport === "sse"
                  ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                  : transport === "connecting"
                  ? "border-amber-200 bg-amber-50 text-amber-800"
                  : "border-rose-200 bg-rose-50 text-rose-800"
              }`}
            >
              {transport === "websocket" || transport === "sse" ? (
                <Wifi className="h-3 w-3" />
              ) : (
                <WifiOff className="h-3 w-3" />
              )}
              {transport === "websocket"
                ? "LIVE WEBSOCKET"
                : transport === "sse"
                ? "LIVE SSE"
                : transport.toUpperCase()}
            </span>
          </div>
          <p className="text-xs text-slate-500">
            Real-time stream of newly ingested & NLP-classified civic discussion records over Redis Pub/Sub
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setPaused((p) => !p)}
            className={`btn-secondary ${paused ? "border-amber-300 bg-amber-50 text-amber-900" : ""}`}
          >
            {paused ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
            {paused ? "Resume Feed" : "Pause Feed"}
          </button>

          {canWrite && (
            <div className="flex items-center gap-1.5">
              <select
                value={selectedSourceId ?? ""}
                onChange={(e) => setSelectedSourceId(e.target.value ? Number(e.target.value) : null)}
                className="input-field w-48"
              >
                <option value="">Default Active Source</option>
                {sources.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
              <button
                onClick={() => triggerLiveBatch.mutate()}
                disabled={triggerLiveBatch.isPending}
                className="btn-primary"
              >
                <Zap className="h-3.5 w-3.5" />
                {triggerLiveBatch.isPending ? "Ingesting..." : "Ingest Live Batch"}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Filter Bar */}
      <div className="surface-panel flex flex-wrap items-center justify-between gap-3 px-4 py-2.5">
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <Radio className="h-3.5 w-3.5 text-indigo-600" />
            <span className="font-mono tabular-nums">{filtered.length}</span> records in live buffer
          </div>
          <select
            value={topicFilter}
            onChange={(e) => setTopicFilter(e.target.value)}
            className="input-field w-52"
          >
            <option value="all">All Topics</option>
            {topics.map((t) => (
              <option key={t.id} value={t.name}>
                {t.name}
              </option>
            ))}
          </select>
          <select
            value={sentimentFilter}
            onChange={(e) => setSentimentFilter(e.target.value)}
            className="input-field w-36"
          >
            <option value="all">All Sentiment</option>
            <option value="positive">Positive</option>
            <option value="neutral">Neutral</option>
            <option value="mixed">Mixed</option>
            <option value="negative">Negative</option>
          </select>
        </div>
        <span className="font-mono text-[10px] text-slate-400">
          Scheduled Celery ingestion emits new records every 3 min · or click "Ingest Live Batch" for instant stream
        </span>
      </div>

      {/* Live Stream Table */}
      <div className="surface-panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-200 bg-slate-50/90 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-2">Processed Time</th>
                <th className="px-3 py-2">Incoming Record</th>
                <th className="px-3 py-2">Source & Provenance</th>
                <th className="px-3 py-2">Topic</th>
                <th className="px-3 py-2">Sentiment</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2 text-right">Inspect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-slate-500">
                    Waiting for incoming records matching active filters...
                  </td>
                </tr>
              ) : (
                filtered.map((item) => (
                  <tr
                    key={`${item.processed_record_id}-${item.processed_at}`}
                    onClick={() => openRecordInspector(item.processed_record_id)}
                    className="cursor-pointer transition hover:bg-slate-50"
                  >
                    <td className="px-4 py-2.5 font-mono text-[11px] text-slate-500 tabular-nums whitespace-nowrap">
                      <div>{new Date(item.processed_at).toLocaleTimeString()}</div>
                      <div className="text-[10px] text-slate-400">REC-{item.processed_record_id}</div>
                    </td>
                    <td className="max-w-md px-3 py-2.5">
                      <p className="line-clamp-2 text-xs text-slate-800">{item.excerpt}</p>
                      <span className="font-mono text-[10px] uppercase text-slate-400">
                        lang: {item.language} {item.is_duplicate ? "· DUPLICATE" : ""}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="max-w-[160px] truncate text-[11px] font-medium text-slate-700">
                        {item.source_name}
                      </div>
                      <div className="mt-0.5">
                        <ProvenanceBadge isSynthetic={item.is_synthetic} label={item.provenance_label} />
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="max-w-[160px] truncate font-medium text-slate-800">{item.topic}</div>
                      <div className="font-mono text-[10px] text-slate-400 tabular-nums">
                        {Math.round(item.topic_confidence * 100)}% conf
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <SentimentBadge sentiment={item.sentiment} confidence={item.sentiment_confidence} />
                    </td>
                    <td className="px-3 py-2.5">
                      <StatusPill status={item.processing_status} />
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          openRecordInspector(item.processed_record_id);
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
      </div>
    </div>
  );
};
