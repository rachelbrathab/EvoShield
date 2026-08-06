/**
 * Minimal API client for the EvoShield backend.
 *
 * The backend is the source of truth: its OpenAPI schema (FastAPI /openapi.json)
 * defines every contract. We hand-write only the few types needed today and
 * will generate a typed client from the OpenAPI spec in Sprint 8.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type HealthPayload = {
  status: "ok" | "degraded";
  version: string;
  environment: string;
  database: "ok" | "unavailable";
  timestamp: string;
};

export type UserProfile = {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  auth_provider: "local" | "github" | "supabase";
  created_at: string | null;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserProfile;
};

/**
 * Error thrown for non-2xx API responses. Carries the backend's error
 * contract: `{"error": {"code": ..., "message": ...}}`.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

type ErrorPayload = { error?: { code?: string; message?: string } };

/**
 * Shared fetch wrapper: JSON in/out, credentials for the session cookie,
 * and normalized errors. All auth endpoints exchange the session via the
 * httpOnly cookie set by the backend.
 */
async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  signal?: AbortSignal,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
      credentials: "include",
      cache: "no-store",
      signal,
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new ApiError(0, "network_error", "Cannot reach the EvoShield API");
  }

  if (!response.ok) {
    let code = "unknown_error";
    let message = `Request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as ErrorPayload;
      code = payload.error?.code ?? code;
      message = payload.error?.message ?? message;
    } catch {
      // Non-JSON error body — keep the generic message.
    }
    throw new ApiError(response.status, code, message);
  }
  return (await response.json()) as T;
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthPayload> {
  return apiFetch<HealthPayload>("/api/v1/health", {}, signal);
}

export async function registerAccount(
  payload: { email: string; password: string; full_name?: string | null },
  signal?: AbortSignal,
): Promise<AuthResponse> {
  return apiFetch<AuthResponse>(
    "/api/v1/auth/register",
    { method: "POST", body: JSON.stringify(payload) },
    signal,
  );
}

export async function login(
  payload: { email: string; password: string },
  signal?: AbortSignal,
): Promise<AuthResponse> {
  return apiFetch<AuthResponse>(
    "/api/v1/auth/login",
    { method: "POST", body: JSON.stringify(payload) },
    signal,
  );
}

export async function logout(signal?: AbortSignal): Promise<void> {
  await apiFetch<unknown>("/api/v1/auth/logout", { method: "POST" }, signal);
}

/**
 * Fetch the current session profile. Throws ApiError(401) when unauthenticated.
 * The session cookie is sent automatically via credentials: "include".
 */
export async function fetchCurrentUser(signal?: AbortSignal): Promise<UserProfile> {
  return apiFetch<UserProfile>("/api/v1/auth/session/check", {}, signal);
}

/** URL to start the GitHub OAuth flow (redirects the browser to GitHub). */
export const githubOAuthUrl = `${API_BASE_URL}/api/v1/auth/oauth/github`;
