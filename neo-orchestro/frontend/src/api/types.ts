/** Mirrors the backend schemas (neo_orchestro/api/schemas.py). */

export type Role = "viewer" | "analyst" | "admin";
export type ScanStatus = "pending" | "running" | "succeeded" | "failed" | "cancelled";
export type Severity = "info" | "low" | "medium" | "high" | "critical";
export type FindingCategory =
  "asset" | "dns_record" | "open_port" | "service" | "vulnerability" | "misconfiguration" | "info";
export type ScopeKind = "domain" | "ip" | "cidr";
export type NetworkClass = "external" | "internal";
export type AuditOutcome = "success" | "denied" | "failure";

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface User {
  id: string;
  org_id: string;
  email: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface ScopeEntry {
  id: string;
  kind: ScopeKind;
  value: string;
  include_subdomains: boolean;
  network_class: NetworkClass;
  description: string | null;
  created_at: string;
}

export interface ScopeDecision {
  allowed: boolean;
  reason: string | null;
  target: string | null;
  pinned_ips: string[];
  matched_rule_ids: string[];
  details: Record<string, string>;
}

export interface Scan {
  id: string;
  engine: string;
  target: string;
  params: Record<string, unknown>;
  status: ScanStatus;
  error_code: string | null;
  error_message: string | null;
  scope_decision: ScopeDecision | null;
  requested_by_id: string | null;
  attempts: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  cancel_requested_at: string | null;
}

export interface Finding {
  id: string;
  scan_id: string;
  category: FindingCategory;
  severity: Severity;
  title: string;
  asset: string;
  description: string | null;
  evidence: Record<string, unknown>;
  source_engine: string;
  created_at: string;
}

export interface Engine {
  name: string;
  description: string;
  target_kinds: ScopeKind[];
}

export interface AuditLog {
  id: number;
  org_id: string | null;
  actor_user_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  outcome: AuditOutcome;
  ip: string | null;
  request_id: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

export interface Meta {
  name: string;
  version: string;
  signature: string;
}

export interface Health {
  status: "ok" | "degraded";
  checks: Record<string, "ok" | "fail">;
}
