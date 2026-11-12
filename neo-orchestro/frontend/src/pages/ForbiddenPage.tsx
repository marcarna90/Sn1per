import { Link } from "react-router-dom";
import { ui } from "../components/ui";
import { useDocumentTitle } from "../lib/useDocumentTitle";

export function ForbiddenPage() {
  useDocumentTitle("Accès refusé");
  return (
    <div className="space-y-3">
      <h1 className={ui.h1}>Accès refusé</h1>
      <p>Vous n&apos;avez pas les droits nécessaires pour consulter cette page.</p>
      <Link to="/" className={ui.link}>
        Retour au tableau de bord
      </Link>
    </div>
  );
}
