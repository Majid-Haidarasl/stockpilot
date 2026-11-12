import pg from "pg";

/** Convert SQLAlchemy-style URL to libpq URL for node-pg. */
function databaseUrl(): string {
  const raw =
    process.env.STOCKPILOT_MIGRATION_DATABASE_URL ??
    process.env.E2E_DATABASE_URL ??
    "";
  if (!raw) {
    throw new Error("STOCKPILOT_MIGRATION_DATABASE_URL is required for e2e DB helpers");
  }
  return raw.replace(/^postgresql\+psycopg:\/\//, "postgresql://");
}

export async function backdateReservation(orderId: string): Promise<void> {
  const client = new pg.Client({ connectionString: databaseUrl() });
  await client.connect();
  try {
    const result = await client.query(
      `UPDATE sales.orders
       SET expires_at = now() - interval '1 minute',
           updated_at = now()
       WHERE id = $1 AND status = 'RESERVED'
       RETURNING id`,
      [orderId],
    );
    if (result.rowCount !== 1) {
      throw new Error(`backdateReservation: no RESERVED order for ${orderId}`);
    }
  } finally {
    await client.end();
  }
}

export async function getAvailableForSku(tenantId: string, sku: string): Promise<number> {
  const client = new pg.Client({ connectionString: databaseUrl() });
  await client.connect();
  try {
    const result = await client.query(
      `SELECT (sp.on_hand - sp.reserved)::int AS available
       FROM inventory.stock_positions sp
       JOIN catalog.products p ON p.id = sp.product_id AND p.tenant_id = sp.tenant_id
       WHERE sp.tenant_id = $1 AND p.sku = $2`,
      [tenantId, sku],
    );
    if (result.rowCount === 0) return 0;
    return Number(result.rows[0].available);
  } finally {
    await client.end();
  }
}
