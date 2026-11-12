import { ApiError, toApiError } from "./errors";
import type { Health, TokenResponse } from "./types";

type Query = Record<string, string | number | boolean | null | undefined>;

interface SendOptions {
  body?: unknown;
  query?: Query;
  /** Cookie-authenticated endpoints need a header a cross-site form cannot set. */
  csrf?: boolean;
  /** Attach the bearer token (default true). */
  bearer?: boolean;
  /** Refresh the access token once on 401 and replay (default true). */
  retryOn401?: boolean;
}

export interface ApiClientOptions {
  fetchImpl?: typeof fetch;
  /** Called when the session can no longer be recovered (refresh failed). */
  onSessionLost?: () => void;
}

// Only same-origin API paths are ever requested: a path can never redirect the app (or its
// credentials) to another host.
const ALLOWED_PATH = /^\/(api|health)\//;

function buildUrl(path: string, query?: Query): string {
  if (!ALLOWED_PATH.test(path)) {
    throw new Error("Only relative /api/ and /health/ paths are allowed");
  }
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

export class ApiClient {
  readonly #fetch: typeof fetch;
  readonly #onSessionLost: (() => void) | undefined;
  // The access token lives in memory only (never localStorage): XSS cannot exfiltrate a
  // long-lived credential, and a reload recovers through the HttpOnly refresh cookie.
  #token: string | null = null;
  #refreshing: Promise<string> | null = null;

  constructor(options: ApiClientOptions = {}) {
    this.#fetch = options.fetchImpl ?? ((...args) => fetch(...args));
    this.#onSessionLost = options.onSessionLost;
  }

  get accessToken(): string | null {
    return this.#token;
  }

  setAccessToken(token: string | null): void {
    this.#token = token;
  }

  // ------------------------------------------------------------------ session

  async login(email: string, password: string): Promise<void> {
    const body = await this.#call<TokenResponse>("POST", "/api/v1/auth/login", {
      body: { email, password },
      bearer: false,
      retryOn401: false,
    });
    this.#token = body.access_token;
  }

  /** Rotate the refresh cookie and obtain a new access token. Concurrent calls share one request. */
  refresh(): Promise<string> {
    this.#refreshing ??= this.#call<TokenResponse>("POST", "/api/v1/auth/refresh", {
      csrf: true,
      bearer: false,
      retryOn401: false,
    })
      .then((body) => {
        this.#token = body.access_token;
        return body.access_token;
      })
      .finally(() => {
        this.#refreshing = null;
      });
    return this.#refreshing;
  }

  async logout(): Promise<void> {
    try {
      await this.#call<undefined>("POST", "/api/v1/auth/logout", {
        csrf: true,
        bearer: false,
        retryOn401: false,
      });
    } finally {
      this.#token = null;
    }
  }

  /** Readiness report. A 503 still carries a useful body ("degraded"), so it is not an error. */
  async health(): Promise<Health> {
    const response = await this.#send("GET", "/health/ready", { bearer: false });
    if (response.status === 200 || response.status === 503)
      return (await response.json()) as Health;
    throw await toApiError(response);
  }

  // ------------------------------------------------------------------ verbs

  get<T>(path: string, query?: Query): Promise<T> {
    return this.#call<T>("GET", path, query ? { query } : {});
  }

  post<T>(path: string, body?: unknown): Promise<T> {
    return this.#call<T>("POST", path, body === undefined ? {} : { body });
  }

  patch<T>(path: string, body: unknown): Promise<T> {
    return this.#call<T>("PATCH", path, { body });
  }

  delete(path: string): Promise<undefined> {
    return this.#call<undefined>("DELETE", path, {});
  }

  // ------------------------------------------------------------------ internals

  async #send(method: string, path: string, options: SendOptions): Promise<Response> {
    const headers = new Headers({ Accept: "application/json" });
    if (options.body !== undefined) headers.set("Content-Type", "application/json");
    if (options.csrf) headers.set("X-Neo-CSRF", "1");
    if (options.bearer !== false && this.#token)
      headers.set("Authorization", `Bearer ${this.#token}`);

    const init: RequestInit = { method, headers, credentials: "include" };
    if (options.body !== undefined) init.body = JSON.stringify(options.body);
    try {
      return await this.#fetch(buildUrl(path, options.query), init);
    } catch (error) {
      if (error instanceof Error && error.message.startsWith("Only relative")) throw error;
      throw new ApiError(0, "network_error", "Impossible de joindre le serveur.");
    }
  }

  async #call<T>(method: string, path: string, options: SendOptions): Promise<T> {
    const sentWith = this.#token;
    let response = await this.#send(method, path, options);

    if (response.status === 401 && options.retryOn401 !== false) {
      // If another request already renewed the token, just replay; otherwise renew (once).
      if (this.#token === sentWith) {
        try {
          await this.refresh();
        } catch {
          this.#token = null;
          this.#onSessionLost?.();
          throw await toApiError(response);
        }
      }
      response = await this.#send(method, path, options);
    }

    if (response.status === 204) return undefined as T;
    if (!response.ok) throw await toApiError(response);
    return (await response.json()) as T;
  }
}
