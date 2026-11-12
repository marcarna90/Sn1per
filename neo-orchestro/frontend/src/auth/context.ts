import { createContext, useContext } from "react";
import type { ApiClient } from "../api/client";
import type { User } from "../api/types";

export type AuthState =
  { status: "loading" } | { status: "anonymous" } | { status: "authenticated"; user: User };

/** Why the visitor is on the login page, when it is not simply a first visit. */
export type AuthNotice = "expired" | "password-changed";

export interface AuthContextValue {
  state: AuthState;
  notice: AuthNotice | null;
  client: ApiClient;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  /** End the local session without calling the API (it already revoked everything). */
  endSession: (notice: AuthNotice) => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>");
  return value;
}

/** The signed-in user. Only call it below <RequireAuth>. */
export function useCurrentUser(): User {
  const { state } = useAuth();
  if (state.status !== "authenticated") throw new Error("No authenticated user");
  return state.user;
}
