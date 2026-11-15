import { Box, Button, Stack, TextField, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { apiFetch, mapApiError, type Product } from "../../shared/api";
import { formatRial, toPersianDigits } from "../../shared/money";
import { statusFromQueryError } from "../../shared/pageStatus";
import { queryKeys } from "../../shared/query/keys";
import {
  inventoryToStockMap,
  isOutOfStock,
  useInventoryStockMap,
} from "../../shared/query/useInventoryStockMap";
import {
  DataTable,
  ErrorState,
  ForbiddenState,
  LoadingState,
  OutOfStockChip,
  SectionCard,
  TenantShell,
  type DataTableColumn,
} from "../../shared/ui";
import { filterProductsBySearch } from "./productsFilter";

/** Fixed placeholder for future product thumbnails (Run 5/6). No image logic. */
function ThumbnailPlaceholder() {
  return (
    <Box
      aria-hidden
      sx={{
        width: 40,
        height: 40,
        borderRadius: 1,
        bgcolor: "action.hover",
        border: 1,
        borderColor: "divider",
        flexShrink: 0,
      }}
    />
  );
}

export function ProductsPage() {
  const { tenantId = "" } = useParams();
  const queryClient = useQueryClient();
  const [sku, setSku] = useState("");
  const [title, setTitle] = useState("");
  const [price, setPrice] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const productsQuery = useQuery({
    queryKey: queryKeys.products(tenantId),
    queryFn: () => apiFetch<Product[]>(`/api/v1/tenants/${tenantId}/products`),
    enabled: Boolean(tenantId),
  });

  const inventoryQuery = useInventoryStockMap(tenantId, Boolean(tenantId));
  const stockMap = useMemo(
    () =>
      inventoryQuery.isSuccess
        ? inventoryToStockMap(inventoryQuery.data)
        : new Map(),
    [inventoryQuery.isSuccess, inventoryQuery.data],
  );
  const showStockChips = inventoryQuery.isSuccess;

  const createMutation = useMutation({
    mutationFn: async () => {
      await apiFetch(`/api/v1/tenants/${tenantId}/products`, {
        method: "POST",
        body: JSON.stringify({
          sku,
          title,
          unit_price_rial: price,
          is_active: true,
        }),
      });
    },
    onSuccess: async () => {
      setSku("");
      setTitle("");
      setPrice("");
      setFormError(null);
      await queryClient.invalidateQueries({ queryKey: queryKeys.products(tenantId) });
    },
    onError: (err) => {
      setFormError(mapApiError(err));
    },
  });

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    await createMutation.mutateAsync();
  }

  const filtered = useMemo(
    () => filterProductsBySearch(productsQuery.data ?? [], search),
    [productsQuery.data, search],
  );

  if (productsQuery.isPending) {
    return (
      <TenantShell title="کالاها">
        <LoadingState />
      </TenantShell>
    );
  }

  if (productsQuery.isError) {
    const status = statusFromQueryError(productsQuery.error);
    return (
      <TenantShell title="کالاها">
        {status.kind === "forbidden" ? (
          <ForbiddenState message={status.message} />
        ) : (
          <ErrorState message={status.message} onRetry={() => void productsQuery.refetch()} />
        )}
      </TenantShell>
    );
  }

  const columns: DataTableColumn<Product>[] = [
    {
      id: "thumb",
      header: "",
      render: () => <ThumbnailPlaceholder />,
    },
    {
      id: "title",
      header: "عنوان",
      render: (item) => item.title,
    },
    {
      id: "sku",
      header: "کد کالا",
      render: (item) => (
        <Box component="span" dir="ltr" sx={{ display: "inline-block" }}>
          {item.sku}
        </Box>
      ),
    },
    {
      id: "price",
      header: "قیمت",
      render: (item) => formatRial(item.unit_price.amount),
    },
    {
      id: "stock",
      header: "موجودی",
      render: (item) => {
        if (!showStockChips) return "—";
        const stock = stockMap.get(item.id);
        const qty = stock?.available ?? 0;
        return (
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography component="span">{toPersianDigits(String(qty))}</Typography>
            <OutOfStockChip show={isOutOfStock(stock)} />
          </Stack>
        );
      },
    },
    {
      id: "active",
      header: "وضعیت",
      render: (item) => (item.is_active ? "فعال" : "غیرفعال"),
    },
    {
      id: "version",
      header: "نسخه",
      render: (item) => toPersianDigits(String(item.version)),
    },
  ];

  return (
    <TenantShell title="کالاها">
      {formError ? <ErrorState message={formError} /> : null}

      <SectionCard>
        <Box component="form" onSubmit={onCreate} sx={{ display: "grid", gap: 1.5 }}>
          <Typography variant="subtitle1" component="h2" sx={{ fontWeight: 600 }}>
            ایجاد کالای جدید
          </Typography>
          <TextField
            label="کد کالا (SKU)"
            value={sku}
            onChange={(e) => setSku(e.target.value)}
            required
          />
          <TextField label="عنوان" value={title} onChange={(e) => setTitle(e.target.value)} required />
          <TextField
            label="قیمت (ریال)"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            required
            helperText="عدد صحیح به‌صورت رشته؛ بدون اعشار"
          />
          <Button type="submit" variant="contained" disabled={createMutation.isPending}>
            ذخیره
          </Button>
        </Box>
      </SectionCard>

      <TextField
        label="جستجوی کالا"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        sx={{ my: 2, maxWidth: 360 }}
        fullWidth
      />

      <DataTable
        columns={columns}
        rows={filtered}
        rowKey={(item) => item.id}
        emptyMessage="کالایی ثبت نشده است."
        renderMobileRow={(item) => (
          <Stack
            direction="row"
            spacing={1.5}
            sx={{ p: 1.5, border: 1, borderColor: "divider", borderRadius: 1 }}
          >
            <ThumbnailPlaceholder />
            <Box sx={{ minWidth: 0 }}>
              <Typography sx={{ fontWeight: 600 }}>{item.title}</Typography>
              <Typography variant="body2" color="text.secondary" dir="ltr">
                {item.sku}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {formatRial(item.unit_price.amount)}
                {item.is_active ? "" : " · غیرفعال"}
              </Typography>
              {showStockChips ? (
                <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 0.5 }}>
                  <Typography variant="body2">
                    موجودی: {toPersianDigits(String(stockMap.get(item.id)?.available ?? 0))}
                  </Typography>
                  <OutOfStockChip show={isOutOfStock(stockMap.get(item.id))} />
                </Stack>
              ) : null}
            </Box>
          </Stack>
        )}
      />
    </TenantShell>
  );
}
