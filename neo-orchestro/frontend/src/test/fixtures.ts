import type { AuditLog, Engine, Finding, Role, Scan, ScopeEntry, User } from "../api/types";

let counter = 0;
const id = () => `00000000-0000-4000-8000-${String(++counter).padStart(12, "0")}`;

export const makeUser = (overrides: Partial<User> = {}): User => ({
  id: id(),
  org_id: "11111111-1111-4111-8111-111111111111",
  email: "admin@acme.example.com",
  role: "admin" satisfies Role,
  is_active: true,
  created_at: "2026-11-01T09:00:00Z",
  last_login_at: "2026-11-12T08:30:00Z",
  ...overrides,
});

export const makeScan = (overrides: Partial<Scan> = {}): Scan => ({
  id: id(),
  engine: "dns_recon",
  target: "app.acme.example.com",
  params: { record_types: ["A", "MX"] },
  status: "pending",
  error_code: null,
  error_message: null,
  scope_decision: {
    allowed: true,
    reason: null,
    target: "app.acme.example.com",
    pinned_ips: ["93.184.216.34"],
    matched_rule_ids: ["r1"],
    details: {},
  },
  requested_by_id: null,
  attempts: 0,
  created_at: "2026-11-12T10:00:00Z",
  started_at: null,
  finished_at: null,
  cancel_requested_at: null,
  ...overrides,
});

export const makeFinding = (overrides: Partial<Finding> = {}): Finding => ({
  id: id(),
  scan_id: "scan-1",
  category: "dns_record",
  severity: "info",
  title: "A record",
  asset: "app.acme.example.com",
  description: "app.acme.example.com has a A record: 93.184.216.34",
  evidence: { type: "A", value: "93.184.216.34" },
  source_engine: "dns_recon",
  created_at: "2026-11-12T10:01:00Z",
  ...overrides,
});

export const makeEntry = (overrides: Partial<ScopeEntry> = {}): ScopeEntry => ({
  id: id(),
  kind: "domain",
  value: "acme.example.com",
  include_subdomains: true,
  network_class: "external",
  description: "Production",
  created_at: "2026-11-02T09:00:00Z",
  ...overrides,
});

export const makeAudit = (overrides: Partial<AuditLog> = {}): AuditLog => ({
  id: 1,
  org_id: "11111111-1111-4111-8111-111111111111",
  actor_user_id: "22222222-2222-4222-8222-222222222222",
  action: "auth.login",
  resource_type: null,
  resource_id: null,
  outcome: "success",
  ip: "203.0.113.7",
  request_id: "req-1",
  details: {},
  created_at: "2026-11-12T10:00:00Z",
  ...overrides,
});

export const DNS_ENGINE: Engine = {
  name: "dns_recon",
  description: "Enumerate DNS records of a domain and flag a missing SPF policy.",
  target_kinds: ["domain"],
};
