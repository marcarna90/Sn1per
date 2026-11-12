import { useState, type FormEvent } from "react";
import { ApiError } from "../api/errors";
import { useChangePassword, useMeta } from "../api/hooks";
import { useAuth, useCurrentUser } from "../auth/context";
import { PageHeader, SIGNATURE } from "../components/Layout";
import { FormError } from "../components/States";
import { ui } from "../components/ui";
import { errorMessage } from "../lib/format";
import { ROLE_LABEL } from "../lib/roles";
import { useDocumentTitle } from "../lib/useDocumentTitle";

export function SettingsPage() {
  useDocumentTitle("Paramètres");
  const user = useCurrentUser();
  const { endSession } = useAuth();
  const meta = useMeta();
  const change = useChangePassword();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (next !== confirm) {
      setError("Les mots de passe ne correspondent pas.");
      return;
    }
    try {
      await change.mutateAsync({ old_password: current, new_password: next });
      endSession("password-changed"); // the server revoked every session of this user
    } catch (caught) {
      setError(
        caught instanceof ApiError && caught.status === 401
          ? "Mot de passe actuel incorrect."
          : errorMessage(caught),
      );
    }
  }

  return (
    <>
      <PageHeader title="Paramètres" />
      <section aria-labelledby="profile" className={`${ui.card} space-y-1`}>
        <h2 id="profile" className={ui.h2}>
          Profil
        </h2>
        <p>Connecté en tant que {user.email}</p>
        <p>{ROLE_LABEL[user.role]}</p>
      </section>

      <section aria-labelledby="password" className={`${ui.card} space-y-4`}>
        <h2 id="password" className={ui.h2}>
          Mot de passe
        </h2>
        <form onSubmit={(event) => void onSubmit(event)} className="max-w-md space-y-4" noValidate>
          {error ? <FormError>{error}</FormError> : null}
          <div>
            <label htmlFor="old-password" className={ui.label}>
              Mot de passe actuel
            </label>
            <input
              id="old-password"
              type="password"
              autoComplete="current-password"
              value={current}
              onChange={(event) => setCurrent(event.target.value)}
              className={ui.input}
            />
          </div>
          <div>
            <label htmlFor="next-password" className={ui.label}>
              Nouveau mot de passe
            </label>
            <input
              id="next-password"
              type="password"
              autoComplete="new-password"
              aria-describedby="next-password-hint"
              value={next}
              onChange={(event) => setNext(event.target.value)}
              className={ui.input}
            />
            <p id="next-password-hint" className={ui.hint}>
              12 à 128 caractères. Toutes vos sessions seront fermées.
            </p>
          </div>
          <div>
            <label htmlFor="confirm-password" className={ui.label}>
              Confirmer le nouveau mot de passe
            </label>
            <input
              id="confirm-password"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              className={ui.input}
            />
          </div>
          <button type="submit" disabled={change.isPending} className={ui.button}>
            Changer le mot de passe
          </button>
        </form>
      </section>

      <section aria-labelledby="about" className={`${ui.card} space-y-1`}>
        <h2 id="about" className={ui.h2}>
          À propos
        </h2>
        {meta.data ? <p>Version {meta.data.version}</p> : null}
        <p className={ui.hint}>{SIGNATURE}</p>
      </section>
    </>
  );
}
