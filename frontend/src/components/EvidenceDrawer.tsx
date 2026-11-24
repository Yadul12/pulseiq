import React, { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Bookmark,
  CheckCircle2,
  Database,
  FileText,
  GitBranch,
  History,
  Save,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { apiRequest } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useWorkspace } from "../context/WorkspaceContext";
import type { MonitoringTopic, RecordDetail } from "../types";
import { ConfidenceBar, ProvenanceBadge, SentimentBadge, StatusPill } from "./Badges";

const REPORT_SECTIONS = [
  "",
  "Executive Finding",
  "Emerging Risk",
  "Public Service Feedback",
  "Policy Sentiment",
  "Counter-Evidence",
];

const SENTIMENT_OPTIONS = ["positive", "neutral", "mixed", "negative"] as const;

export const EvidenceDrawer: React.FC = () => {
  const { inspectedRecordId, closeRecordInspector, pushToast } = useWorkspace();
  const { canWrite } = useAuth();
  const queryClient = useQueryClient();

  const [tab, setTab] = useState<"compare" | "override" | "annotate">("compare");
  const [overrideTopic, setOverrideTopic] = useState("");
  const [overrideSentiment, setOverrideSentiment] = useState("");
  const [overrideReason, setOverrideReason] = useState("");

  const [isBookmarked, setIsBookmarked] = useState(false);
  const [isVerified, setIsVerified] = useState(false);
  const [note, setNote] = useState("");
  const [sectionTag, setSectionTag] = useState("");

  const { data: detail, isLoading, isError, refetch } = useQuery<RecordDetail>({
    queryKey: ["record-detail", inspectedRecordId],
    queryFn: () => apiRequest<RecordDetail>(`/records/${inspectedRecordId}`),
    enabled: inspectedRecordId !== null,
  });

  const { data: topics = [] } = useQuery<MonitoringTopic[]>({
    queryKey: ["topics-all"],
    queryFn: () => apiRequest<MonitoringTopic[]>("/topics"),
    enabled: inspectedRecordId !== null,
  });

  useEffect(() => {
    if (detail) {
      setOverrideTopic(detail.topic_classification.effective_topic);
      setOverrideSentiment(detail.sentiment_classification.effective_sentiment);
      setOverrideReason("");
      const latestAnn = detail.annotations[0];
      setIsBookmarked(latestAnn?.is_bookmarked ?? false);
      setIsVerified(latestAnn?.is_verified ?? false);
      setNote(latestAnn?.note ?? "");
      setSectionTag(latestAnn?.report_section_tag ?? "");
    }
  }, [detail]);

  const overrideMutation = useMutation({
    mutationFn: () =>
      apiRequest(`/records/${inspectedRecordId}/override`, {
        method: "POST",
        body: JSON.stringify({
          overridden_topic: overrideTopic || undefined,
          overridden_sentiment: overrideSentiment || undefined,
          override_reason: overrideReason,
        }),
      }),
    onSuccess: () => {
      pushToast("success", "Classification overridden", `REC-${inspectedRecordId} updated and logged in audit trail.`);
      queryClient.invalidateQueries({ queryKey: ["record-detail", inspectedRecordId] });
      queryClient.invalidateQueries({ queryKey: ["records"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      queryClient.invalidateQueries({ queryKey: ["methodology"] });
      setOverrideReason("");
      setTab("compare");
    },
    onError: (err: Error) => {
      pushToast("error", "Override failed", err.message);
    },
  });

  const annotationMutation = useMutation({
    mutationFn: () =>
      apiRequest(`/records/${inspectedRecordId}/annotation`, {
        method: "PUT",
        body: JSON.stringify({
          is_bookmarked: isBookmarked,
          is_verified: isVerified,
          note,
          report_section_tag: sectionTag || null,
        }),
      }),
    onSuccess: () => {
      pushToast("success", "Analyst annotation saved", `Evidence tags updated for REC-${inspectedRecordId}.`);
      queryClient.invalidateQueries({ queryKey: ["record-detail", inspectedRecordId] });
      queryClient.invalidateQueries({ queryKey: ["records"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
    },
    onError: (err: Error) => {
      pushToast("error", "Could not save annotation", err.message);
    },
  });

  if (inspectedRecordId === null) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/35 backdrop-blur-[1px]">
      <div className="flex h-full w-full max-w-2xl flex-col border-l border-slate-200 bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50/80 px-5 py-3.5">
          <div className="flex items-center gap-2.5">
            <span className="rounded bg-navy-900 px-2 py-0.5 font-mono text-xs font-medium text-white">
              REC-{inspectedRecordId}
            </span>
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Source Evidence & NLP Lineage</h2>
              <p className="text-[11px] text-slate-500">
                Original source text stored separately from processed model output
              </p>
            </div>
          </div>
          <button
            onClick={closeRecordInspector}
            className="rounded-md p-1.5 text-slate-400 transition hover:bg-slate-200/70 hover:text-slate-700"
            aria-label="Close inspector"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Tab Bar */}
        <div className="flex items-center justify-between border-b border-slate-200 px-5">
          <div className="flex gap-5">
            {[
              { id: "compare", label: "Raw vs Processed", icon: GitBranch },
              { id: "override", label: "Correct Classification", icon: ShieldCheck },
              { id: "annotate", label: "Analyst Notes & Verify", icon: Bookmark },
            ].map((t) => {
              const Icon = t.icon;
              const active = tab === t.id;
              return (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id as typeof tab)}
                  className={`flex items-center gap-1.5 border-b-2 py-2.5 text-xs font-medium transition ${
                    active
                      ? "border-indigo-700 text-indigo-700"
                      : "border-transparent text-slate-500 hover:text-slate-800"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {t.label}
                </button>
              );
            })}
          </div>
          {detail && <StatusPill status={detail.processed.processing_status} />}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {isLoading && (
            <div className="space-y-3 py-6">
              <div className="h-5 w-1/3 animate-pulse rounded bg-slate-200" />
              <div className="h-24 w-full animate-pulse rounded bg-slate-100" />
              <div className="h-24 w-full animate-pulse rounded bg-slate-100" />
            </div>
          )}

          {isError && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800">
              <p className="font-medium">Unable to load record details.</p>
              <button onClick={() => refetch()} className="mt-2 btn-secondary">
                Retry
              </button>
            </div>
          )}

          {detail && tab === "compare" && (
            <div className="space-y-4">
              {/* Source Metadata Bar */}
              <div className="flex flex-wrap items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-[11px]">
                <span className="font-medium text-slate-800">{detail.raw.source_name}</span>
                <span className="text-slate-300">|</span>
                <ProvenanceBadge isSynthetic={detail.raw.is_synthetic} label={detail.raw.provenance_label} />
                <span className="text-slate-300">|</span>
                <span className="font-mono text-slate-600">
                  {new Date(detail.raw.published_at).toLocaleString()}
                </span>
                <span className="text-slate-300">|</span>
                <span className="font-mono uppercase text-slate-600">
                  LANG: {detail.processed.detected_language} ({Math.round(detail.processed.language_confidence * 100)}%)
                </span>
                {detail.raw.has_missing_fields && (
                  <span className="inline-flex items-center gap-1 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-800 border border-amber-200">
                    <AlertTriangle className="h-3 w-3" /> Missing source metadata
                  </span>
                )}
                {detail.processed.is_duplicate && (
                  <span className="rounded bg-amber-100 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-amber-900">
                    DUPLICATE {detail.processed.duplicate_of_id ? `OF REC-${detail.processed.duplicate_of_id}` : ""}
                  </span>
                )}
              </div>

              {/* Dual Text Comparison */}
              <div className="grid grid-cols-1 gap-3">
                <div className="rounded-md border border-slate-200 bg-white p-3.5">
                  <div className="mb-1.5 flex items-center justify-between">
                    <span className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                      <Database className="h-3.5 w-3.5 text-slate-400" />
                      Original Source Record (Immutable)
                    </span>
                    <span className="font-mono text-[10px] text-slate-400">{detail.raw.external_id}</span>
                  </div>
                  {detail.raw.original_title && (
                    <p className="mb-1 text-xs font-semibold text-slate-900">{detail.raw.original_title}</p>
                  )}
                  <p className="text-[13px] leading-relaxed text-slate-800">{detail.raw.original_text}</p>
                  <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 border-t border-slate-100 pt-2 font-mono text-[10px] text-slate-500">
                    <span>Author: {detail.raw.author_handle_anonymized || "— (missing)"}</span>
                    <span>Hash: {detail.raw.content_hash.slice(0, 14)}…</span>
                    <span>Adapter: {detail.raw.provider_type}</span>
                  </div>
                </div>

                <div className="rounded-md border border-indigo-200/70 bg-indigo-50/25 p-3.5">
                  <div className="mb-1.5 flex items-center justify-between">
                    <span className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-indigo-800">
                      <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
                      Processed Pipeline Output ({detail.processed.processing_version})
                    </span>
                  </div>
                  <p className="text-xs leading-relaxed text-slate-700">{detail.processed.normalized_text}</p>

                  {/* Entities & Keywords */}
                  <div className="mt-3 grid grid-cols-2 gap-3 border-t border-indigo-100 pt-2.5">
                    <div>
                      <span className="micro-label block mb-1">Extracted Civic Entities</span>
                      <div className="flex flex-wrap gap-1">
                        {detail.processed.entities.length > 0 ? (
                          detail.processed.entities.map((e, i) => (
                            <span
                              key={i}
                              className="inline-flex items-center gap-1 rounded border border-indigo-200 bg-white px-1.5 py-0.5 text-[10px] text-slate-800"
                            >
                              <span className="font-medium">{e.text}</span>
                              <span className="font-mono text-[9px] text-indigo-600">{e.type}</span>
                            </span>
                          ))
                        ) : (
                          <span className="text-[11px] text-slate-400">No gazetteer entities matched</span>
                        )}
                      </div>
                    </div>
                    <div>
                      <span className="micro-label block mb-1">Salient Keywords</span>
                      <div className="flex flex-wrap gap-1">
                        {detail.processed.extracted_keywords.map((k, i) => (
                          <span
                            key={i}
                            className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-700"
                          >
                            {k}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Classification Breakdown */}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="rounded-md border border-slate-200 p-3.5">
                  <div className="flex items-center justify-between">
                    <span className="micro-label">Topic Classification</span>
                    <ConfidenceBar value={detail.topic_classification.confidence} />
                  </div>
                  <p className="mt-1.5 text-xs font-semibold text-slate-900">
                    {detail.topic_classification.effective_topic}
                  </p>
                  {detail.topic_classification.is_overridden && (
                    <div className="mt-1.5 rounded border border-indigo-200 bg-indigo-50/70 px-2 py-1 text-[11px] text-indigo-900">
                      <span className="font-semibold">Analyst Override:</span> model predicted{" "}
                      <span className="line-through opacity-75">{detail.topic_classification.predicted_topic}</span>
                      {detail.topic_classification.override_reason && (
                        <p className="mt-0.5 text-[10px] text-indigo-700">
                          Reason: {detail.topic_classification.override_reason}
                        </p>
                      )}
                    </div>
                  )}
                  <div className="mt-2.5 space-y-1">
                    {Object.entries(detail.topic_classification.class_probabilities)
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 3)
                      .map(([cls, prob]) => (
                        <div key={cls} className="flex items-center justify-between text-[10px]">
                          <span className="truncate pr-2 text-slate-600">{cls}</span>
                          <span className="font-mono text-slate-500 tabular-nums">{Math.round(prob * 100)}%</span>
                        </div>
                      ))}
                  </div>
                  <p className="mt-2 font-mono text-[10px] text-slate-400">
                    Model: {detail.topic_classification.model_name}
                  </p>
                </div>

                <div className="rounded-md border border-slate-200 p-3.5">
                  <div className="flex items-center justify-between">
                    <span className="micro-label">Sentiment Classification</span>
                    <ConfidenceBar value={detail.sentiment_classification.confidence} />
                  </div>
                  <div className="mt-1.5 flex items-center gap-2">
                    <SentimentBadge
                      sentiment={detail.sentiment_classification.effective_sentiment}
                      overridden={detail.sentiment_classification.is_overridden}
                    />
                    <span className="font-mono text-[11px] text-slate-500 tabular-nums">
                      score {detail.sentiment_classification.sentiment_score >= 0 ? "+" : ""}
                      {detail.sentiment_classification.sentiment_score.toFixed(2)}
                    </span>
                  </div>
                  {detail.sentiment_classification.is_overridden && (
                    <div className="mt-1.5 rounded border border-indigo-200 bg-indigo-50/70 px-2 py-1 text-[11px] text-indigo-900">
                      <span className="font-semibold">Analyst Override:</span> model predicted{" "}
                      <span className="capitalize line-through opacity-75">
                        {detail.sentiment_classification.predicted_sentiment}
                      </span>
                      {detail.sentiment_classification.override_reason && (
                        <p className="mt-0.5 text-[10px] text-indigo-700">
                          Reason: {detail.sentiment_classification.override_reason}
                        </p>
                      )}
                    </div>
                  )}
                  <div className="mt-2.5 space-y-1">
                    {Object.entries(detail.sentiment_classification.class_probabilities)
                      .sort((a, b) => b[1] - a[1])
                      .map(([cls, prob]) => (
                        <div key={cls} className="flex items-center justify-between text-[10px]">
                          <span className="capitalize text-slate-600">{cls}</span>
                          <span className="font-mono text-slate-500 tabular-nums">{Math.round(prob * 100)}%</span>
                        </div>
                      ))}
                  </div>
                  <p className="mt-2 font-mono text-[10px] text-slate-400">
                    Model: {detail.sentiment_classification.model_name}
                  </p>
                </div>
              </div>

              {/* Existing Analyst Notes */}
              {detail.annotations.length > 0 && (
                <div className="rounded-md border border-slate-200 bg-slate-50/70 p-3.5">
                  <span className="micro-label flex items-center gap-1.5 mb-2">
                    <FileText className="h-3.5 w-3.5" /> Analyst Annotations
                  </span>
                  <div className="space-y-2">
                    {detail.annotations.map((ann) => (
                      <div key={ann.id} className="rounded border border-slate-200 bg-white p-2.5 text-xs">
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-slate-800">{ann.analyst_name}</span>
                          <div className="flex items-center gap-1.5">
                            {ann.is_verified && (
                              <span className="inline-flex items-center gap-0.5 rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700">
                                <CheckCircle2 className="h-3 w-3" /> Verified
                              </span>
                            )}
                            {ann.report_section_tag && (
                              <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-medium text-indigo-700">
                                {ann.report_section_tag}
                              </span>
                            )}
                          </div>
                        </div>
                        {ann.note && <p className="mt-1 text-slate-600">{ann.note}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {detail && tab === "override" && (
            <div className="space-y-4">
              <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
                Human analyst overrides supersede automated model predictions in all analytics and reports while preserving
                original model outputs and logging an immutable audit record.
              </div>
              {!canWrite ? (
                <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-3">
                  Your current role (Viewer) has read-only access. Sign in as an Analyst or Admin to override classifications.
                </p>
              ) : (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    overrideMutation.mutate();
                  }}
                  className="space-y-3.5"
                >
                  <div>
                    <label className="micro-label block mb-1">Corrected Topic</label>
                    <select
                      className="input-field"
                      value={overrideTopic}
                      onChange={(e) => setOverrideTopic(e.target.value)}
                    >
                      {Array.from(
                        new Set([
                          detail.topic_classification.predicted_topic,
                          detail.topic_classification.effective_topic,
                          ...topics.map((t) => t.name),
                        ])
                      ).map((name) => (
                        <option key={name} value={name}>
                          {name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="micro-label block mb-1">Corrected Sentiment</label>
                    <div className="grid grid-cols-4 gap-2">
                      {SENTIMENT_OPTIONS.map((opt) => (
                        <button
                          type="button"
                          key={opt}
                          onClick={() => setOverrideSentiment(opt)}
                          className={`rounded-md border px-2.5 py-2 text-xs font-medium capitalize transition ${
                            overrideSentiment === opt
                              ? "border-indigo-600 bg-indigo-50 text-indigo-900"
                              : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                          }`}
                        >
                          {opt}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="micro-label block mb-1">Override Justification (Required for Audit Trail)</label>
                    <textarea
                      rows={3}
                      required
                      minLength={5}
                      className="input-field"
                      placeholder="Explain why the automated prediction was inaccurate (e.g., sarcasm misclassified as positive, secondary policy domain)..."
                      value={overrideReason}
                      onChange={(e) => setOverrideReason(e.target.value)}
                    />
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-2">
                    <button type="button" onClick={() => setTab("compare")} className="btn-secondary">
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={overrideMutation.isPending || overrideReason.trim().length < 5}
                      className="btn-primary"
                    >
                      <History className="h-3.5 w-3.5" />
                      {overrideMutation.isPending ? "Saving Override..." : "Apply Verified Override"}
                    </button>
                  </div>
                </form>
              )}
            </div>
          )}

          {detail && tab === "annotate" && (
            <div className="space-y-4">
              {!canWrite ? (
                <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-3">
                  Read-only role: sign in as an Analyst or Admin to bookmark, verify, or annotate records.
                </p>
              ) : (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    annotationMutation.mutate();
                  }}
                  className="space-y-4"
                >
                  <div className="flex flex-wrap gap-3">
                    <label className="flex cursor-pointer items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50">
                      <input
                        type="checkbox"
                        checked={isBookmarked}
                        onChange={(e) => setIsBookmarked(e.target.checked)}
                        className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                      />
                      <Bookmark className="h-3.5 w-3.5 text-indigo-600" />
                      Bookmark in Workspace
                    </label>
                    <label className="flex cursor-pointer items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50">
                      <input
                        type="checkbox"
                        checked={isVerified}
                        onChange={(e) => setIsVerified(e.target.checked)}
                        className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                      />
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                      Mark Evidence as Verified
                    </label>
                  </div>

                  <div>
                    <label className="micro-label block mb-1">Assign to Report Section</label>
                    <select
                      className="input-field"
                      value={sectionTag}
                      onChange={(e) => setSectionTag(e.target.value)}
                    >
                      {REPORT_SECTIONS.map((s) => (
                        <option key={s || "none"} value={s}>
                          {s || "— Unassigned —"}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="micro-label block mb-1">Analyst Briefing Note</label>
                    <textarea
                      rows={4}
                      className="input-field"
                      placeholder="Document corroboration details, geographic context, or briefing commentary..."
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                    />
                  </div>

                  <div className="flex justify-end">
                    <button type="submit" disabled={annotationMutation.isPending} className="btn-primary">
                      <Save className="h-3.5 w-3.5" />
                      {annotationMutation.isPending ? "Saving..." : "Save Annotation"}
                    </button>
                  </div>
                </form>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
