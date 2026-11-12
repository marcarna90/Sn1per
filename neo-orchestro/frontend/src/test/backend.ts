import { vi } from "vitest";
import type { User } from "../api/types";
import { DNS_ENGINE } from "./fixtures";

export interface RequestInfoLike {
  method: string;
  path: string;
  url: URL;
  body: unknown;
}
export type Handler = (request: RequestInfoLike) => unknown;

export interface Recorded {
  method: string;
  path: string;
  query: string;
  body: unknown;
  headers: Headers;
}

/** Tag a handler result with an HTTP status. */
export const status = (code: number, body?: unknown) => ({ __status: code, body });

export const apiError = (code: string, message: string, details: unknown = {}) => ({
  error: { code, message, details, request_id: "req-test-0001" },
});

/** An in-memory fake of the Neo-Orchestro API, installed as the global `fetch`. */
export class FakeBackend {
  readonly calls: Recorded[] = [];
  readonly unhandled: string[] = [];
  readonly #handlers = new Map<string, Handler>();

  /** Register a handler function, or a fixed response body, for "METHOD /path". */
  on(key: string, handler: Handler): this;
  on(key: string, response: object | string | number | null): this;
  on(key: string, handler: unknown): this {
    this.#handlers.set(key, typeof handler === "function" ? (handler as Handler) : () => handler);
    return this;
  }

  /** Answers every endpoint a signed-in user's pages may call with sensible empty data. */
  signedIn(user: User): this {
    return this.on("POST /api/v1/auth/refresh", {
      access_token: "tok-test",
      token_type: "bearer",
      expires_in: 900,
    })
      .on("GET /api/v1/auth/me", user)
      .on("POST /api/v1/auth/logout", status(204))
      .on("GET /api/v1/scans", [])
      .on("GET /api/v1/scope/entries", [])
      .on("GET /api/v1/engines", [DNS_ENGINE])
      .on("GET /api/v1/audit-logs", [])
      .on("GET /health/ready", { status: "ok", checks: { database: "ok", redis: "ok" } })
      .on("GET /api/v1/meta", {
        name: "Neo-Orchestro",
        version: "0.1.0",
        signature: "Designed & Developed by Ronald TSR",
      });
  }

  /** No valid refresh cookie: the visitor is anonymous. */
  signedOut(): this {
    return this.on(
      "POST /api/v1/auth/refresh",
      status(401, apiError("authentication_failed", "invalid or expired token")),
    ).on("GET /api/v1/meta", {
      name: "Neo-Orchestro",
      version: "0.1.0",
      signature: "Designed & Developed by Ronald TSR",
    });
  }

  install(): this {
    vi.stubGlobal("fetch", this.fetch);
    return this;
  }

  called(method: string, path: string): Recorded[] {
    return this.calls.filter((c) => c.method === method && c.path === path);
  }

  readonly fetch = async (input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> => {
    const raw = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const url = new URL(raw, "http://localhost");
    const method = (init.method ?? "GET").toUpperCase();
    const body: unknown = typeof init.body === "string" ? JSON.parse(init.body) : undefined;
    this.calls.push({
      method,
      path: url.pathname,
      query: url.search,
      body,
      headers: new Headers(init.headers),
    });

    const handler = this.#handlers.get(`${method} ${url.pathname}`);
    if (!handler) {
      this.unhandled.push(`${method} ${url.pathname}`);
      return json(apiError("not_found", "no fake handler"), 404);
    }
    const result = await handler({ method, path: url.pathname, url, body });
    if (typeof result === "object" && result !== null && "__status" in result) {
      const { __status, body: payload } = result as { __status: number; body?: unknown };
      return __status === 204 ? new Response(null, { status: 204 }) : json(payload, __status);
    }
    return json(result, 200);
  };
}

function json(body: unknown, statusCode: number): Response {
  return new Response(JSON.stringify(body), {
    status: statusCode,
    headers: { "Content-Type": "application/json" },
  });
}
