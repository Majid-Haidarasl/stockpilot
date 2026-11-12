import { ApiProblemError, parseApiProblem } from "./problem";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8200";

function csrfToken(): string | null {
  const match = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith("stockpilot_csrf="));
  if (!match) return null;
  return decodeURIComponent(match.split("=").slice(1).join("="));
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  const method = (init.method ?? "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD") {
    const csrf = csrfToken();
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers,
      credentials: "include",
    });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new ApiProblemError({ status: 0, code: "NETWORK_ERROR", title: "Network error" });
    }
    throw error;
  }

  if (!response.ok) {
    const problem = await parseApiProblem(response);
    throw new ApiProblemError(problem);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function loginUrl(returnTo = `${window.location.origin}/orgs`): string {
  const params = new URLSearchParams({ return_to: returnTo });
  return `${API_BASE}/auth/login?${params.toString()}`;
}

export async function logoutRequest(): Promise<{ keycloak_logout_url?: string }> {
  return apiFetch<{ status: string; keycloak_logout_url?: string }>("/api/v1/auth/logout", {
    method: "POST",
  });
}
