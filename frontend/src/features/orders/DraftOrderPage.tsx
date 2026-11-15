import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import {
  Box,
  Button,
  IconButton,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import { Link as RouterLink, useNavigate, useParams } from "react-router-dom";
import {
  apiFetch,
  mapApiError,
  type Customer,
  type Order,
  type Product,
} from "../../shared/api";
import { ProductThumb } from "../../shared/media/ProductThumb";
import { formatRial } from "../../shared/money";
import { createIdempotentAction } from "../../shared/mutations/idempotentAction";
import { statusFromQueryError } from "../../shared/pageStatus";
import { queryKeys } from "../../shared/query/keys";
import {
  inventoryToStockMap,
  isOutOfStock,
  useInventoryStockMap,
} from "../../shared/query/useInventoryStockMap";
import {
  EmptyState,
  ErrorState,
  ForbiddenState,
  LoadingState,
  OUT_OF_STOCK_LABEL,
  SectionCard,
  TenantShell,
} from "../../shared/ui";
import {
  hasDraftErrors,
  validateDraftForm,
  type DraftFormErrors,
  type DraftLineInput,
} from "./draftValidation";

function emptyLine(): DraftLineInput {
  return { productId: "", quantity: "1" };
}

const STICKY_FOOTER_HEIGHT_XS = 72;

export function DraftOrderPage() {
  const { tenantId = "" } = useParams();
  const navigate = useNavigate();
  const [customerId, setCustomerId] = useState("");
  const [lines, setLines] = useState<DraftLineInput[]>([emptyLine()]);
  const [fieldErrors, setFieldErrors] = useState<DraftFormErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const createAction = useMemo(() => createIdempotentAction("orders.create"), []);

  const customersQuery = useQuery({
    queryKey: queryKeys.customers(tenantId),
    queryFn: () => apiFetch<Customer[]>(`/api/v1/tenants/${tenantId}/customers`),
    enabled: Boolean(tenantId),
  });

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

  const productsById = useMemo(() => {
    const map = new Map<string, Product>();
    for (const p of productsQuery.data ?? []) {
      map.set(p.id, p);
    }
    return map;
  }, [productsQuery.data]);

  const estimateTotal = useMemo(() => {
    let sum = 0n;
    for (const line of lines) {
      const product = productsById.get(line.productId);
      if (!product || !/^\d+$/.test(line.quantity.trim())) continue;
      sum += BigInt(product.unit_price.amount) * BigInt(line.quantity.trim());
    }
    return sum.toString();
  }, [lines, productsById]);

  const createMutation = useMutation({
    mutationFn: async () => {
      createAction.begin();
      const request = createAction.buildRequest({
        customer_id: customerId,
        lines: lines.map((line) => ({
          product_id: line.productId,
          quantity: Number(line.quantity),
        })),
      });
      return apiFetch<Order>(`/api/v1/tenants/${tenantId}/orders`, {
        method: "POST",
        headers: request.headers,
        body: JSON.stringify(request.body),
      });
    },
    onSuccess: (order) => {
      createAction.clear();
      void navigate(`/t/${tenantId}/orders/${order.id}`);
    },
    onError: (err) => {
      setFormError(mapApiError(err));
    },
  });

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    const errors = validateDraftForm({ customerId, lines });
    setFieldErrors(errors);
    if (hasDraftErrors(errors)) return;
    await createMutation.mutateAsync();
  }

  const listAction = (
    <Button component={RouterLink} to={`/t/${tenantId}/orders`}>
      فهرست سفارش‌ها
    </Button>
  );

  if (customersQuery.isPending || productsQuery.isPending) {
    return (
      <TenantShell title="سفارش پیش‌نویس" actions={listAction}>
        <LoadingState />
      </TenantShell>
    );
  }

  if (customersQuery.isError || productsQuery.isError) {
    const err = customersQuery.error ?? productsQuery.error;
    const failure = statusFromQueryError(err);
    return (
      <TenantShell title="سفارش پیش‌نویس" actions={listAction}>
        {failure.kind === "forbidden" ? (
          <ForbiddenState message={failure.message} />
        ) : (
          <ErrorState message={failure.message} />
        )}
      </TenantShell>
    );
  }

  const customers = customersQuery.data ?? [];
  const products = (productsQuery.data ?? []).filter((p) => p.is_active);

  return (
    <TenantShell title="سفارش پیش‌نویس" actions={listAction}>
      {formError ? <ErrorState message={formError} /> : null}

      {customers.length === 0 || products.length === 0 ? (
        <EmptyState message="برای ایجاد سفارش، مشتری و کالای فعال لازم است." />
      ) : (
        <Box
          component="form"
          onSubmit={(e) => void onSubmit(e)}
          sx={{
            display: "grid",
            gap: 2,
            pb: { xs: `${STICKY_FOOTER_HEIGHT_XS + 16}px`, sm: 10 },
          }}
        >
          <SectionCard>
            <Typography variant="subtitle1" component="h2" sx={{ fontWeight: 600, mb: 1.5 }}>
              مشتری
            </Typography>
            <TextField
              select
              label="مشتری"
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              error={Boolean(fieldErrors.customerId)}
              helperText={fieldErrors.customerId}
              required
              fullWidth
            >
              {customers.map((c) => (
                <MenuItem key={c.id} value={c.id}>
                  {c.name}
                </MenuItem>
              ))}
            </TextField>
          </SectionCard>

          <SectionCard>
            <Typography variant="subtitle1" component="h2" sx={{ fontWeight: 600, mb: 1.5 }}>
              سطرهای سفارش
            </Typography>
            {fieldErrors.lines ? (
              <Typography color="error" variant="body2" sx={{ mb: 1 }}>
                {fieldErrors.lines}
              </Typography>
            ) : null}

            <Stack spacing={1.5}>
              {lines.map((line, index) => {
                const product = productsById.get(line.productId);
                const lineErr = fieldErrors.lineErrors?.[index];
                return (
                  <Stack
                    key={`line-${index}`}
                    direction={{ xs: "column", sm: "row" }}
                    spacing={1}
                    alignItems={{ sm: "flex-start" }}
                  >
                    <TextField
                      select
                      label="کالا"
                      value={line.productId}
                      onChange={(e) => {
                        const next = [...lines];
                        next[index] = { ...line, productId: e.target.value };
                        setLines(next);
                      }}
                      error={Boolean(lineErr?.productId)}
                      helperText={lineErr?.productId}
                      sx={{ flex: 2 }}
                      fullWidth
                    >
                      {products.map((p) => {
                        const oos =
                          showStockChips && isOutOfStock(stockMap.get(p.id));
                        return (
                          <MenuItem key={p.id} value={p.id}>
                            <Stack direction="row" spacing={1} alignItems="center">
                              <ProductThumb
                                tenantId={tenantId}
                                srcPath={p.primary_thumbnail_url}
                                alt={p.title}
                                size={32}
                                decorative
                              />
                              <span>
                                {p.title} ({p.sku})
                                {oos ? ` — ${OUT_OF_STOCK_LABEL}` : ""}
                              </span>
                            </Stack>
                          </MenuItem>
                        );
                      })}
                    </TextField>
                    <TextField
                      label="تعداد"
                      value={line.quantity}
                      onChange={(e) => {
                        const next = [...lines];
                        next[index] = { ...line, quantity: e.target.value };
                        setLines(next);
                      }}
                      error={Boolean(lineErr?.quantity)}
                      helperText={lineErr?.quantity}
                      inputProps={{ inputMode: "numeric", pattern: "[0-9]*" }}
                      sx={{ flex: 1 }}
                    />
                    <Stack
                      direction="row"
                      spacing={1}
                      alignItems="center"
                      sx={{ minWidth: 180, pt: { sm: 1 } }}
                    >
                      <ProductThumb
                        tenantId={tenantId}
                        srcPath={product?.primary_thumbnail_url}
                        alt={product?.title ?? ""}
                        size={32}
                        decorative
                      />
                      <Typography color="text.secondary">
                        {product ? formatRial(product.unit_price.amount) : "—"}
                      </Typography>
                    </Stack>
                    <IconButton
                      aria-label="حذف سطر"
                      onClick={() => setLines(lines.filter((_, i) => i !== index))}
                      disabled={lines.length <= 1}
                    >
                      <DeleteOutlineIcon />
                    </IconButton>
                  </Stack>
                );
              })}
            </Stack>

            <Button
              type="button"
              onClick={() => setLines([...lines, emptyLine()])}
              disabled={lines.length >= 20}
              sx={{ mt: 1.5 }}
            >
              افزودن سطر
            </Button>
          </SectionCard>

          <SectionCard>
            <Typography variant="body2" color="text.secondary">
              جمع تخمینی با قیمت جاری (قبل از رزرو): {formatRial(estimateTotal)}
            </Typography>
          </SectionCard>

          <Box
            sx={{
              position: "sticky",
              bottom: 0,
              zIndex: 2,
              mt: 1,
              py: 1.5,
              px: { xs: 0, sm: 0 },
              bgcolor: "background.default",
              borderTop: 1,
              borderColor: "divider",
              display: "flex",
              justifyContent: "flex-end",
            }}
          >
            <Button type="submit" variant="contained" disabled={createMutation.isPending} fullWidth={false}>
              ذخیره پیش‌نویس
            </Button>
          </Box>
        </Box>
      )}
    </TenantShell>
  );
}
