import {
  Box,
  Button,
  Container,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { apiFetch, type Customer, type OrderListItem } from "../../shared/api";
import { statusFromQueryError } from "../../shared/pageStatus";
import { queryKeys } from "../../shared/query/keys";
import { EmptyState, ErrorState, ForbiddenState, LoadingState } from "../../shared/ui";
import { OrderStatusBadge } from "./status";

const STATUS_FILTERS = [
  { value: "", label: "همه وضعیت‌ها" },
  { value: "DRAFT", label: "پیش‌نویس" },
  { value: "RESERVED", label: "رزروشده" },
  { value: "CONFIRMED", label: "تأییدشده" },
  { value: "SHIPPED", label: "ارسال‌شده" },
  { value: "CANCELLED", label: "لغوشده" },
  { value: "EXPIRED", label: "منقضی‌شده" },
] as const;

const PAGE_SIZE = 20;

export function OrderListPage() {
  const { tenantId = "" } = useParams();
  const [status, setStatus] = useState("");
  const [cursor, setCursor] = useState<{ created_at: string; id: string } | null>(null);
  const [pages, setPages] = useState<OrderListItem[][]>([]);

  const listQuery = useQuery({
    queryKey: [...queryKeys.orders(tenantId, status || null), cursor?.id ?? "first"],
    queryFn: async () => {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
      if (status) params.set("status", status);
      if (cursor?.created_at) params.set("cursor_created_at", cursor.created_at);
      if (cursor?.id) params.set("cursor_id", cursor.id);
      return apiFetch<OrderListItem[]>(
        `/api/v1/tenants/${tenantId}/orders?${params.toString()}`,
      );
    },
    enabled: Boolean(tenantId),
  });

  const customersQuery = useQuery({
    queryKey: queryKeys.customers(tenantId),
    queryFn: () => apiFetch<Customer[]>(`/api/v1/tenants/${tenantId}/customers`),
    enabled: Boolean(tenantId),
  });

  const customerName = useMemo(() => {
    const map = new Map<string, string>();
    for (const c of customersQuery.data ?? []) {
      map.set(c.id, c.name);
    }
    return map;
  }, [customersQuery.data]);

  const items = useMemo(() => {
    const fromQuery = listQuery.data ?? [];
    if (!cursor) return fromQuery;
    return [...pages.flat(), ...fromQuery];
  }, [cursor, listQuery.data, pages]);

  function onStatusChange(next: string) {
    setStatus(next);
    setCursor(null);
    setPages([]);
  }

  function loadMore() {
    const page = listQuery.data ?? [];
    if (page.length === 0) return;
    const last = page[page.length - 1];
    if (!last.created_at) return;
    setPages((prev) => [...prev, page]);
    setCursor({ created_at: last.created_at, id: last.id });
  }

  if (listQuery.isPending && !cursor) {
    return (
      <Container maxWidth="md" sx={{ py: 4 }}>
        <LoadingState />
      </Container>
    );
  }

  if (listQuery.isError) {
    const failure = statusFromQueryError(listQuery.error);
    return (
      <Container maxWidth="md" sx={{ py: 4 }}>
        {failure.kind === "forbidden" ? (
          <ForbiddenState message={failure.message} />
        ) : (
          <ErrorState message={failure.message} onRetry={() => void listQuery.refetch()} />
        )}
      </Container>
    );
  }

  const page = listQuery.data ?? [];
  const hasMore = page.length >= PAGE_SIZE;

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>
          سفارش‌ها
        </Typography>
        <Stack direction="row" spacing={1}>
          <Button component={RouterLink} to={`/t/${tenantId}/orders/new`} variant="contained">
            سفارش جدید
          </Button>
          <Button component={RouterLink} to={`/t/${tenantId}/products`}>
            کالاها
          </Button>
        </Stack>
      </Stack>

      <TextField
        select
        label="وضعیت"
        value={status}
        onChange={(e) => onStatusChange(e.target.value)}
        sx={{ mb: 2, minWidth: 220 }}
      >
        {STATUS_FILTERS.map((opt) => (
          <MenuItem key={opt.value || "all"} value={opt.value}>
            {opt.label}
          </MenuItem>
        ))}
      </TextField>

      {items.length === 0 ? (
        <EmptyState message="سفارشی یافت نشد." />
      ) : (
        <Stack spacing={1}>
          {items.map((order) => (
            <Box
              key={order.id}
              component={RouterLink}
              to={`/t/${tenantId}/orders/${order.id}`}
              sx={{
                p: 2,
                bgcolor: "background.paper",
                borderRadius: 1,
                textDecoration: "none",
                color: "inherit",
                display: "block",
              }}
            >
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Box>
                  <Typography sx={{ fontWeight: 600 }}>
                    {customerName.get(order.customer_id) ?? "مشتری"}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" dir="ltr">
                    {order.id.slice(0, 8)}…
                  </Typography>
                </Box>
                <OrderStatusBadge status={order.status} />
              </Stack>
            </Box>
          ))}
        </Stack>
      )}

      {hasMore ? (
        <Button sx={{ mt: 2 }} onClick={loadMore} disabled={listQuery.isFetching}>
          صفحه بعد
        </Button>
      ) : null}
    </Container>
  );
}
