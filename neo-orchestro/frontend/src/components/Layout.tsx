import { useEffect, useRef } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth, useCurrentUser } from "../auth/context";
import { atLeast } from "../lib/roles";
import { ui } from "./ui";

export const SIGNATURE = "Designed & Developed by Ronald TSR";

interface NavItem {
  to: string;
  label: string;
  admin?: boolean;
  end?: boolean;
}

const ITEMS: NavItem[] = [
  { to: "/", label: "Tableau de bord", end: true },
  { to: "/scans", label: "Scans" },
  { to: "/scope", label: "Périmètre" },
  { to: "/users", label: "Utilisateurs", admin: true },
  { to: "/audit", label: "Journal d'audit", admin: true },
  { to: "/settings", label: "Paramètres" },
];

const LINK =
  "block whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-200 " +
  "dark:text-slate-200 dark:hover:bg-slate-700";
const ACTIVE = "bg-indigo-100 text-indigo-900 dark:bg-indigo-900 dark:text-indigo-50";

export function Layout() {
  const user = useCurrentUser();
  const { logout } = useAuth();
  const location = useLocation();
  const main = useRef<HTMLElement>(null);
  const first = useRef(true);

  // Move keyboard/screen-reader focus to the new page after a navigation (not on first load).
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    main.current?.focus();
  }, [location.pathname]);

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-white focus:px-3 focus:py-2 focus:text-indigo-900"
      >
        Aller au contenu principal
      </a>
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3 dark:border-slate-700 dark:bg-slate-800">
        <p className="text-lg font-semibold tracking-tight">Neo-Orchestro</p>
        <div className="flex items-center gap-3 text-sm">
          <span>{user.email}</span>
          <button type="button" onClick={() => void logout()} className={ui.buttonSecondary}>
            Se déconnecter
          </button>
        </div>
      </header>
      <div className="flex flex-1 flex-col md:flex-row">
        <nav
          aria-label="Navigation principale"
          className="border-b border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-800 md:w-56 md:border-b-0 md:border-r"
        >
          <ul className="flex gap-1 overflow-x-auto md:flex-col">
            {ITEMS.filter((item) => !item.admin || atLeast(user.role, "admin")).map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.end ?? false}
                  className={({ isActive }) => `${LINK} ${isActive ? ACTIVE : ""}`}
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <main id="main" tabIndex={-1} ref={main} className="flex-1 space-y-6 p-4 md:p-6">
          <Outlet />
        </main>
      </div>
      <footer className="border-t border-slate-200 px-4 py-3 text-center text-sm text-slate-700 dark:border-slate-700 dark:text-slate-300">
        {SIGNATURE}
      </footer>
    </div>
  );
}

export function PageHeader({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <h1 className={ui.h1}>{title}</h1>
      {children}
    </div>
  );
}
