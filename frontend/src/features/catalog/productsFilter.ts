import type { Product } from "../../shared/api";

export function filterProductsBySearch(items: Product[], search: string): Product[] {
  const q = search.trim().toLowerCase();
  if (!q) return items;
  return items.filter(
    (p) => p.title.toLowerCase().includes(q) || p.sku.toLowerCase().includes(q),
  );
}
