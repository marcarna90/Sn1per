import { describe, expect, it, vi } from "vitest";
import { ApiClient } from "./client";
import { ApiError } from "./errors";

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

/** The client only ever passes string URLs; make that explicit for the type checker. */
function urlOf(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  return input instanceof URL ? input.href : input.url;
}

function refreshCalls(fetchImpl: { mock: { calls: unknown[][] } }): unknown[][] {
  return fetchImpl.mock.calls.filter((call) => (call[0] as string).endsWith("/auth/refresh"));
}

function setup(handler: Handler) {
  const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
    handler(urlOf(input), init ?? {}),
  );
  const onSessionLost = vi.fn();
  const client = new ApiClient({ fetchImpl: fetchImpl as unknown as typeof fetch, onSessionLost });
  return { client, fetchImpl, onSessionLost };
}

const headersOf = (init: RequestInit) => new Headers(init.headers);

describe("ApiClient requests", () => {
  it("sends the bearer token, JSON body and cookies for authenticated calls", async () => {
    const { client, fetchImpl } = setup(() => json({ ok: true }));
    client.setAccessToken("tok-1");
    await client.post("/api/v1/scans", { target: "a.example.com" });

    const [url, init] = fetchImpl.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/scans");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    expect(headersOf(init).get("Authorization")).toBe("Bearer tok-1");
    expect(headersOf(init).get("Content-Type")).toBe("application/json");
    expect(init.body).toBe(JSON.stringify({ target: "a.example.com" }));
    expect(headersOf(init).get("X-Neo-CSRF")).toBeNull();
  });

  it("omits the Authorization header when there is no token", async () => {
    const { client, fetchImpl } = setup(() => json({}));
    await client.get("/api/v1/meta");
    expect(
      headersOf((fetchImpl.mock.calls[0] as [string, RequestInit])[1]).get("Authorization"),
    ).toBeNull();
  });

  it("serialises query parameters, skipping empty values", async () => {
    const { client, fetchImpl } = setup(() => json([]));
    await client.get("/api/v1/scans", {
      status: "pending",
      limit: 20,
      offset: 0,
      q: "",
      x: undefined,
      y: null,
    });
    expect((fetchImpl.mock.calls[0] as [string])[0]).toBe(
      "/api/v1/scans?status=pending&limit=20&offset=0",
    );
  });

  it("returns undefined for 204 responses", async () => {
    const { client } = setup(() => new Response(null, { status: 204 }));
    await expect(client.delete("/api/v1/scope/entries/x")).resolves.toBeUndefined();
  });

  it("refuses paths outside /api/ and /health/ (no request to arbitrary URLs)", async () => {
    const { client, fetchImpl } = setup(() => json({}));
    await expect(client.get("https://evil.example/steal")).rejects.toThrow(/relative/i);
    await expect(client.get("//evil.example/x")).rejects.toThrow(/relative/i);
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});

describe("ApiClient readiness", () => {
  it("returns the readiness report even when the API is degraded (503)", async () => {
    const report = { status: "degraded", checks: { database: "ok", redis: "fail" } };
    const { client } = setup(() => json(report, 503));
    await expect(client.health()).resolves.toEqual(report);
  });

  it("reports an unreachable API as an ApiError", async () => {
    const fetchImpl = vi.fn(() => Promise.reject(new TypeError("Failed to fetch")));
    const client = new ApiClient({ fetchImpl: fetchImpl as unknown as typeof fetch });
    await expect(client.health()).rejects.toMatchObject({ code: "network_error" });
  });
});

describe("ApiClient errors", () => {
  it("turns the server error envelope into an ApiError", async () => {
    const { client } = setup(() =>
      json(
        {
          error: {
            code: "scope_violation",
            message: "target is not authorised",
            details: { reason: "not_in_scope" },
            request_id: "req-123456",
          },
        },
        403,
      ),
    );
    const error = await client.get("/api/v1/x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.status).toBe(403);
    expect(apiError.code).toBe("scope_violation");
    expect(apiError.message).toBe("target is not authorised");
    expect(apiError.details).toEqual({ reason: "not_in_scope" });
    expect(apiError.requestId).toBe("req-123456");
  });

  it("handles non-JSON error bodies (e.g. a proxy 502 page)", async () => {
    const { client } = setup(() => new Response("<html>Bad gateway</html>", { status: 502 }));
    const error = (await client.get("/api/v1/x").catch((e: unknown) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(502);
    expect(error.code).toBe("http_error");
    expect(error.message).not.toContain("<html>");
  });

  it("reports network failures as an ApiError", async () => {
    const fetchImpl = vi.fn(() => Promise.reject(new TypeError("Failed to fetch")));
    const client = new ApiClient({ fetchImpl: fetchImpl as unknown as typeof fetch });
    const error = (await client.get("/api/v1/x").catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe("network_error");
    expect(error.status).toBe(0);
  });
});

describe("ApiClient session handling", () => {
  it("sends the CSRF header on refresh and logout, and stores the new token", async () => {
    const { client, fetchImpl } = setup((url) =>
      url.endsWith("/refresh")
        ? json({ access_token: "tok-new", token_type: "bearer", expires_in: 900 })
        : new Response(null, { status: 204 }),
    );
    await expect(client.refresh()).resolves.toBe("tok-new");
    expect(client.accessToken).toBe("tok-new");
    await client.logout();
    expect(client.accessToken).toBeNull();

    for (const call of fetchImpl.mock.calls as [string, RequestInit][]) {
      expect(headersOf(call[1]).get("X-Neo-CSRF")).toBe("1");
      expect(call[1].credentials).toBe("include");
    }
  });

  it("refreshes once on 401 and retries the request with the new token", async () => {
    let calls = 0;
    const { client, fetchImpl } = setup((url, init) => {
      if (url.endsWith("/auth/refresh"))
        return json({ access_token: "tok-2", token_type: "bearer", expires_in: 900 });
      calls += 1;
      return headersOf(init).get("Authorization") === "Bearer tok-2"
        ? json({ data: 1 })
        : json(
            {
              error: {
                code: "authentication_failed",
                message: "expired",
                details: {},
                request_id: null,
              },
            },
            401,
          );
    });
    client.setAccessToken("tok-old");
    await expect(client.get("/api/v1/scans")).resolves.toEqual({ data: 1 });
    expect(calls).toBe(2);
    expect(refreshCalls(fetchImpl)).toHaveLength(1);
  });

  it("shares ONE refresh between concurrent 401s", async () => {
    const { client, fetchImpl } = setup((url, init) => {
      if (url.endsWith("/auth/refresh"))
        return json({ access_token: "tok-2", token_type: "bearer", expires_in: 900 });
      return headersOf(init).get("Authorization") === "Bearer tok-2"
        ? json({})
        : json(
            {
              error: { code: "authentication_failed", message: "x", details: {}, request_id: null },
            },
            401,
          );
    });
    client.setAccessToken("tok-old");
    await Promise.all([client.get("/api/v1/a"), client.get("/api/v1/b"), client.get("/api/v1/c")]);
    expect(refreshCalls(fetchImpl)).toHaveLength(1);
  });

  it("ends the session when the refresh fails, without looping", async () => {
    const unauthorised = () =>
      json(
        { error: { code: "authentication_failed", message: "no", details: {}, request_id: null } },
        401,
      );
    const { client, fetchImpl, onSessionLost } = setup(unauthorised);
    client.setAccessToken("tok-old");
    const error = (await client.get("/api/v1/scans").catch((e: unknown) => e)) as ApiError;
    expect(error.status).toBe(401);
    expect(onSessionLost).toHaveBeenCalledTimes(1);
    expect(client.accessToken).toBeNull();
    expect(fetchImpl).toHaveBeenCalledTimes(2); // the request + one refresh, then stop
  });

  it("does not try to refresh when the login itself is rejected", async () => {
    const { client, fetchImpl, onSessionLost } = setup(() =>
      json(
        {
          error: {
            code: "authentication_failed",
            message: "invalid credentials",
            details: {},
            request_id: null,
          },
        },
        401,
      ),
    );
    const error = (await client.login("a@b.example", "wrong").catch((e: unknown) => e)) as ApiError;
    expect(error.status).toBe(401);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(onSessionLost).not.toHaveBeenCalled();
  });

  it("login stores the access token", async () => {
    const { client } = setup(() =>
      json({ access_token: "tok-login", token_type: "bearer", expires_in: 900 }),
    );
    await client.login("a@b.example", "secret-password-123");
    expect(client.accessToken).toBe("tok-login");
  });
});
