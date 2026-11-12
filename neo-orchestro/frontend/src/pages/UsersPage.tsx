import { useState, type FormEvent } from "react";
import { ApiError } from "../api/errors";
import { useCreateUser, useUpdateUser, useUsers } from "../api/hooks";
import type { Role } from "../api/types";
import { PageHeader } from "../components/Layout";
import { EmptyState, ErrorState, FormError, LoadingState, Notice } from "../components/States";
import { ui } from "../components/ui";
import { errorMessage, formatDateTime } from "../lib/format";
import { ROLE_LABEL } from "../lib/roles";
import { useDocumentTitle } from "../lib/useDocumentTitle";

const ROLES = Object.keys(ROLE_LABEL) as Role[];

function CreateUserForm({ onCreated }: { onCreated: () => void }) {
  const create = useCreateUser();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("viewer");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await create.mutateAsync({ email: email.trim(), password, role });
      setEmail("");
      setPassword("");
      onCreated();
    } catch (caught) {
      setError(
        caught instanceof ApiError && caught.status === 409
          ? "Un utilisateur avec cet e-mail existe déjà."
          : errorMessage(caught),
      );
    }
  }

  return (
    <section aria-labelledby="create-user" className={`${ui.card} space-y-4`}>
      <h2 id="create-user" className={ui.h2}>
        Créer un utilisateur
      </h2>
      <form onSubmit={(event) => void onSubmit(event)} className="space-y-4" noValidate>
        {error ? <FormError>{error}</FormError> : null}
        <div className="grid gap-4 md:grid-cols-3">
          <div>
            <label htmlFor="new-email" className={ui.label}>
              E-mail
            </label>
            <input
              id="new-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="off"
              className={ui.input}
            />
          </div>
          <div>
            <label htmlFor="new-password" className={ui.label}>
              Mot de passe
            </label>
            <input
              id="new-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
              aria-describedby="new-password-hint"
              className={ui.input}
            />
            <p id="new-password-hint" className={ui.hint}>
              12 caractères minimum.
            </p>
          </div>
          <div>
            <label htmlFor="new-role" className={ui.label}>
              Rôle
            </label>
            <select
              id="new-role"
              value={role}
              onChange={(event) => setRole(event.target.value as Role)}
              className={ui.input}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABEL[r]}
                </option>
              ))}
            </select>
          </div>
        </div>
        <button type="submit" disabled={create.isPending} className={ui.button}>
          Créer l&apos;utilisateur
        </button>
      </form>
    </section>
  );
}

export function UsersPage() {
  useDocumentTitle("Utilisateurs");
  const users = useUsers();
  const update = useUpdateUser();
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function change(id: string, changes: { role?: Role; is_active?: boolean }) {
    setError(null);
    setNotice(null);
    update.mutate(
      { id, ...changes },
      {
        onSuccess: () => setNotice("Utilisateur mis à jour."),
        onError: (caught) => setError(errorMessage(caught)),
      },
    );
  }

  return (
    <>
      <PageHeader title="Utilisateurs" />
      {notice ? <Notice>{notice}</Notice> : null}
      {error ? <FormError>{error}</FormError> : null}

      {users.isPending ? (
        <LoadingState />
      ) : users.isError ? (
        <ErrorState error={users.error} onRetry={() => void users.refetch()} />
      ) : users.data.length === 0 ? (
        <EmptyState>Aucun utilisateur.</EmptyState>
      ) : (
        <div className={ui.tableWrap}>
          <table className={ui.table}>
            <caption className="sr-only">Utilisateurs de l&apos;organisation</caption>
            <thead>
              <tr>
                <th scope="col" className={ui.th}>
                  E-mail
                </th>
                <th scope="col" className={ui.th}>
                  Rôle
                </th>
                <th scope="col" className={ui.th}>
                  Statut
                </th>
                <th scope="col" className={ui.th}>
                  Dernière connexion
                </th>
                <th scope="col" className={ui.th}>
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
              {users.data.map((u) => (
                <tr key={u.id}>
                  <td className={ui.td}>{u.email}</td>
                  <td className={ui.td}>
                    <select
                      aria-label={`Rôle de ${u.email}`}
                      value={u.role}
                      onChange={(event) => change(u.id, { role: event.target.value as Role })}
                      className={ui.input}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {ROLE_LABEL[r]}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className={ui.td}>{u.is_active ? "Actif" : "Désactivé"}</td>
                  <td className={ui.td}>
                    {u.last_login_at ? formatDateTime(u.last_login_at) : "Jamais"}
                  </td>
                  <td className={ui.td}>
                    <button
                      type="button"
                      className={u.is_active ? ui.buttonDanger : ui.buttonSecondary}
                      aria-label={`${u.is_active ? "Désactiver" : "Réactiver"} ${u.email}`}
                      onClick={() => change(u.id, { is_active: !u.is_active })}
                    >
                      {u.is_active ? "Désactiver" : "Réactiver"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <CreateUserForm onCreated={() => setNotice("Utilisateur créé.")} />
    </>
  );
}
