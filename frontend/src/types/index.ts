export interface User {
  id: number;
  email: string;
  full_name: string;
  role: "admin" | "senior_analyst" | "analyst" | "viewer";
  department: string;
  is_active: boolean;
  created_at: string;
  last_login_at?: string | null;
}

export interface MonitoringTopic {
  id: number;
  name: string;
  slug: string;
  description: string;
  category: string;
  keywords: string[];
  excluded_keywords: string[];
  data_source_ids: number[];
  time_range_days: number;
  language: string;
  status: "active" | "paused" | "archived";
  created_at: string;
  updated_at: string;
  record_count?: number;
  recent_24h_count?: number;
  avg_sentiment?: number;
  has_emerging_trend?: boolean;
}

export interface DataSource {
  id: number;
  name: string;
  slug: string;
  provider_type: "csv" | "rss" | "public_api" | "synthetic_stream";
  description: string;
  config: Record<string, unknown>;
  is_synthetic: boolean;
  is_enabled: boolean;
  schedule_interval_minutes: number;
  rate_limit_per_min: number;
  last_cursor?: string | null;
  last_ingested_at?: string | null;
  health_status: "healthy" | "degraded" | "error" | "idle";
  total_records_ingested: number;
  error_count_24h: number;
  created_at: string;
}

export interface IngestionJob {
  id: number;
  source_id: number;
  source_name: string;
  provider_type: string;
  monitoring_topic_id?: number | null;
  job_type: string;
  status: "queued" | "running" | "completed" | "partial" | "failed";
  records_fetched: number;
  records_inserted: number;
  records_duplicated: number;
  records_failed: number;
  retry_count: number;
  cursor_before?: string | null;
  cursor_after?: string | null;
  error_log: Array<{ timestamp?: string; level?: string; code?: string; message?: string }>;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
}

export interface SentimentBreakdown {
  positive: number;
  neutral: number;
  mixed: number;
  negative: number;
}

export interface ClusterItem {
  id: number;
  monitoring_topic_id?: number | null;
  topic_name: string;
  cluster_label: string;
  summary: string;
  top_keywords: string[];
  record_count: number;
  recent_24h_count: number;
  baseline_daily_avg: number;
  avg_sentiment_score: number;
  sentiment_breakdown: SentimentBreakdown;
  coherence_score: number;
  trend_velocity: number;
  growth_pct: number;
  is_emerging: boolean;
  embedding_backend?: string;
  representative_record_ids: number[];
}

export interface RecordListItem {
  id: number;
  raw_record_id: number;
  external_id: string;
  source_id: number;
  source_name: string;
  provider_type: string;
  is_synthetic: boolean;
  provenance_label: string;
  has_missing_fields: boolean;
  published_at: string;
  original_title?: string | null;
  original_text: string;
  normalized_text: string;
  detected_language: string;
  language_confidence: number;
  is_duplicate: boolean;
  duplicate_of_id?: number | null;
  processing_status: "pending" | "processed" | "needs_review" | "failed";
  entities: Array<{ text: string; type: string }>;
  extracted_keywords: string[];
  predicted_topic: string;
  effective_topic: string;
  monitoring_topic_id?: number | null;
  topic_confidence: number;
  topic_overridden: boolean;
  predicted_sentiment: "positive" | "neutral" | "mixed" | "negative";
  effective_sentiment: "positive" | "neutral" | "mixed" | "negative";
  sentiment_score: number;
  sentiment_confidence: number;
  sentiment_overridden: boolean;
  is_bookmarked: boolean;
  is_verified: boolean;
  analyst_note: string;
  report_section_tag?: string | null;
}

export interface RecordDetail {
  id: number;
  raw: {
    id: number;
    external_id: string;
    source_id: number;
    source_name: string;
    provider_type: string;
    source_url?: string | null;
    author_handle_anonymized?: string | null;
    original_title?: string | null;
    original_text: string;
    raw_metadata: Record<string, unknown>;
    published_at: string;
    ingested_at: string;
    content_hash: string;
    is_synthetic: boolean;
    provenance_label: string;
    has_missing_fields: boolean;
  };
  processed: {
    normalized_text: string;
    detected_language: string;
    language_confidence: number;
    is_duplicate: boolean;
    duplicate_of_id?: number | null;
    similarity_score?: number | null;
    entities: Array<{ text: string; type: string }>;
    extracted_keywords: string[];
    processing_status: string;
    processing_version: string;
    processed_at: string;
  };
  topic_classification: {
    monitoring_topic_id?: number | null;
    predicted_topic: string;
    effective_topic: string;
    topic_category: string;
    confidence: number;
    class_probabilities: Record<string, number>;
    model_name: string;
    model_version: string;
    is_overridden: boolean;
    overridden_topic?: string | null;
    overridden_by_name?: string | null;
    overridden_at?: string | null;
    override_reason?: string | null;
  };
  sentiment_classification: {
    predicted_sentiment: string;
    effective_sentiment: string;
    sentiment_score: number;
    confidence: number;
    class_probabilities: Record<string, number>;
    model_name: string;
    model_version: string;
    is_overridden: boolean;
    overridden_sentiment?: string | null;
    overridden_by_name?: string | null;
    overridden_at?: string | null;
    override_reason?: string | null;
  };
  annotations: Array<{
    id: number;
    analyst_id: number;
    analyst_name: string;
    is_bookmarked: boolean;
    is_verified: boolean;
    note: string;
    tags: string[];
    report_section_tag?: string | null;
    updated_at: string;
  }>;
}

export interface LiveEventRecord {
  type: string;
  processed_record_id: number;
  raw_record_id: number;
  external_id: string;
  source_id: number;
  source_name: string;
  provider_type: string;
  is_synthetic: boolean;
  provenance_label: string;
  published_at: string;
  processed_at: string;
  title?: string | null;
  excerpt: string;
  language: string;
  topic: string;
  monitoring_topic_id?: number | null;
  topic_confidence: number;
  sentiment: "positive" | "neutral" | "mixed" | "negative";
  sentiment_score: number;
  sentiment_confidence: number;
  is_duplicate: boolean;
  processing_status: string;
}

export interface CivicEvent {
  id: number;
  title: string;
  description: string;
  event_type: string;
  location: string;
  start_time: string;
  end_time: string;
  baseline_days: number;
  monitoring_topic_ids: number[];
  keywords: string[];
  status: string;
  created_at: string;
}

export interface ReportSummary {
  id: number;
  title: string;
  subtitle: string;
  monitoring_topic_id?: number | null;
  event_id?: number | null;
  time_range_start: string;
  time_range_end: string;
  status: "draft" | "reviewed" | "published";
  executive_summary: string;
  key_metrics: Record<string, number>;
  evidence_count: number;
  generated_by_name: string;
  created_at: string;
  updated_at: string;
}

export interface AlertItem {
  id: number;
  severity: "info" | "warning" | "critical";
  category: string;
  title: string;
  message: string;
  resource_type?: string | null;
  resource_id?: string | null;
  is_read: boolean;
  created_at: string;
}
