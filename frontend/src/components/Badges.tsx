import React from "react";

export const SENTIMENT_COLORS: Record<string, string> = {
  positive: "#2E7D63",
  neutral: "#64748B",
  mixed: "#B47B2B",
  negative: "#B4434A",
};

export const SentimentBadge: React.FC<{
  sentiment: string;
  confidence?: number;
  overridden?: boolean;
}> = ({ sentiment, confidence, overridden }) => {
  const styles: Record<string, string> = {
    positive: "bg-emerald-50/90 text-[#23634D] border-emerald-200/80",
    neutral: "bg-slate-100 text-slate-700 border-slate-200",
    mixed: "bg-amber-50/90 text-[#925E18] border-amber-200/90",
    negative: "bg-rose-50/90 text-[#99353C] border-rose-200/80",
  };
  const cls = styles[sentiment] || styles.neutral;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-medium capitalize tabular-nums ${cls}`}
    >
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: SENTIMENT_COLORS[sentiment] || "#64748B" }}
      />
      {sentiment}
      {typeof confidence === "number" && (
        <span className="font-mono text-[10px] opacity-75">{Math.round(confidence * 100)}%</span>
      )}
      {overridden && (
        <span
          title="Analyst verified override"
          className="ml-0.5 rounded bg-indigo-100 px-1 text-[9px] font-semibold uppercase tracking-wide text-indigo-800"
        >
          OVR
        </span>
      )}
    </span>
  );
};

export const ProvenanceBadge: React.FC<{ isSynthetic: boolean; label?: string }> = ({
  isSynthetic,
  label,
}) => {
  const shortLabel =
    label === "PREPARED_CSV_SYNTHETIC"
      ? "Prepared CSV (Syn)"
      : label === "PUBLIC_RSS_SYNTHETIC_FALLBACK"
      ? "RSS Fallback (Syn)"
      : label === "PERMITTED_API_SYNTHETIC_FALLBACK"
      ? "API Fallback (Syn)"
      : label === "SYNTHETIC_STREAM"
      ? "Synthetic Stream"
      : isSynthetic
      ? "Synthetic"
      : label || "Public Source";

  return (
    <span
      title={`Data Provenance: ${label || (isSynthetic ? "SYNTHETIC" : "PUBLIC")}`}
      className={`inline-flex items-center rounded border px-1.5 py-0.5 font-mono text-[10px] font-medium ${
        isSynthetic
          ? "border-slate-200 bg-slate-50 text-slate-600"
          : "border-blue-200 bg-blue-50 text-blue-700"
      }`}
    >
      {shortLabel}
    </span>
  );
};

export const StatusPill: React.FC<{ status: string }> = ({ status }) => {
  const map: Record<string, string> = {
    active: "bg-emerald-50 text-emerald-800 border-emerald-200",
    healthy: "bg-emerald-50 text-emerald-800 border-emerald-200",
    completed: "bg-emerald-50 text-emerald-800 border-emerald-200",
    published: "bg-emerald-50 text-emerald-800 border-emerald-200",
    processed: "bg-slate-100 text-slate-700 border-slate-200",
    paused: "bg-amber-50 text-amber-800 border-amber-200",
    degraded: "bg-amber-50 text-amber-800 border-amber-200",
    partial: "bg-amber-50 text-amber-800 border-amber-200",
    needs_review: "bg-amber-50 text-amber-800 border-amber-200",
    reviewed: "bg-indigo-50 text-indigo-800 border-indigo-200",
    running: "bg-blue-50 text-blue-800 border-blue-200",
    queued: "bg-blue-50 text-blue-800 border-blue-200",
    draft: "bg-slate-100 text-slate-700 border-slate-200",
    archived: "bg-slate-100 text-slate-500 border-slate-200",
    idle: "bg-slate-100 text-slate-600 border-slate-200",
    error: "bg-rose-50 text-rose-800 border-rose-200",
    failed: "bg-rose-50 text-rose-800 border-rose-200",
  };
  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
        map[status] || "bg-slate-100 text-slate-700 border-slate-200"
      }`}
    >
      {status.replace("_", " ")}
    </span>
  );
};

export const ConfidenceBar: React.FC<{ value: number }> = ({ value }) => {
  const pct = Math.round(value * 100);
  const color =
    value >= 0.72 ? "bg-indigo-600" : value >= 0.56 ? "bg-amber-500" : "bg-rose-500";
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1.5 w-14 overflow-hidden rounded-full bg-slate-200">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-[11px] text-slate-600 tabular-nums">{pct}%</span>
    </div>
  );
};
