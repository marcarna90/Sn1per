/** An error returned by (or while reaching) the API. `code` is stable and machine-readable. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  readonly requestId: string | null;

  constructor(
    status: number,
    code: string,
    message: string,
    details: unknown = {},
    requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

interface ErrorEnvelope {
  error: { code: string; message: string; details?: unknown; request_id?: string | null };
}

function isEnvelope(value: unknown): value is ErrorEnvelope {
  if (typeof value !== "object" || value === null || !("error" in value)) return false;
  const error = value.error;
  return (
    typeof error === "object" &&
    error !== null &&
    typeof (error as { code?: unknown }).code === "string" &&
    typeof (error as { message?: unknown }).message === "string"
  );
}

/** Build an ApiError from a failed response, tolerating non-JSON bodies (proxy error pages). */
export async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body: unknown = await response.json();
    if (isEnvelope(body)) {
      const { code, message, details, request_id } = body.error;
      return new ApiError(response.status, code, message, details ?? {}, request_id ?? null);
    }
  } catch {
    // not JSON: fall through to the generic error (never surface raw HTML to users)
  }
  return new ApiError(
    response.status,
    "http_error",
    `Erreur inattendue du serveur (HTTP ${String(response.status)}).`,
  );
}
