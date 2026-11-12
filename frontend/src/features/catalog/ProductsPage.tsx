import { Box, Button, Container, Stack, TextField, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { apiFetch, mapApiError, type Product } from "../../shared/api";
import { formatRial } from "../../shared/money";
import { statusFromQueryError } from "../../shared/pageStatus";
import { queryKeys } from "../../shared/query/keys";
import { EmptyState, ErrorState, ForbiddenState, LoadingState } from "../../shared/ui";

export function ProductsPage() {
  const { tenantId = "" } = useParams();
  const queryClient = useQueryClient();
  const [sku, setSku] = useState("");
  const [title, setTitle] = useState("");
  const [price, setPrice] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const productsQuery = useQuery({
    queryKey: queryKeys.products(tenantId),
    queryFn: () => apiFetch<Product[]>(`/api/v1/tenants/${tenantId}/products`),
    enabled: Boolean(tenantId),
  });

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

  if (productsQuery.isPending) {
    return (
      <Container maxWidth="md" sx={{ py: 4 }}>
        <LoadingState />
      </Container>
    );
  }

  if (productsQuery.isError) {
    const status = statusFromQueryError(productsQuery.error);
    return (
      <Container maxWidth="md" sx={{ py: 4 }}>
        {status.kind === "forbidden" ? (
          <ForbiddenState message={status.message} />
        ) : (
          <ErrorState message={status.message} onRetry={() => void productsQuery.refetch()} />
        )}
      </Container>
    );
  }

  const items = productsQuery.data ?? [];

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>
          کالاها
        </Typography>
        <Stack direction="row" spacing={1}>
          <Button component={RouterLink} to={`/t/${tenantId}/orders`}>
            سفارش‌ها
          </Button>
          <Button component={RouterLink} to={`/t/${tenantId}/inventory`}>
            موجودی
          </Button>
          <Button component={RouterLink} to={`/t/${tenantId}/customers`}>
            مشتریان
          </Button>
          <Button component={RouterLink} to="/orgs">
            تغییر سازمان
          </Button>
        </Stack>
      </Stack>

      {formError ? <ErrorState message={formError} /> : null}

      <Box component="form" onSubmit={onCreate} sx={{ mb: 3, display: "grid", gap: 1.5 }}>
        <Typography variant="subtitle1">ایجاد کالای جدید</Typography>
        <TextField label="کد کالا (SKU)" value={sku} onChange={(e) => setSku(e.target.value)} required />
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

      {items.length === 0 ? (
        <EmptyState message="کالایی ثبت نشده است." />
      ) : (
        <Stack spacing={1}>
          {items.map((item) => (
            <Box key={item.id} sx={{ p: 2, bgcolor: "background.paper", borderRadius: 1 }}>
              <Typography sx={{ fontWeight: 600 }}>
                {item.title}{" "}
                <Box component="span" sx={{ direction: "ltr", display: "inline-block" }}>
                  ({item.sku})
                </Box>
              </Typography>
              <Typography color="text.secondary">
                قیمت: {formatRial(item.unit_price.amount)} · نسخه {item.version}
                {item.is_active ? "" : " · غیرفعال"}
              </Typography>
            </Box>
          ))}
        </Stack>
      )}
    </Container>
  );
}
