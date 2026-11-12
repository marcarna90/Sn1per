import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../api/errors";
import { useCreateScan, useEngines, useScans } from "../api/hooks";
import type { ScanStatus } from "../api/types";
import { useCurrentUser } from "../auth/context";
import { StatusBadge } from "../components/Badges";
import { PageHeader } from "../components/Layout";
import { EmptyState, ErrorState, FormError, LoadingState } from "../components/States";
import { ui } from "../components/ui";
import {
  errorMessage,
  formatDateTime,
  scopeReasonLabel,
  scopeReasonOf,
  STATUS_LABEL,
} from "../lib/format";
import { atLeast } from "../lib/roles";
import { useDocumentTitle } from "../lib/useDocumentTitle";

const RECORD_TYPES = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"] as const;
const DEFAULT_TYPES: readonly string[] = ["A", "AAAA", "MX", "NS", "TXT"];
const STATUSES = Object.keys(STATUS_LABEL) as ScanStatus[];

function creationError(error: unknown): string {
  const reason = scopeReasonOf(error);
  if (reason) return `Cible refusée : ${scopeReasonLabel(reason)}.`;
  if (error instanceof ApiError && error.status === 503) {
    return "La file de tâches est indisponible. Réessayez dans un instant.";
  }
  return errorMessage(error);
}

function NewScanForm() {
  const navigate = useNavigate();
  const engines = useEngines();
  const createScan = useCreateScan();
  const [engine, setEngine] = useState("");
  const [target, setTarget] = useState("");
  const [types, setTypes] = useState<readonly string[]>(DEFAULT_TYPES);
  const [error, setError] = useState<string | null>(null);

  if (engines.isPending) return <LoadingState />;
  if (engines.isError)
    return <ErrorState error={engines.error} onRetry={() => void engines.refetch()} />;

  const selected = engine || engines.data[0]?.name || "";
  const isDns = selected === "dns_recon";

  function toggle(type: string) {
    setTypes((current) =>
      current.includes(type) ? current.filter((t) => t !== type) : [...current, type],
    );
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const params = isDns ? { record_types: RECORD_TYPES.filter((t) => types.includes(t)) } : {};
    try {
      const scan = await createScan.mutateAsync({
        engine: selected,
        target: target.trim(),
        params,
      });
      void navigate(`/scans/${scan.id}`);
    } catch (caught) {
      setError(creationError(caught));
    }
  }

  return (
    <section aria-labelledby="new-scan" className={`${ui.card} space-y-4`}>
      <h2 id="new-scan" className={ui.h2}>
        Nouveau scan
      </h2>
      <p className={ui.hint}>
        La cible est vérifiée par rapport au périmètre autorisé avant toute exécution.
      </p>
      <form onSubmit={(event) => void onSubmit(event)} className="space-y-4" noValidate>
        {error ? <FormError>{error}</FormError> : null}
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label htmlFor="scan-engine" className={ui.label}>
              Moteur
            </label>
            <select
              id="scan-engine"
              value={selected}
              onChange={(event) => setEngine(event.target.value)}
              className={ui.input}
            >
              {engines.data.map((e) => (
                <option key={e.name} value={e.name}>
                  {e.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="scan-target" className={ui.label}>
              Cible
            </label>
            <input
              id="scan-target"
              value={target}
              onChange={(event) => setTarget(event.target.value)}
              required
              autoComplete="off"
              spellCheck={false}
              placeholder="app.exemple.com"
              className={ui.input}
            />
          </div>
        </div>
        {isDns ? (
          <fieldset className="space-y-2">
            <legend className={ui.label}>Types d&apos;enregistrements</legend>
            <div className="flex flex-wrap gap-4">
              {RECORD_TYPES.map((type) => (
                <label key={type} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={types.includes(type)}
                    onChange={() => toggle(type)}
                  />
                  {type}
                </label>
              ))}
            </div>
          </fieldset>
        ) : null}
        <button type="submit" disabled={createScan.isPending} className={ui.button}>
          Lancer le scan
        </button>
      </form>
    </section>
  );
}

export function ScansPage() {
  useDocumentTitle("Scans");
  const user = useCurrentUser();
  const canCreate = atLeast(user.role, "analyst");
  const [status, setStatus] = useState<ScanStatus | "">("");
  const scans = useScans({ status: status || undefined, limit: 50 });

  return (
    <>
      <PageHeader title="Scans" />
      {canCreate ? (
        <NewScanForm />
      ) : (
        <p className={ui.hint}>Votre rôle (lecteur) ne permet pas de lancer des scans.</p>
      )}

      <section aria-labelledby="history" className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 id="history" className={ui.h2}>
            Historique
          </h2>
          <div>
            <label htmlFor="status-filter" className={ui.label}>
              Statut
            </label>
            <select
              id="status-filter"
              value={status}
              onChange={(event) => setStatus(event.target.value as ScanStatus | "")}
              className={ui.input}
            >
              <option value="">Tous</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABEL[s]}
                </option>
              ))}
            </select>
          </div>
        </div>

        {scans.isPending ? (
          <LoadingState />
        ) : scans.isError ? (
          <ErrorState error={scans.error} onRetry={() => void scans.refetch()} />
        ) : scans.data.length === 0 ? (
          <EmptyState>
            <p>Aucun scan pour le moment.</p>
            {canCreate ? (
              <p className="mt-1 text-sm">Lancez un premier scan avec le formulaire ci-dessus.</p>
            ) : null}
          </EmptyState>
        ) : (
          <div className={ui.tableWrap}>
            <table className={ui.table}>
              <caption className="sr-only">Liste des scans</caption>
              <thead>
                <tr>
                  <th scope="col" className={ui.th}>
                    Cible
                  </th>
                  <th scope="col" className={ui.th}>
                    Moteur
                  </th>
                  <th scope="col" className={ui.th}>
                    Statut
                  </th>
                  <th scope="col" className={ui.th}>
                    Créé le
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                {scans.data.map((scan) => (
                  <tr key={scan.id}>
                    <td className={ui.td}>
                      <Link to={`/scans/${scan.id}`} className={ui.link}>
                        {scan.target}
                      </Link>
                    </td>
                    <td className={ui.td}>{scan.engine}</td>
                    <td className={ui.td}>
                      <StatusBadge status={scan.status} />
                    </td>
                    <td className={ui.td}>{formatDateTime(scan.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
