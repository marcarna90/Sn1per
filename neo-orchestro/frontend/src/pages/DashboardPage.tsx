import { Link } from "react-router-dom";
import type { ScanStatus } from "../api/types";
import { useAuditLogs, useHealth, useScans, useScopeEntries } from "../api/hooks";
import { useCurrentUser } from "../auth/context";
import { PageHeader } from "../components/Layout";
import { StatusBadge } from "../components/Badges";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { ui } from "../components/ui";
import { formatDateTime, OUTCOME_LABEL, STATUS_LABEL } from "../lib/format";
import { atLeast } from "../lib/roles";
import { useDocumentTitle } from "../lib/useDocumentTitle";

const ORDER: ScanStatus[] = ["pending", "running", "succeeded", "failed", "cancelled"];

function Card({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className={`${ui.card} space-y-2`}>
      <h2 id={id} className={ui.h2}>
        {title}
      </h2>
      {children}
    </section>
  );
}

export function DashboardPage() {
  useDocumentTitle("Tableau de bord");
  const user = useCurrentUser();
  const isAdmin = atLeast(user.role, "admin");
  const health = useHealth();
  const scans = useScans({ limit: 200 });
  const entries = useScopeEntries();
  const audit = useAuditLogs({ offset: 0, limit: 5, enabled: isAdmin });

  const counts = new Map<ScanStatus, number>();
  for (const scan of scans.data ?? []) counts.set(scan.status, (counts.get(scan.status) ?? 0) + 1);

  return (
    <>
      <PageHeader title="Tableau de bord" />
      <div className="grid gap-4 md:grid-cols-3">
        <Card id="card-api" title="État de l'API">
          {health.isPending ? (
            <LoadingState />
          ) : health.isError ? (
            <p className="font-semibold text-red-800 dark:text-red-300">Injoignable</p>
          ) : (
            <p
              className={`font-semibold ${health.data.status === "ok" ? "text-green-800 dark:text-green-300" : "text-red-800 dark:text-red-300"}`}
            >
              {health.data.status === "ok" ? "Opérationnelle" : "Dégradée"}
            </p>
          )}
        </Card>
        <Card id="card-scans" title="Scans">
          {scans.isPending ? (
            <LoadingState />
          ) : scans.isError ? (
            <p>Indisponible</p>
          ) : (
            <>
              <p className="text-3xl font-bold">{scans.data.length}</p>
              <ul className="text-sm">
                {ORDER.filter((status) => counts.has(status)).map((status) => (
                  <li key={status}>{`${STATUS_LABEL[status]} : ${String(counts.get(status))}`}</li>
                ))}
              </ul>
            </>
          )}
        </Card>
        <Card id="card-scope" title="Autorisations de périmètre">
          {entries.isPending ? (
            <LoadingState />
          ) : entries.isError ? (
            <p>Indisponible</p>
          ) : (
            <>
              <p className="text-3xl font-bold">{entries.data.length}</p>
              <Link to="/scope" className={ui.link}>
                Gérer le périmètre
              </Link>
            </>
          )}
        </Card>
      </div>

      <section aria-labelledby="recent-scans" className="space-y-2">
        <h2 id="recent-scans" className={ui.h2}>
          Scans récents
        </h2>
        {scans.isPending ? (
          <LoadingState />
        ) : scans.isError ? (
          <ErrorState error={scans.error} onRetry={() => void scans.refetch()} />
        ) : scans.data.length === 0 ? (
          <EmptyState>Aucun scan pour le moment.</EmptyState>
        ) : (
          <ul className={`${ui.card} divide-y divide-slate-200 dark:divide-slate-700`}>
            {scans.data.slice(0, 5).map((scan) => (
              <li key={scan.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <Link to={`/scans/${scan.id}`} className={ui.link}>
                  {scan.target}
                </Link>
                <span className="flex items-center gap-3 text-sm">
                  <StatusBadge status={scan.status} />
                  <span>{formatDateTime(scan.created_at)}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {isAdmin ? (
        <section aria-labelledby="recent-activity" className="space-y-2">
          <h2 id="recent-activity" className={ui.h2}>
            Activité récente
          </h2>
          {audit.isPending ? (
            <LoadingState />
          ) : audit.isError ? (
            <ErrorState error={audit.error} onRetry={() => void audit.refetch()} />
          ) : audit.data.length === 0 ? (
            <EmptyState>Aucun événement.</EmptyState>
          ) : (
            <ul className={`${ui.card} divide-y divide-slate-200 dark:divide-slate-700`}>
              {audit.data.map((event) => (
                <li key={event.id} className="flex flex-wrap justify-between gap-2 py-2 text-sm">
                  <span>{event.action}</span>
                  <span>
                    {OUTCOME_LABEL[event.outcome]} · {formatDateTime(event.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}
    </>
  );
}
