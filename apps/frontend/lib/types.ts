export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export interface CaseOut {
  id: string;
  owner_id: string;
  name: string;
  description: string;
  status: string;
  tags: string[];
  evidence_count: number;
  created_at: string;
  updated_at: string;
}

export interface EvidenceOut {
  id: string;
  evidence_id: string;
  item_type: string;
  title: string;
  description: string;
  status: string;
  extracted: boolean;
  provider_label: string;
  created_at: string;
}

export interface TimelineEventOut {
  event_id: string;
  title: string;
  description: string;
  time_type: string;
  time_start: string;
  time_end: string;
  time_label: string;
  certainty: string;
  ordering_index: number;
  linked_fact_ids: string[];
  source_evidence_ids: string[];
}

export interface ConflictOut {
  conflict_id: string;
  subject: string;
  description: string;
  status: string;
  sides: { claim: string; evidence_ids: string[] }[];
}

export interface AnchorOut {
  anchor_id: string;
  type: string;
  value: Record<string, unknown>;
  normalized: string;
  source_evidence_ids: string[];
  strength: string;
}

export interface FactOut {
  fact_id: string;
  statement: string;
  status: string;
  category: string;
  qualifier: string;
  constraint_strength: string;
  source_type: string;
  is_authoritative: boolean;
  source_evidence_ids: string[];
  extra: Record<string, unknown>;
}

export interface ScenarioOut {
  id: string;
  hypothesis_id: string;
  hypothesis_label: string;
  status: string;
  is_survivor: boolean;
  summary: string;
  cause_claim: string;
  participants: string[];
  rejection_reason: string;
  final_verdict: string;
  iteration_count: number;
  score_total: number;
  score_breakdown: Record<string, unknown>;
  unknown_count: number;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  created_at: string;
}

export interface ScenarioDetail extends ScenarioOut {
  case_id: string;
  known: string[];
  inferred: string[];
  unknown: string[];
  anchors_satisfied: string[];
  events: ScenarioEventOut[];
  similar_cases: SimilarCaseOut[];
  discriminating: DiscriminatingEvidenceOut[];
  video: VideoOut | null;
  audit: AuditEventOut[];
}

export interface ScenarioEventOut {
  id: string;
  scenario_id: string;
  event_order: number;
  description: string;
  event_type: string;
  linked_fact_ids: string[];
  evidence_links: string[];
  timing: Record<string, string>;
  location: string;
}

export interface SimilarCaseOut {
  reference_label: string;
  title: string;
  similarity: number;
  relevant_patterns: string[];
}

export interface DiscriminatingEvidenceOut {
  pair: string[];
  shared: string[];
  differing: string[];
  needed: string[];
  note: string;
}

export interface VideoOut {
  id: string;
  status: string;
  provider: string;
  is_mock: boolean;
  duration_seconds: number;
  width: number;
  height: number;
  label_text: string;
  validation: Record<string, unknown>;
  error: string;
  stream_url?: string;
}

export interface VideoSpecOut {
  id: string;
  scenario_id: string;
  case_id: string;
  status: string;
  spec: Record<string, unknown>;
  visual_prompt: string;
  shots: VideoShotOut[];
}

export interface VideoShotOut {
  shot_index: number;
  duration_seconds: number;
  description: string;
  status: string;
}

export interface AuditEventOut {
  id: string;
  action: string;
  agent: string;
  provider: string;
  summary: string;
  timestamp: string;
  input_object_ids: string[];
  output_object_id: string;
  extra: Record<string, unknown>;
}

export interface AnalysisStatus {
  case_id: string;
  status: string;
  progress: number;
  job_id: string;
  error: string;
  result: Record<string, unknown>;
}

export interface CaseDashboard {
  case: CaseOut;
  evidence_count: number;
  analysis_status: string;
  fact_count: number;
  timeline_count: number;
  constraint_count: number;
  hard_constraint_count: number;
  conflict_count: number;
  unknown_area_count: number;
  anchor_count: number;
  scenario_survivor_count: number;
  scenario_rejected_count: number;
  top_scenarios: ScenarioOut[];
  similar_case_count: number;
  video_count: number;
}

export interface ProviderStatus {
  llm: { provider: string; is_mock: boolean; label?: string };
  embeddings: { provider: string; is_mock: boolean };
  speech_to_text: { provider: string; is_mock: boolean };
  vision: { provider: string; is_mock: boolean };
  video_understanding: { provider: string; is_mock: boolean };
  video_generation: { provider: string; is_mock: boolean };
}
