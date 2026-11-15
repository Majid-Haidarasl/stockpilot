import type { Customer } from "../../shared/api";

export function filterCustomersBySearch(items: Customer[], search: string): Customer[] {
  const q = search.trim().toLowerCase();
  if (!q) return items;
  return items.filter((c) => {
    const name = c.name.toLowerCase();
    const phone = (c.phone ?? "").toLowerCase();
    return name.includes(q) || phone.includes(q);
  });
}
