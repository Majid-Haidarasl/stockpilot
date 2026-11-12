/** Order cycle actions allowed for status × role (UI only; server enforces). */

export type OrderStatusCode =
  | "DRAFT"
  | "RESERVED"
  | "CONFIRMED"
  | "SHIPPED"
  | "CANCELLED"
  | "EXPIRED";

export type OrgRole = "admin" | "sales" | "warehouse" | "viewer";

export type OrderAction = "reserve" | "confirm" | "cancel" | "ship";

export type AllowedOrderActions = Record<OrderAction, boolean>;

const COMMERCIAL: ReadonlySet<OrgRole> = new Set(["admin", "sales"]);
const SHIPPERS: ReadonlySet<OrgRole> = new Set(["admin", "warehouse"]);

export function allowedOrderActions(
  status: string,
  role: string,
): AllowedOrderActions {
  const r = role as OrgRole;
  const commercial = COMMERCIAL.has(r);
  const shipper = SHIPPERS.has(r);
  return {
    reserve: status === "DRAFT" && commercial,
    confirm: status === "RESERVED" && commercial,
    cancel:
      (status === "DRAFT" || status === "RESERVED" || status === "CONFIRMED") &&
      commercial,
    ship: status === "CONFIRMED" && shipper,
  };
}
