import { ApiError } from "../api/errors";
import type { AuditOutcome, NetworkClass, ScanStatus, ScopeKind, Severity } from "../api/types";

const dateTime = new Intl.DateTimeFormat("fr-FR", { dateStyle: "short", timeStyle: "medium" });

export const formatDateTime = (iso: string | null): string =>
  iso ? dateTime.format(new Date(iso)) : "—";

export const STATUS_LABEL: Record<ScanStatus, string> = {
  pending: "En attente",
  running: "En cours",
  succeeded: "Terminé",
  failed: "Échoué",
  cancelled: "Annulé",
};

export const SEVERITY_LABEL: Record<Severity, string> = {
  info: "Info",
  low: "Faible",
  medium: "Moyenne",
  high: "Élevée",
  critical: "Critique",
};

export const KIND_LABEL: Record<ScopeKind, string> = {
  domain: "Domaine",
  ip: "Adresse IP",
  cidr: "Plage CIDR",
};

export const CLASS_LABEL: Record<NetworkClass, string> = {
  external: "Externe",
  internal: "Interne",
};

export const OUTCOME_LABEL: Record<AuditOutcome, string> = {
  success: "Succès",
  denied: "Refusé",
  failure: "Échec",
};

const REASONS: Record<string, string> = {
  not_in_scope: "hors du périmètre autorisé",
  blocked_address: "adresse interdite (boucle locale, lien local, métadonnées cloud…)",
  internal_not_authorised: "adresse interne non autorisée explicitement",
  invalid_target: "cible invalide",
  unresolvable: "nom de domaine introuvable",
  resolution_failed: "résolution DNS impossible",
  too_many_addresses: "trop d'adresses IP résolues",
  scheme_not_allowed: "protocole non autorisé",
  userinfo_not_allowed: "identifiants dans l'URL interdits",
  too_many_redirects: "trop de redirections",
};

/** Plain-language explanation of a scope refusal code. */
export const scopeReasonLabel = (reason: string | null | undefined): string =>
  (reason && REASONS[reason]) || reason || "raison inconnue";

/** The refusal reason carried by a `scope_violation` error, if any. */
export function scopeReasonOf(error: unknown): string | null {
  if (!(error instanceof ApiError) || error.code !== "scope_violation") return null;
  const details = error.details as { reason?: unknown } | null;
  return typeof details?.reason === "string" ? details.reason : null;
}

/** A message safe to show a user (ApiError messages are already sanitised server-side). */
export const errorMessage = (error: unknown): string =>
  error instanceof ApiError ? error.message : "Une erreur inattendue est survenue.";
