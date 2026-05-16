export type Agent = {
  id: string;
  lineage: string;
  name: string;
  version: number;
  status: string;
  on_chain_token_id?: string | null;
  basescan_url?: string | null;
  rolling_24h_brier?: number | null;
  trades_today?: number;
  open_positions?: number;
  trade_floor?: number;
  unrealized_pnl_usd?: number | null;
  latest_forecast?: {
    id: string;
    ticker: string;
    predicted_direction: "long" | "short" | "flat";
    confidence: number;
    will_trade: boolean;
    status: string;
    emitted_at: string;
    brier_score?: number | null;
  } | null;
};

export type MirrorEvent = {
  id?: string;
  agent_id?: string | null;
  kind: string;
  severity?: string;
  payload?: Record<string, unknown>;
  created_at?: string;
};

export type Forecast = {
  id: string;
  agent_id: string;
  ticker: string;
  predicted_direction: "long" | "short" | "flat";
  confidence: number;
  probability_up: number;
  will_trade: boolean;
  status: string;
  emitted_at: string;
  resolves_at: string;
  brier_score?: number | null;
};

export type CalibrationBucket = {
  lower: number;
  upper: number;
  count: number;
  predicted_avg: number | null;
  realized_frequency: number | null;
};

export type BlueFinding = {
  id: string;
  agent_id: string;
  sample_size: number;
  predicted_confidence_avg: number;
  realized_accuracy: number;
  brier_gap: number;
  suggested_failure_mode: string;
  suggested_fix_direction: string;
  status: string;
  created_at: string;
};

export type OnchainJob = {
  id: string;
  job_type: string;
  agent_id?: string | null;
  status: string;
  attempt_count: number;
  last_error?: string | null;
  tx_hash?: string | null;
};

export type PatchRecord = {
  id: string;
  source_agent_id?: string | null;
  target_agent_id: string;
  blue_finding_id?: string | null;
  patch_type: string;
  proposed_patch_json: Record<string, unknown>;
  holdout_pre_brier?: number | null;
  holdout_post_brier?: number | null;
  holdout_pre_trade_rate?: number | null;
  holdout_post_trade_rate?: number | null;
  brier_improvement_pct?: number | null;
  trade_rate_preservation_pct?: number | null;
  status: string;
  gate_passed?: boolean | null;
  rejection_reason?: string | null;
  applied_agent_id?: string | null;
  created_at: string;
};

export type LineageNode = {
  id: string;
  lineage: string;
  version: number;
  token_id?: string | null;
};

export type LineageEdge = {
  source: string;
  target: string;
  type: "vertical" | "crossover";
};

export type LineageGraph = {
  nodes: LineageNode[];
  edges: LineageEdge[];
};
