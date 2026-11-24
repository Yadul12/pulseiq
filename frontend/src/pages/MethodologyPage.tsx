import React from "react";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, Cpu, Scale, ShieldAlert } from "lucide-react";
import { apiRequest } from "../api/client";

interface MethodologyTelemetry {
  pipeline_version: string;
  models: {
    topic_classifier: { name: string; version: string; avg_confidence: number };
    sentiment_classifier: { name: string; version: string; avg_confidence: number };
    embedding_clustering: { backend: string; algorithm: string };
    trend_detection: { algorithm: string; emerging_threshold_z: number };
  };
  corpus_telemetry: {
    total_raw_records: number;
    total_processed_records: number;
    synthetic_records: number;
    synthetic_pct: number;
    duplicate_records: number;
    duplicate_rate_pct: number;
    missing_field_records: number;
    missing_field_rate_pct: number;
    needs_review_queue: number;
    needs_review_pct: number;
    topic_overrides: number;
    sentiment_overrides: number;
    language_distribution: Array<{ language: string; count: number }>;
    provenance_breakdown: Array<{ label: string; count: number }>;
  };
  classification_definitions: Record<string, string>;
  limitations: string[];
}

const PIPELINE_STAGES = [
  ["1. Data Ingestion", "Modular CSV, Public RSS, Permitted API, and clearly labelled Synthetic adapters with rate-limiting and retry."],
  ["2. Text Normalisation", "HTML stripping, Unicode normalization, URL/email/handle privacy redaction. Original raw text remains untouched."],
  ["3. Language Detection", "Deterministic multilingual stopword + diacritic scorer covering en, es, fr, de, and pt with confidence scores."],
  ["4. Duplicate Detection", "Exact SHA-256 content hashing paired with order-insensitive shingle signatures to flag syndicated duplicates."],
  ["5. Topic Classification", "Calibrated scikit-learn TF-IDF (1-2 grams) + LogisticRegression trained on an independent civic corpus."],
  ["6. Sentiment Classification", "4-class calibrated model (positive, neutral, mixed, negative) + continuous polarity score [-1, +1]."],
  ["7. Entity Extraction", "Zero-hallucination civic gazetteer extracting agencies, corridors, infrastructure, policies, and events."],
  ["8. Topic Clustering", "Dense L2-normalized semantic vectors (Sentence-Transformers optional / TF-IDF+SVD default) + MiniBatchKMeans."],
  ["9. Trend Detection", "Modified Z-score burst detection comparing 72h daily velocity against trailing 27-day rolling baseline."],
  ["10. Analyst Review", "Confidence-routed verification queue (<0.56), human overrides with audit trail, and evidence-grounded reporting."],
];

export const MethodologyPage: React.FC = () => {
  const { data, isLoading } = useQuery<MethodologyTelemetry>({
    queryKey: ["methodology"],
    queryFn: () => apiRequest<MethodologyTelemetry>("/methodology"),
  });

  if (isLoading || !data) {
    return <div className="surface-panel h-96 animate-pulse" />;
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-base font-semibold tracking-tight text-slate-900">
          NLP Methodology, Reliability & Data Limitations
        </h1>
        <p className="text-xs text-slate-500">
          Transparent model specifications, corpus coverage diagnostics, classification definitions, and ethical intelligence boundaries
        </p>
      </div>

      {/* Explicit Non-Polling Notice */}
      <div className="rounded-lg border border-amber-200 bg-amber-50/80 px-4 py-3 text-xs text-amber-950">
        <div className="flex items-start gap-2.5">
          <Scale className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" />
          <div>
            <p className="font-semibold">Scientific Interpretation & Ethical Boundary Notice</p>
            <p className="mt-0.5 leading-relaxed text-amber-900/90">
              PulseIQ sentiment and volume metrics are NOT a scientifically representative measure of general public opinion.
              Public discussion sources reflect self-selected participants and configured synthetic/prepared streams. PulseIQ
              strictly prohibits unauthorized scraping, individual political profiling, voter persuasion, or micro-targeting.
            </p>
          </div>
        </div>
      </div>

      {/* Live Corpus Reliability Telemetry */}
      <div className="surface-panel grid grid-cols-2 divide-y divide-slate-200 sm:grid-cols-3 lg:grid-cols-6 lg:divide-x lg:divide-y-0">
        <div className="px-4 py-3">
          <div className="micro-label">Indexed Corpus</div>
          <div className="mt-1 font-mono text-lg font-semibold text-slate-900 tabular-nums">
            {data.corpus_telemetry.total_raw_records.toLocaleString()}
          </div>
          <div className="text-[10px] text-slate-500">{data.pipeline_version}</div>
        </div>
        <div className="px-4 py-3">
          <div className="micro-label">Synthetic Disclosure</div>
          <div className="mt-1 font-mono text-lg font-semibold text-slate-900 tabular-nums">
            {data.corpus_telemetry.synthetic_pct}%
          </div>
          <div className="text-[10px] text-slate-500">
            {data.corpus_telemetry.synthetic_records.toLocaleString()} labelled rows
          </div>
        </div>
        <div className="px-4 py-3">
          <div className="micro-label">Duplicate Rate</div>
          <div className="mt-1 font-mono text-lg font-semibold text-slate-900 tabular-nums">
            {data.corpus_telemetry.duplicate_rate_pct}%
          </div>
          <div className="text-[10px] text-slate-500">
            {data.corpus_telemetry.duplicate_records.toLocaleString()} flagged copies
          </div>
        </div>
        <div className="px-4 py-3">
          <div className="micro-label">Missing Metadata</div>
          <div className="mt-1 font-mono text-lg font-semibold text-slate-900 tabular-nums">
            {data.corpus_telemetry.missing_field_rate_pct}%
          </div>
          <div className="text-[10px] text-slate-500">
            {data.corpus_telemetry.missing_field_records.toLocaleString()} partial rows
          </div>
        </div>
        <div className="px-4 py-3">
          <div className="micro-label">Review Queue (&lt;56%)</div>
          <div className="mt-1 font-mono text-lg font-semibold text-amber-800 tabular-nums">
            {data.corpus_telemetry.needs_review_pct}%
          </div>
          <div className="text-[10px] text-slate-500">
            {data.corpus_telemetry.needs_review_queue.toLocaleString()} records routed
          </div>
        </div>
        <div className="px-4 py-3">
          <div className="micro-label">Human Overrides</div>
          <div className="mt-1 font-mono text-lg font-semibold text-indigo-700 tabular-nums">
            {data.corpus_telemetry.topic_overrides + data.corpus_telemetry.sentiment_overrides}
          </div>
          <div className="text-[10px] text-slate-500">
            {data.corpus_telemetry.topic_overrides} topic · {data.corpus_telemetry.sentiment_overrides} tone
          </div>
        </div>
      </div>

      {/* Model Registry + Classification Definitions */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="surface-panel p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-indigo-700" />
            <h2 className="section-heading">Active Model Specifications</h2>
          </div>
          <div className="divide-y divide-slate-100 text-xs">
            <div className="flex justify-between py-2">
              <span className="text-slate-500">Topic Classifier</span>
              <span className="font-mono text-slate-800">
                {data.models.topic_classifier.name} (avg conf {Math.round(data.models.topic_classifier.avg_confidence * 100)}%)
              </span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-slate-500">Sentiment Classifier</span>
              <span className="font-mono text-slate-800">
                {data.models.sentiment_classifier.name} (avg conf {Math.round(data.models.sentiment_classifier.avg_confidence * 100)}%)
              </span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-slate-500">Semantic Clustering Backend</span>
              <span className="font-mono text-slate-800">{data.models.embedding_clustering.backend}</span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-slate-500">Burst / Emerging Trend Model</span>
              <span className="font-mono text-slate-800">Z &ge; {data.models.trend_detection.emerging_threshold_z}</span>
            </div>
          </div>

          <div className="border-t border-slate-100 pt-3">
            <div className="micro-label mb-1.5">Dataset Provenance Breakdown</div>
            <div className="space-y-1">
              {data.corpus_telemetry.provenance_breakdown.map((p) => (
                <div key={p.label} className="flex justify-between text-[11px]">
                  <span className="font-mono text-slate-600">{p.label}</span>
                  <span className="font-mono text-slate-800 tabular-nums">{p.count.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="surface-panel p-4 space-y-3">
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-indigo-700" />
            <h2 className="section-heading">Sentiment Classification Definitions</h2>
          </div>
          <div className="space-y-2.5 text-xs">
            {Object.entries(data.classification_definitions).map(([k, desc]) => (
              <div key={k} className="rounded border border-slate-200 bg-slate-50/70 p-2.5">
                <span className="font-semibold capitalize text-slate-900">{k}</span>
                <p className="mt-0.5 text-[11px] leading-relaxed text-slate-600">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 10-Stage Pipeline Grid */}
      <div className="surface-panel p-4">
        <h2 className="section-heading mb-3">10-Stage Intelligence Pipeline Architecture</h2>
        <div className="grid grid-cols-1 gap-2.5 md:grid-cols-2 lg:grid-cols-5">
          {PIPELINE_STAGES.map(([stage, desc]) => (
            <div key={stage} className="rounded border border-slate-200 bg-slate-50/50 p-3">
              <div className="text-[11px] font-semibold text-indigo-800">{stage}</div>
              <p className="mt-1 text-[11px] leading-snug text-slate-600">{desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Model, Sampling & Bias Limitations */}
      <div className="surface-panel p-4">
        <div className="flex items-center gap-2 mb-2.5">
          <ShieldAlert className="h-4 w-4 text-amber-700" />
          <h2 className="section-heading">Model Limitations, Sampling Caveats & Potential Biases</h2>
        </div>
        <ul className="space-y-2 text-xs text-slate-700">
          {data.limitations.map((item, idx) => (
            <li key={idx} className="flex items-start gap-2 rounded border border-slate-100 bg-slate-50/60 px-3 py-2">
              <span className="font-mono text-[11px] font-semibold text-slate-400">0{idx + 1}</span>
              <span className="leading-relaxed">{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
