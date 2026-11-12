import { useEffect, useState } from "react";
import { useAuditLogs } from "../api/hooks";
import { PageHeader } from "../components/Layout";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { ui } from "../components/ui";
import { formatDateTime, OUTCOME_LABEL } from "../lib/format";
import { useDocumentTitle } from "../lib/useDocumentTitle";

const PAGE_SIZE = 25;

export function AuditPage() {
  useDocumentTitle("Journal d'audit");
  const [filter, setFilter] = useState("");
  const [action, setAction] = useState("");
  const [offset, setOffset] = useState(0);

  // Debounce the filter so typing does not fire one request per keystroke.
  useEffect(() => {
    const id = setTimeout(() => {
      setAction(filter.trim());
      setOffset(0);
    }, 250);
    return () => clearTimeout(id);
  }, [filter]);

  const logs = useAuditLogs({ action: action || undefined, offset, limit: PAGE_SIZE });

  return (
    <>
      <PageHeader title="Journal d'audit">
        <p className={ui.hint}>
          Historique en ajout seul : aucune entrée ne peut être modifiée ni supprimée.
        </p>
      </PageHeader>
      <div className="max-w-sm">
        <label htmlFor="audit-filter" className={ui.label}>
          Filtrer par action
        </label>
        <input
          id="audit-filter"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          autoComplete="off"
          spellCheck={false}
          placeholder="scan.create"
          className={ui.input}
        />
      </div>

      {logs.isPending ? (
        <LoadingState />
      ) : logs.isError ? (
        <ErrorState error={logs.error} onRetry={() => void logs.refetch()} />
      ) : logs.data.length === 0 ? (
        <EmptyState>Aucun événement.</EmptyState>
      ) : (
        <div className={ui.tableWrap}>
          <table className={ui.table}>
            <caption className="sr-only">Événements d&apos;audit</caption>
            <thead>
              <tr>
                <th scope="col" className={ui.th}>
                  Date
                </th>
                <th scope="col" className={ui.th}>
                  Action
                </th>
                <th scope="col" className={ui.th}>
                  Résultat
                </th>
                <th scope="col" className={ui.th}>
                  Acteur
                </th>
                <th scope="col" className={ui.th}>
                  IP
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
              {logs.data.map((event) => (
                <tr key={event.id}>
                  <td className={ui.td}>{formatDateTime(event.created_at)}</td>
                  <td className={`${ui.td} font-mono`}>{event.action}</td>
                  <td className={ui.td}>{OUTCOME_LABEL[event.outcome]}</td>
                  <td className={`${ui.td} font-mono`}>
                    {event.actor_user_id?.slice(0, 8) ?? "système"}
                  </td>
                  <td className={ui.td}>{event.ip ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex gap-3">
        <button
          type="button"
          className={ui.buttonSecondary}
          disabled={offset === 0}
          onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
        >
          Précédent
        </button>
        <button
          type="button"
          className={ui.buttonSecondary}
          disabled={!logs.data || logs.data.length < PAGE_SIZE}
          onClick={() => setOffset((o) => o + PAGE_SIZE)}
        >
          Suivant
        </button>
      </div>
    </>
  );
}
