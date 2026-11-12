import type { ScanStatus, Severity } from "../api/types";
import { SEVERITY_LABEL, STATUS_LABEL } from "../lib/format";

// Text colours are chosen for >= 4.5:1 contrast on their background in both themes. Status is
// always conveyed by the label too, never by colour alone.
const STATUS_STYLE: Record<ScanStatus, string> = {
  pending: "bg-slate-200 text-slate-900 dark:bg-slate-600 dark:text-slate-50",
  running: "bg-blue-100 text-blue-900 dark:bg-blue-900 dark:text-blue-50",
  succeeded: "bg-green-100 text-green-900 dark:bg-green-900 dark:text-green-50",
  failed: "bg-red-100 text-red-900 dark:bg-red-900 dark:text-red-50",
  cancelled: "bg-amber-100 text-amber-900 dark:bg-amber-900 dark:text-amber-50",
};

const SEVERITY_STYLE: Record<Severity, string> = {
  info: "bg-slate-200 text-slate-900 dark:bg-slate-600 dark:text-slate-50",
  low: "bg-yellow-100 text-yellow-900 dark:bg-yellow-900 dark:text-yellow-50",
  medium: "bg-orange-100 text-orange-900 dark:bg-orange-900 dark:text-orange-50",
  high: "bg-red-100 text-red-900 dark:bg-red-900 dark:text-red-50",
  critical: "bg-red-800 text-white dark:bg-red-950 dark:text-red-50",
};

const BASE = "inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold";

export const StatusBadge = ({ status }: { status: ScanStatus }) => (
  <span className={`${BASE} ${STATUS_STYLE[status]}`}>{STATUS_LABEL[status]}</span>
);

export const SeverityBadge = ({ severity }: { severity: Severity }) => (
  <span className={`${BASE} ${SEVERITY_STYLE[severity]}`}>{SEVERITY_LABEL[severity]}</span>
);
