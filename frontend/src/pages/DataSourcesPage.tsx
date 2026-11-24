import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Database, Play, Plus, RefreshCw, X } from "lucide-react";
import { apiRequest } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useWorkspace } from "../context/WorkspaceContext";
import type { DataSource, IngestionJob } from "../types";
import { ProvenanceBadge, StatusPill } from "../components/Badges";

export const DataSourcesPage: React.FC = () => {
  const { canWrite, isSeniorOrAdmin } = useAuth();
  const { pushToast } = useWorkspace();
  const queryClient = useQueryClient();

  const [selectedJob, setSelectedJob] = useState<IngestionJob | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const [name, setName] = useState("");
  const [providerType, setProviderType] = useState<"csv" | "rss" | "public_api" | "synthetic_stream">("synthetic_stream");
  const [description, setDescription] = useState("");
  const [endpointOrPath, setEndpointOrPath] = useState("");
  const [rateLimit, setRateLimit] = useState(60);

  const { data: sources = [], isLoading: loadingSources } = useQuery<DataSource[]>({
    queryKey: ["sources-list"],
    queryFn: () => apiRequest<DataSource[]>("/sources"),
  });

  const { data: jobsData, isLoading: loadingJobs } = useQuery<{
    total: number;
    items: IngestionJob[];
  }>({
    queryKey: ["ingestion-jobs"],
    queryFn: () => apiRequest("/ingestion-jobs?page=1&page_size=25"),
  });

  const runMutation = useMutation({
    mutationFn: (sourceId: number) =>
      apiRequest<{ job_id: number; records_inserted: number; records_duplicated: number; status: string }>(
        `/sources/${sourceId}/run`,
        {
          method: "POST",
          body: JSON.stringify({ batch_size: 18, use_celery: false }),
        }
      ),
    onSuccess: (res) => {
      pushToast(
        "success",
        `Ingestion Job #${res.job_id} ${res.status}`,
        `+${res.records_inserted} records inserted (${res.records_duplicated} duplicates flagged).`
      );
      queryClient.invalidateQueries({ queryKey: ["sources-list"] });
      queryClient.invalidateQueries({ queryKey: ["ingestion-jobs"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
    },
    onError: (err: Error) => pushToast("error", "Ingestion job failed", err.message),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_enabled }: { id: number; is_enabled: boolean }) =>
      apiRequest(`/sources/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_enabled }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources-list"] });
    },
  });

  const createMutation = useMutation({
    mutationFn: () => {
      const cfg: Record<string, unknown> = {};
      if (providerType === "csv") cfg.file_path = endpointOrPath || "/app/data/prepared_civic_consultations_sample.csv";
      if (providerType === "rss") {
        cfg.feed_url = endpointOrPath || "https://feeds.example.gov/civic.xml";
        cfg.fallback_to_synthetic = true;
      }
      if (providerType === "public_api") {
        cfg.endpoint = endpointOrPath || "https://api.example.gov/public/items.json";
        cfg.fallback_to_synthetic = true;
      }
      if (providerType === "synthetic_stream") cfg.batch_size = 20;

      return apiRequest("/sources", {
        method: "POST",
        body: JSON.stringify({
          name,
          provider_type: providerType,
          description,
          config: cfg,
          is_synthetic: true,
          is_enabled: true,
          rate_limit_per_min: rateLimit,
        }),
      });
    },
    onSuccess: () => {
      pushToast("success", "Data source configured", `"${name}" registered.`);
      queryClient.invalidateQueries({ queryKey: ["sources-list"] });
      setCreateOpen(false);
      setName("");
      setDescription("");
      setEndpointOrPath("");
    },
    onError: (err: Error) => pushToast("error", "Could not create source", err.message),
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-base font-semibold tracking-tight text-slate-900">
            Data Sources & Ingestion Pipeline
          </h1>
          <p className="text-xs text-slate-500">
            Modular provider adapters for Prepared CSV, Public RSS, Permitted APIs, and clearly labelled Synthetic Streams
          </p>
        </div>
        {isSeniorOrAdmin && (
          <button onClick={() => setCreateOpen(true)} className="btn-primary">
            <Plus className="h-3.5 w-3.5" /> Register Adapter Source
          </button>
        )}
      </div>

      {/* Sources Table */}
      <div className="surface-panel overflow-hidden">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-indigo-700" />
            <h2 className="section-heading">Configured Provider Adapters ({sources.length})</h2>
          </div>
          <span className="font-mono text-[10px] text-slate-500">
            Rate-limit backoff · Cursor incremental sync · Automatic synthetic fallback disclosure
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-200 bg-slate-50/90 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-2">Source & Provenance</th>
                <th className="px-3 py-2">Adapter</th>
                <th className="px-3 py-2">Schedule / Rate</th>
                <th className="px-3 py-2 text-right">Ingested</th>
                <th className="px-3 py-2">Cursor</th>
                <th className="px-3 py-2">Health</th>
                <th className="px-4 py-2 text-right">Controls</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loadingSources ? (
                <tr>
                  <td colSpan={7} className="p-6 text-center text-slate-400">
                    Loading sources...
                  </td>
                </tr>
              ) : (
                sources.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-50/70">
                    <td className="max-w-sm px-4 py-2.5">
                      <div className="font-semibold text-slate-900">{s.name}</div>
                      <p className="mt-0.5 line-clamp-1 text-[11px] text-slate-500">{s.description}</p>
                      <div className="mt-1">
                        <ProvenanceBadge isSynthetic={s.is_synthetic} />
                      </div>
                    </td>
                    <td className="px-3 py-2.5 font-mono text-[11px] uppercase text-indigo-700">
                      {s.provider_type}
                    </td>
                    <td className="px-3 py-2.5 font-mono text-[11px] text-slate-600 tabular-nums">
                      <div>Every {s.schedule_interval_minutes}m</div>
                      <div className="text-[10px] text-slate-400">{s.rate_limit_per_min} req/min</div>
                    </td>
                    <td className="px-3 py-2.5 text-right font-mono text-xs text-slate-800 tabular-nums">
                      {s.total_records_ingested.toLocaleString()}
                    </td>
                    <td className="max-w-[140px] truncate px-3 py-2.5 font-mono text-[10px] text-slate-500">
                      {s.last_cursor || "—"}
                    </td>
                    <td className="px-3 py-2.5">
                      <StatusPill status={s.health_status} />
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {canWrite && (
                          <>
                            <button
                              onClick={() => toggleMutation.mutate({ id: s.id, is_enabled: !s.is_enabled })}
                              className={`rounded border px-2 py-1 text-[10px] font-medium ${
                                s.is_enabled
                                  ? "border-slate-200 bg-white text-slate-700"
                                  : "border-amber-200 bg-amber-50 text-amber-800"
                              }`}
                            >
                              {s.is_enabled ? "Enabled" : "Disabled"}
                            </button>
                            <button
                              onClick={() => runMutation.mutate(s.id)}
                              disabled={runMutation.isPending}
                              className="btn-secondary px-2 py-1 text-[11px]"
                            >
                              {runMutation.isPending && runMutation.variables === s.id ? (
                                <RefreshCw className="h-3 w-3 animate-spin" />
                              ) : (
                                <Play className="h-3 w-3" />
                              )}
                              Run Sync
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Ingestion Job Execution History & Error Logs */}
      <div className="surface-panel overflow-hidden">
        <div className="border-b border-slate-200 px-4 py-3">
          <h2 className="section-heading">Ingestion Job Log & Retry Telemetry</h2>
          <p className="text-[11px] text-slate-500">
            Incremental cursors, duplicate counts, retry attempts, and diagnostic warning/error entries
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-200 bg-slate-50/90 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-2">Job ID</th>
                <th className="px-3 py-2">Source</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2 text-right">Fetched / Inserted / Dup</th>
                <th className="px-3 py-2 text-right">Retries</th>
                <th className="px-3 py-2">Completed</th>
                <th className="px-4 py-2 text-right">Logs</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loadingJobs ? (
                <tr>
                  <td colSpan={8} className="p-6 text-center text-slate-400">
                    Loading job history...
                  </td>
                </tr>
              ) : (
                (jobsData?.items ?? []).map((j) => (
                  <tr key={j.id} className="hover:bg-slate-50">
                    <td className="px-4 py-2 font-mono text-[11px] font-medium text-indigo-700">
                      JOB-{j.id}
                    </td>
                    <td className="max-w-[200px] truncate px-3 py-2 font-medium text-slate-800">
                      {j.source_name}
                    </td>
                    <td className="px-3 py-2 font-mono text-[10px] uppercase text-slate-500">
                      {j.job_type}
                    </td>
                    <td className="px-3 py-2">
                      <StatusPill status={j.status} />
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-[11px] text-slate-700 tabular-nums">
                      {j.records_fetched.toLocaleString()} / {j.records_inserted.toLocaleString()} /{" "}
                      <span className="text-amber-700">{j.records_duplicated.toLocaleString()}</span>
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-[11px] tabular-nums">
                      {j.retry_count}
                    </td>
                    <td className="px-3 py-2 font-mono text-[10px] text-slate-500 whitespace-nowrap">
                      {j.completed_at ? new Date(j.completed_at).toLocaleString() : "Running..."}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {j.error_log.length > 0 ? (
                        <button
                          onClick={() => setSelectedJob(j)}
                          className="inline-flex items-center gap-1 rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-800 hover:bg-amber-100"
                        >
                          <AlertCircle className="h-3 w-3" /> {j.error_log.length} log(s)
                        </button>
                      ) : (
                        <span className="font-mono text-[10px] text-slate-400">Clean</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Job Log Modal */}
      {selectedJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="w-full max-w-lg rounded-lg border border-slate-200 bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
              <h3 className="text-sm font-semibold text-slate-900">
                Diagnostic Logs — JOB-{selectedJob.id} ({selectedJob.source_name})
              </h3>
              <button onClick={() => setSelectedJob(null)} className="text-slate-400 hover:text-slate-700">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="max-h-80 overflow-y-auto p-4 space-y-2">
              {selectedJob.error_log.map((entry, idx) => (
                <div key={idx} className="rounded border border-slate-200 bg-slate-50 p-3 text-xs">
                  <div className="flex items-center justify-between font-mono text-[10px]">
                    <span className="font-semibold text-amber-800">{entry.code || entry.level}</span>
                    <span className="text-slate-400">{entry.timestamp}</span>
                  </div>
                  <p className="mt-1 text-slate-700">{entry.message}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Create Source Modal */}
      {createOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3.5">
              <h3 className="text-sm font-semibold text-slate-900">Register Data Source Adapter</h3>
              <button onClick={() => setCreateOpen(false)} className="text-slate-400 hover:text-slate-700">
                <X className="h-4 w-4" />
              </button>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                createMutation.mutate();
              }}
              className="space-y-3 p-5"
            >
              <div>
                <label className="micro-label block mb-1">Source Name</label>
                <input required value={name} onChange={(e) => setName(e.target.value)} className="input-field" />
              </div>
              <div>
                <label className="micro-label block mb-1">Provider Adapter Type</label>
                <select
                  value={providerType}
                  onChange={(e) => setProviderType(e.target.value as typeof providerType)}
                  className="input-field"
                >
                  <option value="synthetic_stream">Synthetic Event Stream</option>
                  <option value="csv">Prepared CSV Dataset</option>
                  <option value="rss">Public RSS Feed</option>
                  <option value="public_api">Permitted Public API</option>
                </select>
              </div>
              {providerType !== "synthetic_stream" && (
                <div>
                  <label className="micro-label block mb-1">
                    {providerType === "csv" ? "CSV File Path" : "Endpoint / Feed URL"}
                  </label>
                  <input
                    value={endpointOrPath}
                    onChange={(e) => setEndpointOrPath(e.target.value)}
                    placeholder={
                      providerType === "csv"
                        ? "/app/data/prepared_civic_consultations_sample.csv"
                        : "https://feeds.example.gov/civic.xml"
                    }
                    className="input-field"
                  />
                </div>
              )}
              <div>
                <label className="micro-label block mb-1">Description</label>
                <textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} className="input-field" />
              </div>
              <div>
                <label className="micro-label block mb-1">Rate Limit (Requests / Min)</label>
                <input
                  type="number"
                  min={1}
                  max={600}
                  value={rateLimit}
                  onChange={(e) => setRateLimit(Number(e.target.value))}
                  className="input-field"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setCreateOpen(false)} className="btn-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={createMutation.isPending} className="btn-primary">
                  Register Source
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
