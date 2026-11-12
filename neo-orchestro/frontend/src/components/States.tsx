import type { ReactNode } from "react";
import { ApiError } from "../api/errors";
import { ui } from "./ui";

export function LoadingState({ label = "Chargement…" }: { label?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-2 p-4 text-slate-700 dark:text-slate-300"
    >
      <span
        aria-hidden="true"
        className="h-4 w-4 animate-spin rounded-full border-2 border-slate-400 border-t-indigo-700"
      />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const detail = error instanceof ApiError ? error.message : "Impossible de charger les données.";
  const requestId = error instanceof ApiError ? error.requestId : null;
  return (
    <div
      role="alert"
      className="rounded-lg border border-red-700 bg-red-50 p-4 text-red-900 dark:bg-red-950 dark:text-red-100"
    >
      <p className="font-semibold">Une erreur est survenue</p>
      <p className="mt-1 text-sm">{detail}</p>
      {requestId ? <p className="mt-1 text-xs">Référence : {requestId}</p> : null}
      {onRetry ? (
        <button type="button" onClick={onRetry} className={`${ui.buttonSecondary} mt-3`}>
          Réessayer
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-400 p-6 text-center text-slate-700 dark:text-slate-300">
      {children}
    </div>
  );
}

/** An inline form error, announced to assistive technology. */
export function FormError({ children }: { children: ReactNode }) {
  return (
    <div
      role="alert"
      className="rounded-md border border-red-700 bg-red-50 px-3 py-2 text-sm text-red-900 dark:bg-red-950 dark:text-red-100"
    >
      {children}
    </div>
  );
}

/** A transient success message, announced politely. */
export function Notice({ children }: { children: ReactNode }) {
  return (
    <div
      role="status"
      aria-label="Notification"
      className="rounded-md border border-green-700 bg-green-50 px-3 py-2 text-sm text-green-900 dark:bg-green-950 dark:text-green-100"
    >
      {children}
    </div>
  );
}
