import { Navigate, Outlet, useLocation } from "react-router-dom";
import type { Role } from "../api/types";
import { LoadingState } from "../components/States";
import { atLeast } from "../lib/roles";
import { ForbiddenPage } from "../pages/ForbiddenPage";
import { useAuth } from "./context";

/** Renders the nested routes for signed-in users; everyone else is sent to the login page. */
export function RequireAuth() {
  const { state } = useAuth();
  const location = useLocation();
  if (state.status === "loading") return <LoadingState />;
  if (state.status === "anonymous") {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  return <Outlet />;
}

/** UI-level role gate. It is a convenience only: the API enforces the same rule server-side. */
export function RequireRole({ minimum }: { minimum: Role }) {
  const { state } = useAuth();
  if (state.status !== "authenticated") return null;
  return atLeast(state.user.role, minimum) ? <Outlet /> : <ForbiddenPage />;
}
