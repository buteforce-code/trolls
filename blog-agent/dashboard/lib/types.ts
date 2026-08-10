/** Shapes the dashboard reads. Mirrors the Supabase tables `run.py` writes. */

export interface Topic {
  id: string
  slug: string
  title: string
  status: string
  tags: string[] | null
  created_at: string
  updated_at: string
  scheduled_for?: string | null
  brief?: string | null
  target_keyword?: string | null
  content_format?: string | null
  source_kind?: string | null
  source_detail?: Record<string, unknown> | null
  source_run_id?: string | null
}

export interface BlogPost {
  id: string
  topic_id: string
  research_json?: string | null
  mdx_draft?: string | null
  mdx_final?: string | null
  meta_title?: string | null
  meta_description?: string | null
  published_url?: string | null
  published_at?: string | null
  word_count?: number | null
  rejection_log?: unknown[] | null
  hero_image_url?: string | null
  last_error?: string | null
  schema_json?: unknown
  social_json?: unknown
  audit_json?: unknown
  updated_at?: string | null
}

export interface AutopilotState {
  enabled: boolean
  gapHours: number
  scheduled: { slug: string; title: string; scheduled_for: string }[]
  nextPublishAt?: string | null
  error?: string
}

export interface AgentRun {
  id: string
  topic_slug: string | null
  topic_id: string | null
  trigger: string | null
  status: string
  started_at: string
  finished_at: string | null
  duration_ms: number | null
  total_input_tokens: number | null
  total_output_tokens: number | null
  total_cost_usd: number | string | null
  agent_count: number | null
  error: string | null
}

export interface AgentEvent {
  id: number
  run_id: string
  seq: number
  agent: string | null
  kind: string
  detail: Record<string, unknown> | null
  input_tokens: number | null
  output_tokens: number | null
  cost_usd: number | string | null
  duration_ms: number | null
  at: string
}
