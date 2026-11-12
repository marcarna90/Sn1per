import { useState, type FormEvent } from "react";
import { ApiError } from "../api/errors";
import {
  useAddScopeEntry,
  useDeleteScopeEntry,
  useScopeCheck,
  useScopeEntries,
} from "../api/hooks";
import type { ScopeKind } from "../api/types";
import { useCurrentUser } from "../auth/context";
import { PageHeader } from "../components/Layout";
import { EmptyState, ErrorState, FormError, LoadingState } from "../components/States";
import { ui } from "../components/ui";
import { CLASS_LABEL, errorMessage, KIND_LABEL, scopeReasonLabel } from "../lib/format";
import { atLeast } from "../lib/roles";
import { useDocumentTitle } from "../lib/useDocumentTitle";

const KINDS = Object.keys(KIND_LABEL) as ScopeKind[];

function AddEntryForm() {
  const add = useAddScopeEntry();
  const [kind, setKind] = useState<ScopeKind>("domain");
  const [value, setValue] = useState("");
  const [subdomains, setSubdomains] = useState(false);
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await add.mutateAsync({
        kind,
        value: value.trim(),
        include_subdomains: kind === "domain" && subdomains,
        description: description.trim() || undefined,
      });
      setValue("");
      setDescription("");
    } catch (caught) {
      setError(
        caught instanceof ApiError && caught.status === 409
          ? "Cette autorisation existe déjà."
          : errorMessage(caught),
      );
    }
  }

  return (
    <section aria-labelledby="add-entry" className={`${ui.card} space-y-4`}>
      <h2 id="add-entry" className={ui.h2}>
        Ajouter une autorisation
      </h2>
      <form onSubmit={(event) => void onSubmit(event)} className="space-y-4" noValidate>
        {error ? <FormError>{error}</FormError> : null}
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label htmlFor="entry-kind" className={ui.label}>
              Type
            </label>
            <select
              id="entry-kind"
              value={kind}
              onChange={(event) => setKind(event.target.value as ScopeKind)}
              className={ui.input}
            >
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {KIND_LABEL[k]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="entry-value" className={ui.label}>
              Valeur
            </label>
            <input
              id="entry-value"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              required
              autoComplete="off"
              spellCheck={false}
              placeholder={
                kind === "cidr" ? "10.20.0.0/16" : kind === "ip" ? "93.184.216.34" : "exemple.com"
              }
              className={ui.input}
            />
          </div>
        </div>
        {kind === "domain" ? (
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={subdomains}
              onChange={(event) => setSubdomains(event.target.checked)}
            />
            Inclure les sous-domaines
          </label>
        ) : null}
        <div>
          <label htmlFor="entry-description" className={ui.label}>
            Description (optionnel)
          </label>
          <input
            id="entry-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            maxLength={500}
            className={ui.input}
          />
        </div>
        <button type="submit" disabled={add.isPending} className={ui.button}>
          Ajouter
        </button>
      </form>
    </section>
  );
}

function CheckTarget() {
  const check = useScopeCheck();
  const [target, setTarget] = useState("");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (target.trim()) check.mutate(target.trim());
  }

  return (
    <section aria-labelledby="check-target" className={`${ui.card} space-y-3`}>
      <h2 id="check-target" className={ui.h2}>
        Tester une cible
      </h2>
      <p className={ui.hint}>
        Vérifie, sans rien lancer, si une cible serait autorisée maintenant.
      </p>
      <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-3" noValidate>
        <div className="min-w-60 flex-1">
          <label htmlFor="check-input" className={ui.label}>
            Cible à tester
          </label>
          <input
            id="check-input"
            value={target}
            onChange={(event) => setTarget(event.target.value)}
            autoComplete="off"
            spellCheck={false}
            className={ui.input}
          />
        </div>
        <button type="submit" disabled={check.isPending} className={ui.button}>
          Tester
        </button>
      </form>
      {check.isError ? <FormError>{errorMessage(check.error)}</FormError> : null}
      {check.data ? (
        <div role="status" aria-label="Résultat du test" className="space-y-1 text-sm">
          {check.data.allowed ? (
            <>
              <p className="font-semibold text-green-800 dark:text-green-300">Autorisée</p>
              <p>Adresses validées : {check.data.pinned_ips.join(", ")}</p>
            </>
          ) : (
            <p className="font-semibold text-red-800 dark:text-red-300">
              Refusée : {scopeReasonLabel(check.data.reason)}.
            </p>
          )}
        </div>
      ) : null}
    </section>
  );
}

export function ScopePage() {
  useDocumentTitle("Périmètre autorisé");
  const user = useCurrentUser();
  const entries = useScopeEntries();
  const remove = useDeleteScopeEntry();
  const [confirming, setConfirming] = useState<string | null>(null);

  return (
    <>
      <PageHeader title="Périmètre autorisé">
        <p className={ui.hint}>Aucune cible ne peut être analysée sans autorisation explicite.</p>
      </PageHeader>

      {entries.isPending ? (
        <LoadingState />
      ) : entries.isError ? (
        <ErrorState error={entries.error} onRetry={() => void entries.refetch()} />
      ) : entries.data.length === 0 ? (
        <EmptyState>
          Aucune autorisation configurée. Ajoutez un domaine, une IP ou une plage pour pouvoir
          lancer des scans.
        </EmptyState>
      ) : (
        <div className={ui.tableWrap}>
          <table className={ui.table}>
            <caption className="sr-only">Périmètre autorisé</caption>
            <thead>
              <tr>
                <th scope="col" className={ui.th}>
                  Type
                </th>
                <th scope="col" className={ui.th}>
                  Valeur
                </th>
                <th scope="col" className={ui.th}>
                  Classe
                </th>
                <th scope="col" className={ui.th}>
                  Sous-domaines
                </th>
                <th scope="col" className={ui.th}>
                  Description
                </th>
                {atLeast(user.role, "admin") ? (
                  <th scope="col" className={ui.th}>
                    Actions
                  </th>
                ) : null}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
              {entries.data.map((entry) => (
                <tr key={entry.id}>
                  <td className={ui.td}>{KIND_LABEL[entry.kind]}</td>
                  <td className={`${ui.td} font-mono`}>{entry.value}</td>
                  <td className={ui.td}>{CLASS_LABEL[entry.network_class]}</td>
                  <td className={ui.td}>
                    {entry.kind === "domain" ? (entry.include_subdomains ? "Oui" : "Non") : "—"}
                  </td>
                  <td className={ui.td}>{entry.description ?? "—"}</td>
                  {atLeast(user.role, "admin") ? (
                    <td className={ui.td}>
                      {confirming === entry.id ? (
                        <span className="flex gap-2">
                          <button
                            type="button"
                            className={ui.buttonDanger}
                            aria-label={`Confirmer la suppression de ${entry.value}`}
                            onClick={() => {
                              remove.mutate(entry.id);
                              setConfirming(null);
                            }}
                          >
                            Confirmer
                          </button>
                          <button
                            type="button"
                            className={ui.buttonSecondary}
                            aria-label={`Annuler la suppression de ${entry.value}`}
                            onClick={() => setConfirming(null)}
                          >
                            Annuler
                          </button>
                        </span>
                      ) : (
                        <button
                          type="button"
                          className={ui.buttonSecondary}
                          aria-label={`Supprimer ${entry.value}`}
                          onClick={() => setConfirming(entry.id)}
                        >
                          Supprimer
                        </button>
                      )}
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {remove.isError ? <FormError>{errorMessage(remove.error)}</FormError> : null}

      {atLeast(user.role, "admin") ? <AddEntryForm /> : null}
      {atLeast(user.role, "analyst") ? <CheckTarget /> : null}
    </>
  );
}
