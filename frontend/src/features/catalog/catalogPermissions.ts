/** Catalog write roles match backend can_manage_catalog_writes (admin + sales). */

export function canWriteCatalog(role: string): boolean {
  return role === "admin" || role === "sales";
}
