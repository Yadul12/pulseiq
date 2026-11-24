import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  Compass,
  Edit3,
  Pause,
  Play,
  Plus,
  RefreshCw,
  X,
} from "lucide-react";
import { apiRequest } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useWorkspace } from "../context/WorkspaceContext";
import type { DataSource, MonitoringTopic } from "../types";
import { StatusPill } from "../components/Badges";

const CATEGORIES = [
  "Infrastructure",
  "Government Services",
  "Environment",
  "Public Policy",
  "Community",
  "Public Events",
];

const LANGUAGES = [
  { value: "all", label: "All Languages" },
  { value: "en", label: "English (en)" },
  { value: "es", label: "Spanish (es)" },
  { value: "fr", label: "French (fr)" },
  { value: "de", label: "German (de)" },
  { value: "pt", label: "Portuguese (pt)" },
];

export const MonitoringTopicsPage: React.FC = () => {
  const { canWrite } = useAuth();
  const { pushToast } = useWorkspace();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [modalOpen, setModalOpen] = useState(false);
  const [editingTopic, setEditingTopic] = useState<MonitoringTopic | null>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [keywordsText, setKeywordsText] = useState("");
  const [excludedText, setExcludedText] = useState("");
  const [selectedSourceIds, setSelectedSourceIds] = useState<number[]>([]);
  const [timeRangeDays, setTimeRangeDays] = useState(30);
  const [language, setLanguage] = useState("all");

  const { data: topics = [], isLoading } = useQuery<MonitoringTopic[]>({
    queryKey: ["topics-list", statusFilter],
    queryFn: () =>
      apiRequest<MonitoringTopic[]>(
        statusFilter === "all" ? "/topics" : `/topics?status=${statusFilter}`
      ),
  });

  const { data: sources = [] } = useQuery<DataSource[]>({
    queryKey: ["sources-list"],
    queryFn: () => apiRequest<DataSource[]>("/sources"),
  });

  const openCreateModal = () => {
    setEditingTopic(null);
    setName("");
    setDescription("");
    setCategory(CATEGORIES[0]);
    setKeywordsText("");
    setExcludedText("");
    setSelectedSourceIds(sources.filter((s) => s.is_enabled).map((s) => s.id));
    setTimeRangeDays(30);
    setLanguage("all");
    setModalOpen(true);
  };

  const openEditModal = (t: MonitoringTopic) => {
    setEditingTopic(t);
    setName(t.name);
    setDescription(t.description);
    setCategory(t.category);
    setKeywordsText(t.keywords.join(", "));
    setExcludedText(t.excluded_keywords.join(", "));
    setSelectedSourceIds(t.data_source_ids || []);
    setTimeRangeDays(t.time_range_days);
    setLanguage(t.language);
    setModalOpen(true);
  };

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = {
        name,
        description,
        category,
        keywords: keywordsText
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        excluded_keywords: excludedText
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        data_source_ids: selectedSourceIds,
        time_range_days: timeRangeDays,
        language,
      };
      if (editingTopic) {
        return apiRequest(`/topics/${editingTopic.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      }
      return apiRequest("/topics", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: () => {
      pushToast(
        "success",
        editingTopic ? "Monitoring topic updated" : "Monitoring topic created",
        `"${name}" configuration saved.`
      );
      queryClient.invalidateQueries({ queryKey: ["topics-list"] });
      queryClient.invalidateQueries({ queryKey: ["topics-sidebar"] });
      setModalOpen(false);
    },
    onError: (err: Error) => pushToast("error", "Could not save topic", err.message),
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: "active" | "paused" | "archived" }) =>
      apiRequest(`/topics/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
    onSuccess: (_res, vars) => {
      pushToast("info", "Topic status updated", `Monitoring status set to ${vars.status}.`);
      queryClient.invalidateQueries({ queryKey: ["topics-list"] });
      queryClient.invalidateQueries({ queryKey: ["topics-sidebar"] });
    },
    onError: (err: Error) => pushToast("error", "Status change failed", err.message),
  });

  const ingestMutation = useMutation({
    mutationFn: (id: number) =>
      apiRequest<{ records_inserted: number; records_duplicated: number; source_name: string }>(
        `/topics/${id}/ingest`,
        {
          method: "POST",
          body: JSON.stringify({ batch_size: 20, use_celery: false }),
        }
      ),
    onSuccess: (res) => {
      pushToast(
        "success",
        "Topic ingestion & NLP pipeline complete",
        `+${res.records_inserted} records processed (${res.records_duplicated} duplicates flagged) from ${res.source_name}.`
      );
      queryClient.invalidateQueries({ queryKey: ["topics-list"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      queryClient.invalidateQueries({ queryKey: ["explorer"] });
      queryClient.invalidateQueries({ queryKey: ["records"] });
    },
    onError: (err: Error) => pushToast("error", "Ingestion failed", err.message),
  });

  const toggleSource = (id: number) => {
    setSelectedSourceIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-base font-semibold tracking-tight text-slate-900">
            Monitoring Workspace
          </h1>
          <p className="text-xs text-slate-500">
            Define keyword scopes, excluded terms, permitted sources, and language rules for civic issue tracking
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-md border border-slate-200 bg-white p-0.5">
            {["all", "active", "paused", "archived"].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`rounded px-2.5 py-1 text-[11px] font-medium capitalize transition ${
                  statusFilter === st
                    ? "bg-navy-900 text-white"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {st}
              </button>
            ))}
          </div>
          {canWrite && (
            <button onClick={openCreateModal} className="btn-primary">
              <Plus className="h-3.5 w-3.5" />
              New Monitoring Topic
            </button>
          )}
        </div>
      </div>

      {/* Topics Data Table */}
      <div className="surface-panel overflow-hidden">
        {isLoading ? (
          <div className="p-6 space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded bg-slate-100" />
            ))}
          </div>
        ) : topics.length === 0 ? (
          <div className="p-10 text-center">
            <p className="text-xs font-medium text-slate-700">No monitoring topics match this filter.</p>
            {canWrite && (
              <button onClick={openCreateModal} className="mt-3 btn-primary">
                Create First Topic
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200 bg-slate-50/90 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-4 py-2.5">Monitoring Topic & Scope</th>
                  <th className="px-3 py-2.5">Keywords / Exclusions</th>
                  <th className="px-3 py-2.5 text-center">Window / Lang</th>
                  <th className="px-3 py-2.5 text-right">Indexed</th>
                  <th className="px-3 py-2.5 text-right">Avg Tone</th>
                  <th className="px-3 py-2.5">Status</th>
                  <th className="px-4 py-2.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {topics.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-50/70">
                    <td className="max-w-xs px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-900">{t.name}</span>
                        {t.has_emerging_trend && (
                          <span className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[9px] font-semibold text-amber-800">
                            EMERGING
                          </span>
                        )}
                      </div>
                      <p className="mt-0.5 line-clamp-2 text-[11px] text-slate-500">{t.description}</p>
                      <span className="mt-1 inline-block font-mono text-[10px] text-indigo-700">
                        {t.category} · {(t.data_source_ids || []).length} sources
                      </span>
                    </td>
                    <td className="max-w-xs px-3 py-3">
                      <div className="flex flex-wrap gap-1">
                        {t.keywords.slice(0, 6).map((kw) => (
                          <span
                            key={kw}
                            className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 font-mono text-[10px] text-slate-700"
                          >
                            +{kw}
                          </span>
                        ))}
                        {t.keywords.length > 6 && (
                          <span className="text-[10px] text-slate-400">+{t.keywords.length - 6}</span>
                        )}
                      </div>
                      {t.excluded_keywords.length > 0 && (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {t.excluded_keywords.slice(0, 3).map((ex) => (
                            <span
                              key={ex}
                              className="rounded border border-rose-200/70 bg-rose-50/60 px-1.5 py-0.5 font-mono text-[10px] text-rose-700"
                            >
                              -{ex}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-3 text-center font-mono text-[11px] text-slate-600 tabular-nums">
                      <div>{t.time_range_days}d</div>
                      <div className="text-[10px] uppercase text-slate-400">{t.language}</div>
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-xs text-slate-800 tabular-nums">
                      <div>{(t.record_count ?? 0).toLocaleString()}</div>
                      <div className="text-[10px] text-slate-400">+{t.recent_24h_count ?? 0} (24h)</div>
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-[11px] tabular-nums">
                      <span
                        className={
                          (t.avg_sentiment ?? 0) < -0.15
                            ? "text-[#99353C]"
                            : (t.avg_sentiment ?? 0) > 0.15
                            ? "text-[#23634D]"
                            : "text-slate-600"
                        }
                      >
                        {(t.avg_sentiment ?? 0) >= 0 ? "+" : ""}
                        {(t.avg_sentiment ?? 0).toFixed(2)}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <StatusPill status={t.status} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => navigate(`/explorer?topicId=${t.id}`)}
                          className="rounded border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-100 hover:text-indigo-700"
                          title="Explore Topic Evidence & Clusters"
                        >
                          <Compass className="h-3.5 w-3.5" />
                        </button>
                        {canWrite && t.status !== "archived" && (
                          <button
                            onClick={() => ingestMutation.mutate(t.id)}
                            disabled={ingestMutation.isPending}
                            className="rounded border border-indigo-200 bg-indigo-50/70 p-1.5 text-indigo-700 hover:bg-indigo-100"
                            title="Run Incremental Ingestion & NLP Pipeline Now"
                          >
                            <RefreshCw
                              className={`h-3.5 w-3.5 ${
                                ingestMutation.isPending && ingestMutation.variables === t.id
                                  ? "animate-spin"
                                  : ""
                              }`}
                            />
                          </button>
                        )}
                        {canWrite && (
                          <>
                            <button
                              onClick={() => openEditModal(t)}
                              className="rounded border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-100"
                              title="Edit Topic"
                            >
                              <Edit3 className="h-3.5 w-3.5" />
                            </button>
                            {t.status === "active" ? (
                              <button
                                onClick={() => statusMutation.mutate({ id: t.id, status: "paused" })}
                                className="rounded border border-slate-200 p-1.5 text-amber-700 hover:bg-amber-50"
                                title="Pause Monitoring"
                              >
                                <Pause className="h-3.5 w-3.5" />
                              </button>
                            ) : (
                              <button
                                onClick={() => statusMutation.mutate({ id: t.id, status: "active" })}
                                className="rounded border border-slate-200 p-1.5 text-emerald-700 hover:bg-emerald-50"
                                title="Resume Active Monitoring"
                              >
                                <Play className="h-3.5 w-3.5" />
                              </button>
                            )}
                            {t.status !== "archived" && (
                              <button
                                onClick={() => statusMutation.mutate({ id: t.id, status: "archived" })}
                                className="rounded border border-slate-200 p-1.5 text-slate-500 hover:bg-slate-100"
                                title="Archive Topic"
                              >
                                <Archive className="h-3.5 w-3.5" />
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create / Edit Topic Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-[1px]">
          <div className="w-full max-w-xl rounded-lg border border-slate-200 bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3.5">
              <h2 className="text-sm font-semibold text-slate-900">
                {editingTopic ? "Edit Monitoring Topic" : "Create Monitoring Topic"}
              </h2>
              <button onClick={() => setModalOpen(false)} className="text-slate-400 hover:text-slate-700">
                <X className="h-4 w-4" />
              </button>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                saveMutation.mutate();
              }}
              className="space-y-3.5 p-5"
            >
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className="micro-label block mb-1">Topic Name</label>
                  <input
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Stormwater & Flood Infrastructure"
                    className="input-field"
                  />
                </div>
                <div>
                  <label className="micro-label block mb-1">Civic Domain Category</label>
                  <select value={category} onChange={(e) => setCategory(e.target.value)} className="input-field">
                    {CATEGORIES.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="micro-label block mb-1">Analyst Scope Description</label>
                <textarea
                  rows={2}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Describe the public service, policy, or infrastructure focus..."
                  className="input-field"
                />
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className="micro-label block mb-1">Include Keywords (comma-separated)</label>
                  <input
                    required
                    value={keywordsText}
                    onChange={(e) => setKeywordsText(e.target.value)}
                    placeholder="stormwater, drain, flooding, culvert"
                    className="input-field"
                  />
                </div>
                <div>
                  <label className="micro-label block mb-1">Excluded Keywords (comma-separated)</label>
                  <input
                    value={excludedText}
                    onChange={(e) => setExcludedText(e.target.value)}
                    placeholder="commercial ad, sports"
                    className="input-field"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="micro-label block mb-1">Default Time Window (Days)</label>
                  <input
                    type="number"
                    min={1}
                    max={365}
                    value={timeRangeDays}
                    onChange={(e) => setTimeRangeDays(Number(e.target.value))}
                    className="input-field"
                  />
                </div>
                <div>
                  <label className="micro-label block mb-1">Language Filter</label>
                  <select value={language} onChange={(e) => setLanguage(e.target.value)} className="input-field">
                    {LANGUAGES.map((l) => (
                      <option key={l.value} value={l.value}>
                        {l.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="micro-label block mb-1.5">Configured Data Sources ({selectedSourceIds.length} selected)</label>
                <div className="grid max-h-36 grid-cols-1 gap-1.5 overflow-y-auto rounded-md border border-slate-200 p-2 sm:grid-cols-2">
                  {sources.map((s) => (
                    <label
                      key={s.id}
                      className="flex cursor-pointer items-center gap-2 rounded px-1.5 py-1 text-[11px] text-slate-700 hover:bg-slate-50"
                    >
                      <input
                        type="checkbox"
                        checked={selectedSourceIds.includes(s.id)}
                        onChange={() => toggleSource(s.id)}
                        className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                      />
                      <span className="truncate">{s.name}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="flex justify-end gap-2 border-t border-slate-100 pt-3">
                <button type="button" onClick={() => setModalOpen(false)} className="btn-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={saveMutation.isPending} className="btn-primary">
                  {saveMutation.isPending
                    ? "Saving..."
                    : editingTopic
                    ? "Save Changes"
                    : "Create Monitoring Topic"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
