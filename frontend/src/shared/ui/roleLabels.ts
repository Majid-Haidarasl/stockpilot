const ROLE_LABELS: Record<string, string> = {
  admin: "مدیر",
  sales: "فروش",
  warehouse: "انبار",
  viewer: "ناظر",
};

export function roleLabel(role: string): string {
  return ROLE_LABELS[role] ?? role;
}
