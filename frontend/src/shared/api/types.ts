/** Domain DTOs used by pages until OpenAPI component schemas are preferred at call sites. */

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

export type InventoryItem = {
  product_id: string;
  sku: string;
  title: string;
  warehouse_code: string;
  on_hand: number;
  reserved: number;
  available: number;
  stock_warning_threshold: number;
  version: number;
};

export type InventoryMovement = {
  id: string;
  product_id: string;
  sku: string;
  title: string;
  physical_delta: number;
  reserved_delta: number;
  reason: string;
  reference: string | null;
  created_at: string;
};

export type MoneyOut = {
  amount: string;
  currency: string;
};

export type OrderLine = {
  id: string;
  product_id: string;
  product_sku: string;
  product_title: string;
  quantity: number;
  unit_price: MoneyOut;
};

export type Order = {
  id: string;
  tenant_id: string;
  customer_id: string;
  status: string;
  version: number;
  lines: OrderLine[];
  total: MoneyOut;
  total_is_estimate: boolean;
  reserved_at?: string | null;
  expires_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type OrderListItem = {
  id: string;
  tenant_id: string;
  customer_id: string;
  status: string;
  version: number;
  created_at?: string | null;
  expires_at?: string | null;
};

export type OrderTimelineEvent = {
  event_type: string;
  occurred_at: string;
  actor_display_name?: string | null;
  from_status?: string | null;
  to_status?: string | null;
};

export type DashboardLowStock = {
  product_id: string;
  sku: string;
  title: string;
  available: number;
  stock_warning_threshold: number;
};

export type Dashboard = {
  order_counts_by_status: Record<string, number>;
  shipped_total: MoneyOut;
  low_stock: DashboardLowStock[];
  range_from: string;
  range_to: string;
};

export type Member = {
  id: string;
  user_id: string;
  role: "admin" | "sales" | "warehouse" | "viewer";
  email?: string | null;
  display_name?: string | null;
};
