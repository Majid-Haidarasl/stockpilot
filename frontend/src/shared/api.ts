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

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string; title?: string };
      detail = body.detail ?? body.title ?? detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
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

export type MeResponse = {
  user: {
    id: string;
    email: string | null;
    display_name: string | null;
  };
  organizations: Array<{
    tenant_id: string;
    slug: string;
    name: string;
    role: string;
    membership_id: string;
  }>;
};

export type Product = {
  id: string;
  tenant_id: string;
  sku: string;
  title: string;
  unit_price: { amount: string; currency: string };
  is_active: boolean;
  stock_warning_threshold: number;
  version: number;
};

export type Customer = {
  id: string;
  tenant_id: string;
  name: string;
  phone: string | null;
  email: string | null;
  notes: string | null;
  version: number;
};
