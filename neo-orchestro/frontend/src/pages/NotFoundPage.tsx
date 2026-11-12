import { Link } from "react-router-dom";
import { ui } from "../components/ui";
import { useDocumentTitle } from "../lib/useDocumentTitle";

export function NotFoundPage() {
  useDocumentTitle("Page introuvable");
  return (
    <div className="space-y-3">
      <h1 className={ui.h1}>Page introuvable</h1>
      <p>La page demandée n&apos;existe pas.</p>
      <Link to="/" className={ui.link}>
        Retour au tableau de bord
      </Link>
    </div>
  );
}
