import { Alert, Box, Button, MenuItem, Stack, TextField, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  apiFetch,
  mapApiError,
  type InventoryItem,
  type InventoryMovement,
  type Product,
} from "../../shared/api";
import { statusFromQueryError } from "../../shared/pageStatus";
import { queryKeys } from "../../shared/query/keys";
import { getTenant } from "../../shared/tenant";
import {
  EmptyState,
  ErrorState,
  ForbiddenState,
  LoadingState,
  TenantShell,
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

  const items = inventoryQuery.data ?? [];
  const movements = movementsQuery.data ?? [];
  const products = productsQuery.data ?? [];

  return (
    <TenantShell title="موجودی">
      {formError ? (
        <Box sx={{ mb: 2 }}>
          <ErrorState message={formError} />
        </Box>
      ) : null}

      {canWrite ? (
        <Box component="form" onSubmit={(e) => void onSubmit(e)} sx={{ mb: 3, display: "grid", gap: 1.5 }}>
          <Typography variant="subtitle1" component="h2">
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
      ) : (
        <Alert severity="warning" sx={{ mb: 3 }} role="status" data-testid="inventory-write-denied">
          {INVENTORY_WRITE_DENIED_MESSAGE}
        </Alert>
      )}

      <Typography variant="h6" component="h2" sx={{ mb: 1, fontWeight: 700 }}>
        موقعیت‌های موجودی
      </Typography>
      <Box sx={{ mb: 3 }}>
        {items.length === 0 ? (
          <EmptyState message="هنوز موجودی ثبت نشده است." />
        ) : (
          <Stack spacing={1}>
            {items.map((item) => (
              <Box
                key={`${item.product_id}-${item.warehouse_code}`}
                sx={{ p: 2, bgcolor: "background.paper", borderRadius: 1 }}
              >
                <Typography sx={{ fontWeight: 600 }}>
                  {item.title}{" "}
                  <Box component="span" sx={{ direction: "ltr", display: "inline-block" }}>
                    ({item.sku})
                  </Box>
                </Typography>
                <Typography color="text.secondary">
                  فیزیکی: {item.on_hand} · رزرو: {item.reserved} · قابل فروش: {item.available}
                  {item.on_hand <= item.stock_warning_threshold ? " · هشدار کمبود" : ""}
                </Typography>
              </Box>
            ))}
          </Stack>
        )}
      </Box>

      <Typography variant="h6" component="h2" sx={{ mb: 1, fontWeight: 700 }}>
        دفتر حرکت موجودی
      </Typography>
      {movements.length === 0 ? (
        <EmptyState message="حرکتی ثبت نشده است." />
      ) : (
        <Stack spacing={1}>
          {movements.map((movement) => (
            <Box key={movement.id} sx={{ p: 2, bgcolor: "background.paper", borderRadius: 1 }}>
              <Typography sx={{ fontWeight: 600 }}>
                {movement.title} ({movement.sku})
              </Typography>
              <Typography color="text.secondary">
                فیزیکی {movement.physical_delta} · رزرو {movement.reserved_delta} · {movement.reason}
                {movement.reference ? ` · ${movement.reference}` : ""}
              </Typography>
            </Box>
          ))}
        </Stack>
      )}
    </TenantShell>
  );
}
