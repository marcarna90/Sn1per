import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { useAuth } from "../auth/context";
import type {
  AuditLog,
  Engine,
  Finding,
  Health,
  Meta,
  Role,
  Scan,
  ScanStatus,
  ScopeDecision,
  ScopeEntry,
  ScopeKind,
  Severity,
  User,
} from "./types";

const ACTIVE: readonly ScanStatus[] = ["pending", "running"];
const POLL_MS = 3000;

export const useApi = () => useAuth().client;

// ------------------------------------------------------------------ platform

export function useHealth(): UseQueryResult<Health> {
  const api = useApi();
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api.health(),
    refetchInterval: 30_000,
  });
}

export function useMeta(): UseQueryResult<Meta> {
  const api = useApi();
  return useQuery({ queryKey: ["meta"], queryFn: () => api.get<Meta>("/api/v1/meta") });
}

// ------------------------------------------------------------------ scans

export function useEngines(enabled = true): UseQueryResult<Engine[]> {
  const api = useApi();
  return useQuery({
    queryKey: ["engines"],
    queryFn: () => api.get<Engine[]>("/api/v1/engines"),
    enabled,
  });
}

export function useScans(params: { status?: ScanStatus | undefined; limit?: number }) {
  const api = useApi();
  return useQuery({
    queryKey: ["scans", params],
    queryFn: () =>
      api.get<Scan[]>("/api/v1/scans", { status: params.status, limit: params.limit ?? 50 }),
  });
}

export function useScan(id: string) {
  const api = useApi();
  return useQuery({
    queryKey: ["scan", id],
    queryFn: () => api.get<Scan>(`/api/v1/scans/${id}`),
    // Follow a scan while it is queued or running.
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ACTIVE.includes(status) ? POLL_MS : false;
    },
  });
}

export function useFindings(id: string, severity: Severity | undefined, polling: boolean) {
  const api = useApi();
  return useQuery({
    queryKey: ["findings", id, severity ?? "all"],
    queryFn: () => api.get<Finding[]>(`/api/v1/scans/${id}/findings`, { severity, limit: 200 }),
    refetchInterval: polling ? POLL_MS : false,
  });
}

export interface NewScan {
  engine: string;
  target: string;
  params: Record<string, unknown>;
}

export function useCreateScan() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (scan: NewScan) => api.post<Scan>("/api/v1/scans", scan),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scans"] }),
  });
}

export function useCancelScan(id: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<Scan>(`/api/v1/scans/${id}/cancel`),
    onSuccess: (scan) => {
      queryClient.setQueryData(["scan", id], scan);
      return queryClient.invalidateQueries({ queryKey: ["scans"] });
    },
  });
}

// ------------------------------------------------------------------ scope

export function useScopeEntries() {
  const api = useApi();
  return useQuery({
    queryKey: ["scope"],
    queryFn: () => api.get<ScopeEntry[]>("/api/v1/scope/entries"),
  });
}

export interface NewScopeEntry {
  kind: ScopeKind;
  value: string;
  include_subdomains: boolean;
  description?: string | undefined;
}

export function useAddScopeEntry() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (entry: NewScopeEntry) => api.post<ScopeEntry>("/api/v1/scope/entries", entry),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scope"] }),
  });
}

export function useDeleteScopeEntry() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/scope/entries/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scope"] }),
  });
}

export function useScopeCheck() {
  const api = useApi();
  return useMutation({
    mutationFn: (target: string) => api.post<ScopeDecision>("/api/v1/scope/check", { target }),
  });
}

// ------------------------------------------------------------------ users & audit

export function useUsers() {
  const api = useApi();
  return useQuery({ queryKey: ["users"], queryFn: () => api.get<User[]>("/api/v1/users") });
}

export function useCreateUser() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (user: { email: string; password: string; role: Role }) =>
      api.post<User>("/api/v1/users", user),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });
}

export function useUpdateUser() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...changes }: { id: string; role?: Role; is_active?: boolean }) =>
      api.patch<User>(`/api/v1/users/${id}`, changes),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });
}

export function useAuditLogs(params: {
  action?: string;
  offset: number;
  limit: number;
  enabled?: boolean;
}) {
  const api = useApi();
  const { enabled = true, ...query } = params;
  return useQuery({
    queryKey: ["audit", query],
    queryFn: () => api.get<AuditLog[]>("/api/v1/audit-logs", query),
    enabled,
  });
}

export function useChangePassword() {
  const api = useApi();
  return useMutation({
    mutationFn: (body: { old_password: string; new_password: string }) =>
      api.post<undefined>("/api/v1/auth/change-password", body),
  });
}
