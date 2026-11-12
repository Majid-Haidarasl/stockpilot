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
