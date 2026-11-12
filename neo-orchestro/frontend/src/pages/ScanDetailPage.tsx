import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/errors";
import { useCancelScan, useFindings, useScan } from "../api/hooks";
import type { Scan, Severity } from "../api/types";
import { useCurrentUser } from "../auth/context";
import { SeverityBadge, StatusBadge } from "../components/Badges";
import { PageHeader } from "../components/Layout";
import { EmptyState, ErrorState, FormError, LoadingState } from "../components/States";
import { ui } from "../components/ui";
import { errorMessage, formatDateTime, SEVERITY_LABEL } from "../lib/format";
import { atLeast } from "../lib/roles";
import { useDocumentTitle } from "../lib/useDocumentTitle";

const SEVERITIES = Object.keys(SEVERITY_LABEL) as Severity[];

function Field({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-sm text-slate-600 dark:text-slate-400">{term}</dt>
      <dd className="font-medium">{children}</dd>
    </div>
  );
}

function Findings({ scan }: { scan: Scan }) {
  const [severity, setSeverity] = useState<Severity | "">("");
  const active = scan.status === "pending" || scan.status === "running";
  const findings = useFindings(scan.id, severity || undefined, active);

  return (
    <section aria-labelledby="findings" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 id="findings" className={ui.h2}>
          Résultats
        </h2>
        <div>
          <label htmlFor="severity-filter" className={ui.label}>
            Gravité
          </label>
          <select
            id="severity-filter"
            value={severity}
            onChange={(event) => setSeverity(event.target.value as Severity | "")}
            className={ui.input}
          >
            <option value="">Toutes</option>
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>
                {SEVERITY_LABEL[s]}
              </option>
            ))}
          </select>
        </div>
      </div>
      {findings.isPending ? (
        <LoadingState />
      ) : findings.isError ? (
        <ErrorState error={findings.error} onRetry={() => void findings.refetch()} />
      ) : findings.data.length === 0 ? (
        <EmptyState>Aucun résultat pour le moment.</EmptyState>
      ) : (
        <div className={ui.tableWrap}>
          <table className={ui.table}>
            <caption className="sr-only">Résultats du scan</caption>
            <thead>
              <tr>
                <th scope="col" className={ui.th}>
                  Gravité
                </th>
                <th scope="col" className={ui.th}>
                  Titre
                </th>
                <th scope="col" className={ui.th}>
                  Actif
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
              {findings.data.map((finding) => (
                <tr key={finding.id}>
                  <td className={ui.td}>
                    <SeverityBadge severity={finding.severity} />
                  </td>
                  <td className={ui.td}>
                    <p className="font-medium">{finding.title}</p>
                    {finding.description ? (
                      <p className="text-slate-600 dark:text-slate-400">{finding.description}</p>
                    ) : null}
                  </td>
                  <td className={ui.td}>{finding.asset}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function ScanDetailPage() {
  const { scanId = "" } = useParams();
  const user = useCurrentUser();
  const scan = useScan(scanId);
  const cancel = useCancelScan(scanId);
  useDocumentTitle(scan.data?.target ?? "Scan");

  if (scan.isPending) return <LoadingState />;
  if (scan.isError) {
    if (scan.error instanceof ApiError && scan.error.status === 404) {
      return (
        <div className="space-y-3">
          <h1 className={ui.h1}>Scan introuvable</h1>
          <Link to="/scans" className={ui.link}>
            Retour aux scans
          </Link>
        </div>
      );
    }
    return <ErrorState error={scan.error} onRetry={() => void scan.refetch()} />;
  }

  const data = scan.data;
  const cancellable =
    atLeast(user.role, "analyst") && (data.status === "pending" || data.status === "running");

  return (
    <>
      <PageHeader title={data.target}>
        <p>
          <Link to="/scans" className={ui.link}>
            ← Tous les scans
          </Link>
        </p>
      </PageHeader>
      <div className={`${ui.card} space-y-4`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <StatusBadge status={data.status} />
          {cancellable ? (
            <button
              type="button"
              onClick={() => cancel.mutate()}
              disabled={cancel.isPending}
              className={ui.buttonDanger}
            >
              Annuler le scan
            </button>
          ) : null}
        </div>
        {cancel.isError ? <FormError>{errorMessage(cancel.error)}</FormError> : null}
        {data.error_message ? (
          <div
            role="alert"
            className="rounded-md border border-red-700 bg-red-50 px-3 py-2 text-sm text-red-900 dark:bg-red-950 dark:text-red-100"
          >
            <p className="font-semibold">Erreur : {data.error_message}</p>
            {data.error_code ? <p>Code : {data.error_code}</p> : null}
          </div>
        ) : null}
        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field term="Moteur">{data.engine}</Field>
          <Field term="Créé le">{formatDateTime(data.created_at)}</Field>
          <Field term="Démarré le">{formatDateTime(data.started_at)}</Field>
          <Field term="Terminé le">{formatDateTime(data.finished_at)}</Field>
          <Field term="Tentatives">{data.attempts}</Field>
        </dl>
        {data.scope_decision && data.scope_decision.pinned_ips.length > 0 ? (
          <div>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Adresses validées par le contrôle de périmètre
            </p>
            <ul className="font-mono text-sm">
              {data.scope_decision.pinned_ips.map((ip) => (
                <li key={ip}>{ip}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
      <Findings scan={data} />
    </>
  );
}
