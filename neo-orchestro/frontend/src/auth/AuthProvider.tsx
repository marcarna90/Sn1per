import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiClient } from "../api/client";
import type { User } from "../api/types";
import { AuthContext, type AuthContextValue, type AuthNotice, type AuthState } from "./context";

const ME = "/api/v1/auth/me";

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<AuthState>({ status: "loading" });
  const [notice, setNotice] = useState<AuthNotice | null>(null);

  const client = useMemo(
    () =>
      new ApiClient({
        // A refresh that fails mid-session means the session is gone: drop cached data too.
        onSessionLost: () => {
          queryClient.clear();
          setNotice("expired");
          setState({ status: "anonymous" });
        },
      }),
    [queryClient],
  );

  // Restore the session after a reload: the HttpOnly refresh cookie is the only thing that
  // survives (the access token lives in memory).
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        await client.refresh();
        const user = await client.get<User>(ME);
        if (!cancelled) setState({ status: "authenticated", user });
      } catch {
        if (!cancelled) setState({ status: "anonymous" });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [client]);

  const login = useCallback(
    async (email: string, password: string) => {
      await client.login(email, password);
      const user = await client.get<User>(ME);
      setNotice(null);
      setState({ status: "authenticated", user });
    },
    [client],
  );

  const endSession = useCallback(
    (reason: AuthNotice) => {
      client.setAccessToken(null);
      queryClient.clear();
      setNotice(reason);
      setState({ status: "anonymous" });
    },
    [client, queryClient],
  );

  const logout = useCallback(async () => {
    try {
      await client.logout();
    } catch {
      // The server may be unreachable; the local session must end regardless.
    } finally {
      queryClient.clear();
      setNotice(null);
      setState({ status: "anonymous" });
    }
  }, [client, queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({ state, notice, client, login, logout, endSession }),
    [state, notice, client, login, logout, endSession],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
