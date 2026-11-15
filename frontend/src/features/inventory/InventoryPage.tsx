import { Alert, Box, Button, MenuItem, TextField, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  apiFetch,
  mapApiError,
  type InventoryItem,
  type InventoryMovement,
  type Product,
} from "../../shared/api";
import { toPersianDigits } from "../../shared/money";
import { statusFromQueryError } from "../../shared/pageStatus";
import { queryKeys } from "../../shared/query/keys";
import { formatTehranDateTime } from "../../shared/tehranDisplay";
import { getTenant } from "../../shared/tenant";
import {
  DataTable,
  EmptyState,
  ErrorState,
  ForbiddenState,
  isLowStock,
  LoadingState,
  LowStockMark,
  OutOfStockChip,
  SectionCard,
  TenantShell,
  type DataTableColumn,
} from "../../shared/ui";
import { canWriteInventory, INVENTORY_WRITE_DENIED_MESSAGE } from "./inventoryPermissions";

export function InventoryPage() {
  const { tenantId = "" } = useParams();
  const role = getTenant()?.role ?? "viewer";
  const canWrite = canWriteInventory(role);
  const queryClient = useQueryClient();
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [reference, setReference] = useState("");
  const [reason, setReason] = useState("");
  const [mode, setMode] = useState<"receipt" | "adjustment">("receipt");
  const [formError, setFormError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const inventoryQuery = useQuery({
    queryKey: queryKeys.inventory(tenantId),
    queryFn: () => apiFetch<InventoryItem[]>(`/api/v1/tenants/${tenantId}/inventory`),
    enabled: Boolean(tenantId),
  });

  const movementsQuery = useQuery({
    queryKey: queryKeys.inventoryMovements(tenantId),
    queryFn: () =>
      apiFetch<InventoryMovement[]>(`/api/v1/tenants/${tenantId}/inventory/movements?limit=50`),
    enabled: Boolean(tenantId),
  });

  const productsQuery = useQuery({
    queryKey: queryKeys.products(tenantId),
    queryFn: () => apiFetch<Product[]>(`/api/v1/tenants/${tenantId}/products`),
    enabled: Boolean(tenantId) && canWrite,
  });

  useEffect(() => {
    const first = productsQuery.data?.[0]?.id;
    if (first) {
      setProductId((current) => current || first);
    }
  }, [productsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!canWrite) {
        throw new Error(INVENTORY_WRITE_DENIED_MESSAGE);
      }
      if (mode === "receipt") {
        await apiFetch(`/api/v1/tenants/${tenantId}/inventory/receipts`, {
          method: "POST",
          body: JSON.stringify({
            product_id: productId,
            quantity: Number(quantity),
            reference,
          }),
        });
      } else {
        await apiFetch(`/api/v1/tenants/${tenantId}/inventory/adjustments`, {
          method: "POST",
          body: JSON.stringify({
            product_id: productId,
            quantity: Number(quantity),
            reason,
            reference: reference || null,
          }),
        });
      }
    },
    onSuccess: async () => {
      setQuantity("");
      setReference("");
      setReason("");
      setFormError(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.inventory(tenantId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.inventoryMovements(tenantId) }),
      ]);
    },
    onError: (err) => {
      setFormError(mapApiError(err));
    },
  });

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    await saveMutation.mutateAsync();
  }

  const filteredItems = useMemo(() => {
    const items = inventoryQuery.data ?? [];
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (item) => item.title.toLowerCase().includes(q) || item.sku.toLowerCase().includes(q),
    );
  }, [inventoryQuery.data, search]);

  const loading = inventoryQuery.isPending || movementsQuery.isPending;
  const firstError = inventoryQuery.error ?? movementsQuery.error;

  if (loading) {
    return (
      <TenantShell title="موجودی">
        <LoadingState />
      </TenantShell>
    );
  }

  if (firstError) {
    const status = statusFromQueryError(firstError);
    return (
      <TenantShell title="موجودی">
        {status.kind === "forbidden" ? (
          <ForbiddenState message={status.message} />
        ) : (
          <ErrorState
            message={status.message}
            onRetry={() => {
              void inventoryQuery.refetch();
              void movementsQuery.refetch();
            }}
          />
        )}
      </TenantShell>
    );
  }

  const movements = movementsQuery.data ?? [];
  const products = productsQuery.data ?? [];

  const positionColumns: DataTableColumn<InventoryItem>[] = [
    {
      id: "title",
      header: "کالا",
      render: (item) => (
        <Box>
          <Typography sx={{ fontWeight: 600 }}>{item.title}</Typography>
          <Typography variant="body2" color="text.secondary" dir="ltr">
            {item.sku}
          </Typography>
        </Box>
      ),
    },
    {
      id: "on_hand",
      header: "فیزیکی",
      render: (item) => toPersianDigits(String(item.on_hand)),
    },
    {
      id: "reserved",
      header: "رزرو",
      render: (item) => toPersianDigits(String(item.reserved)),
    },
    {
      id: "available",
      header: "قابل فروش",
      render: (item) => toPersianDigits(String(item.available)),
    },
    {
      id: "stock_status",
      header: "وضعیت",
      render: (item) => (
        <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", alignItems: "center" }}>
          <OutOfStockChip show={item.available <= 0} />
          <LowStockMark
            show={item.available > 0 && isLowStock(item.available, item.stock_warning_threshold)}
          />
        </Box>
      ),
    },
  ];

  const movementColumns: DataTableColumn<InventoryMovement>[] = [
    {
      id: "title",
      header: "کالا",
      render: (m) => (
        <Box>
          <Typography sx={{ fontWeight: 600 }}>{m.title}</Typography>
          <Typography variant="body2" color="text.secondary" dir="ltr">
            {m.sku}
          </Typography>
        </Box>
      ),
    },
    {
      id: "physical",
      header: "فیزیکی",
      render: (m) => toPersianDigits(String(m.physical_delta)),
    },
    {
      id: "reserved",
      header: "رزرو",
      render: (m) => toPersianDigits(String(m.reserved_delta)),
    },
    {
      id: "reason",
      header: "دلیل",
      render: (m) => m.reason,
    },
    {
      id: "when",
      header: "زمان",
      render: (m) => formatTehranDateTime(m.created_at),
    },
  ];

  return (
    <TenantShell title="موجودی">
      {formError ? (
        <Box sx={{ mb: 2 }}>
          <ErrorState message={formError} />
        </Box>
      ) : null}

      {canWrite ? (
        <SectionCard>
          <Box component="form" onSubmit={(e) => void onSubmit(e)} sx={{ display: "grid", gap: 1.5 }}>
            <Typography variant="subtitle1" component="h2" sx={{ fontWeight: 600 }}>
              ثبت رسید / تعدیل
            </Typography>
            <TextField
              select
              label="نوع"
              value={mode}
              onChange={(e) => setMode(e.target.value as "receipt" | "adjustment")}
            >
              <MenuItem value="receipt">رسید ورود</MenuItem>
              <MenuItem value="adjustment">تعدیل</MenuItem>
            </TextField>
            <TextField
              select
              label="کالا"
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
              required
            >
              {products.map((product) => (
                <MenuItem key={product.id} value={product.id}>
                  {product.title} ({product.sku})
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label={mode === "receipt" ? "تعداد (مثبت)" : "تعداد (مثبت یا منفی)"}
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              required
            />
            <TextField
              label="مرجع"
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              required={mode === "receipt"}
            />
            {mode === "adjustment" ? (
              <TextField
                label="دلیل (الزامی)"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                required
              />
            ) : null}
            <Button type="submit" variant="contained" disabled={saveMutation.isPending || !productId}>
              ذخیره
            </Button>
          </Box>
        </SectionCard>
      ) : (
        <Alert severity="warning" sx={{ mb: 3 }} role="status" data-testid="inventory-write-denied">
          {INVENTORY_WRITE_DENIED_MESSAGE}
        </Alert>
      )}

      <Typography variant="h6" component="h2" sx={{ mt: 3, mb: 1, fontWeight: 700 }}>
        موقعیت‌های موجودی
      </Typography>
      <TextField
        label="جستجوی موجودی"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        sx={{ mb: 2, maxWidth: 360 }}
        fullWidth
      />
      <DataTable
        columns={positionColumns}
        rows={filteredItems}
        rowKey={(item) => `${item.product_id}-${item.warehouse_code}`}
        emptyMessage="هنوز موجودی ثبت نشده است."
        renderMobileRow={(item) => (
          <Box sx={{ p: 1.5, border: 1, borderColor: "divider", borderRadius: 1 }}>
            <Typography sx={{ fontWeight: 600 }}>
              {item.title}{" "}
              <Box component="span" sx={{ direction: "ltr", display: "inline-block" }}>
                ({item.sku})
              </Box>
            </Typography>
            <Typography color="text.secondary" variant="body2">
              فیزیکی: {toPersianDigits(String(item.on_hand))} · رزرو:{" "}
              {toPersianDigits(String(item.reserved))} · قابل فروش:{" "}
              {toPersianDigits(String(item.available))}
            </Typography>
            <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", mt: 0.5 }}>
              <OutOfStockChip show={item.available <= 0} />
              <LowStockMark
                show={item.available > 0 && isLowStock(item.available, item.stock_warning_threshold)}
              />
            </Box>
          </Box>
        )}
      />

      <Typography variant="h6" component="h2" sx={{ mt: 3, mb: 1, fontWeight: 700 }}>
        دفتر حرکت موجودی
      </Typography>
      {movements.length === 0 ? (
        <EmptyState message="حرکتی ثبت نشده است." />
      ) : (
        <DataTable
          columns={movementColumns}
          rows={movements}
          rowKey={(m) => m.id}
          renderMobileRow={(m) => (
            <Box sx={{ p: 1.5, border: 1, borderColor: "divider", borderRadius: 1 }}>
              <Typography sx={{ fontWeight: 600 }}>
                {m.title} ({m.sku})
              </Typography>
              <Typography color="text.secondary" variant="body2">
                فیزیکی {toPersianDigits(String(m.physical_delta))} · رزرو{" "}
                {toPersianDigits(String(m.reserved_delta))} · {m.reason}
                {m.reference ? ` · ${m.reference}` : ""}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {formatTehranDateTime(m.created_at)}
              </Typography>
            </Box>
          )}
        />
      )}
    </TenantShell>
  );
}
