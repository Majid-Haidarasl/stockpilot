export type TenantSelection = {
  tenantId: string;
  name: string;
  role: string;
};

const KEY = "stockpilot.selectedTenant";

export function getTenant(): TenantSelection | null {
  const raw = sessionStorage.getItem(KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as TenantSelection;
  } catch {
    return null;
  }
}

export function setTenant(value: TenantSelection): void {
  sessionStorage.setItem(KEY, JSON.stringify(value));
}

export function clearTenant(): void {
  sessionStorage.removeItem(KEY);
}
