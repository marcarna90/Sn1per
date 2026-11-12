import { useState, type FormEvent } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { ApiError } from "../api/errors";
import { useAuth } from "../auth/context";
import { SIGNATURE } from "../components/Layout";
import { FormError } from "../components/States";
import { ui } from "../components/ui";
import { useDocumentTitle } from "../lib/useDocumentTitle";

const NOTICES = {
  expired: "Votre session a expiré. Veuillez vous reconnecter.",
  "password-changed": "Mot de passe modifié. Veuillez vous reconnecter.",
} as const;

function loginError(error: unknown): string {
  if (error instanceof ApiError) {
    // One generic message for every rejected credential: the server never says which part
    // was wrong or whether the account exists or is locked.
    if (error.status === 401) return "Identifiants invalides ou compte verrouillé.";
    return error.message;
  }
  return "Une erreur inattendue est survenue.";
}

export function LoginPage() {
  useDocumentTitle("Connexion");
  const { state, notice, login } = useAuth();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (state.status === "authenticated") return <Navigate to={from} replace />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
    } catch (caught) {
      setError(loginError(caught));
      setPassword(""); // never keep a rejected password in the field
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <main
        id="main"
        className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-6 p-6"
      >
        <div>
          <h1 className={ui.h1}>Connexion</h1>
          <p className={`${ui.hint} mt-1`}>
            Neo-Orchestro — plateforme d&apos;évaluation et d&apos;orchestration de sécurité.
          </p>
        </div>
        {notice ? (
          <div
            role="status"
            className="rounded-md border border-blue-700 bg-blue-50 px-3 py-2 text-sm text-blue-900 dark:bg-blue-950 dark:text-blue-100"
          >
            {NOTICES[notice]}
          </div>
        ) : null}
        <form
          onSubmit={(event) => void onSubmit(event)}
          className={`${ui.card} space-y-4`}
          noValidate
        >
          {error ? <FormError>{error}</FormError> : null}
          <div>
            <label htmlFor="email" className={ui.label}>
              Adresse e-mail
            </label>
            <input
              id="email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={ui.input}
            />
          </div>
          <div>
            <label htmlFor="password" className={ui.label}>
              Mot de passe
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={ui.input}
            />
          </div>
          <button type="submit" disabled={busy} className={`${ui.button} w-full`}>
            Se connecter
          </button>
        </form>
      </main>
      <footer className="px-4 py-3 text-center text-sm text-slate-700 dark:text-slate-300">
        {SIGNATURE}
      </footer>
    </div>
  );
}
