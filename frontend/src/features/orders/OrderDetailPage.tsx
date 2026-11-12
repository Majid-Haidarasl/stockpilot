import { Box, Button, Container, Stack, Typography } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import {
  apiFetch,
  type Customer,
  type Order,
  type OrderTimelineEvent,
} from "../../shared/api";
import { formatRial, toPersianDigits } from "../../shared/money";
import { statusFromQueryError } from "../../shared/pageStatus";
import { queryKeys } from "../../shared/query/keys";
import { getTenant } from "../../shared/tenant";
import { EmptyState, ErrorState, ForbiddenState, LoadingState } from "../../shared/ui";
import { allowedOrderActions } from "./allowedActions";
import { ReservationCountdown } from "./ReservationCountdown";
import { OrderStatusBadge } from "./status";
import { orderStatusLabel } from "./statusLabels";
import { useOrderCycleAction } from "./useOrderCycleAction";

const EVENT_LABELS: Record<string, string> = {
  "order.draft_created": "ایجاد پیش‌نویس",
  "order.draft_updated": "ویرایش پیش‌نویس",
  "order.reserved": "رزرو",
  "order.confirmed": "تأیید",
  "order.cancelled": "لغو",
  "order.shipped": "ارسال",
  "order.expired": "انقضا",
};

export function OrderDetailPage() {
  const { tenantId = "", orderId = "" } = useParams();
  const role = getTenant()?.role ?? "viewer";

  const orderQuery = useQuery({
    queryKey: queryKeys.order(tenantId, orderId),
    queryFn: () => apiFetch<Order>(`/api/v1/tenants/${tenantId}/orders/${orderId}`),
    enabled: Boolean(tenantId && orderId),
  });

  const timelineQuery = useQuery({
    queryKey: queryKeys.orderTimeline(tenantId, orderId),
    queryFn: () =>
      apiFetch<OrderTimelineEvent[]>(
        `/api/v1/tenants/${tenantId}/orders/${orderId}/timeline`,
      ),
    enabled: Boolean(tenantId && orderId),
  });

  const customersQuery = useQuery({
    queryKey: queryKeys.customers(tenantId),
    queryFn: () => apiFetch<Customer[]>(`/api/v1/tenants/${tenantId}/customers`),
    enabled: Boolean(tenantId),
  });

  const titleBySku = useMemo(() => {
    const map: Record<string, string> = {};
    for (const line of orderQuery.data?.lines ?? []) {
      map[line.product_sku] = line.product_title;
    }
    return map;
  }, [orderQuery.data?.lines]);

  const cycle = useOrderCycleAction({ tenantId, orderId, titleBySku });

  if (orderQuery.isPending) {
    return (
      <Container maxWidth="md" sx={{ py: 4 }}>
        <LoadingState />
      </Container>
    );
  }

  if (orderQuery.isError) {
    const failure = statusFromQueryError(orderQuery.error);
    return (
      <Container maxWidth="md" sx={{ py: 4 }}>
        {failure.kind === "forbidden" ? (
          <ForbiddenState message={failure.message} />
        ) : (
          <ErrorState message={failure.message} onRetry={() => void orderQuery.refetch()} />
        )}
      </Container>
    );
  }

  const order = orderQuery.data;
  if (!order) {
    return (
      <Container maxWidth="md" sx={{ py: 4 }}>
        <EmptyState message="سفارش یافت نشد." />
      </Container>
    );
  }

  const actions = allowedOrderActions(order.status, role);
  const frozen = order.status !== "DRAFT";
  const customerName =
    customersQuery.data?.find((c) => c.id === order.customer_id)?.name ?? "مشتری";
  const busy = cycle.pendingAction !== null;

  async function onAction(action: "reserve" | "confirm" | "cancel" | "ship") {
    await cycle.run(action, order.version);
  }

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>
          جزئیات سفارش
        </Typography>
        <Button component={RouterLink} to={`/t/${tenantId}/orders`}>
          فهرست
        </Button>
      </Stack>

      <Stack spacing={1.5} sx={{ mb: 3 }}>
        <OrderStatusBadge status={order.status} />
        <Typography>مشتری: {customerName}</Typography>
        <Typography variant="body2" color="text.secondary" dir="ltr">
          {order.id}
        </Typography>
        {order.status === "RESERVED" ? (
          <>
            {order.expires_at ? (
              <Typography variant="body2">
                مهلت رزرو:{" "}
                <Box component="span" dir="ltr">
                  {order.expires_at}
                </Box>
              </Typography>
            ) : null}
            <ReservationCountdown expiresAt={order.expires_at} />
          </>
        ) : null}
        {cycle.errorMessage ? <ErrorState message={cycle.errorMessage} /> : null}
      </Stack>

      <Typography variant="h6" sx={{ mb: 1, fontWeight: 600 }}>
        سطرهای سفارش {frozen ? "(قفل‌شده پس از رزرو)" : ""}
      </Typography>
      <Stack spacing={1} sx={{ mb: 3 }}>
        {order.lines.map((line) => (
          <Box key={line.id} sx={{ p: 2, bgcolor: "background.paper", borderRadius: 1 }}>
            <Typography sx={{ fontWeight: 600 }}>{line.product_title}</Typography>
            <Typography variant="body2" color="text.secondary" dir="ltr">
              {line.product_sku}
            </Typography>
            <Typography variant="body2">
              تعداد: {toPersianDigits(String(line.quantity))} · قیمت واحد:{" "}
              {formatRial(line.unit_price.amount)}
            </Typography>
          </Box>
        ))}
      </Stack>

      <Typography sx={{ mb: 2 }}>
        {order.total_is_estimate ? "جمع تخمینی (قیمت جاری): " : "جمع (قیمت فریزشده): "}
        {formatRial(order.total.amount)}
      </Typography>

      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 4 }}>
        {actions.reserve ? (
          <Button
            variant="contained"
            disabled={busy}
            onClick={() => void onAction("reserve")}
            data-testid="action-reserve"
          >
            رزرو
          </Button>
        ) : null}
        {actions.confirm ? (
          <Button
            variant="contained"
            disabled={busy}
            onClick={() => void onAction("confirm")}
            data-testid="action-confirm"
          >
            تأیید
          </Button>
        ) : null}
        {actions.ship ? (
          <Button
            variant="contained"
            disabled={busy}
            onClick={() => void onAction("ship")}
            data-testid="action-ship"
          >
            ارسال
          </Button>
        ) : null}
        {actions.cancel ? (
          <Button
            color="error"
            disabled={busy}
            onClick={() => void onAction("cancel")}
            data-testid="action-cancel"
          >
            لغو
          </Button>
        ) : null}
        {cycle.lastConflictCode === "VERSION_CONFLICT" ? (
          <Typography variant="body2" color="text.secondary">
            داده تازه بارگذاری شد؛ در صورت نیاز دوباره اقدام کنید (ارسال خودکار انجام نمی‌شود).
          </Typography>
        ) : null}
      </Stack>

      <Typography variant="h6" sx={{ mb: 1, fontWeight: 600 }}>
        تاریخچه تغییرات
      </Typography>
      {timelineQuery.isPending ? (
        <LoadingState message="در حال بارگذاری تاریخچه…" />
      ) : timelineQuery.isError ? (
        <ErrorState message={statusFromQueryError(timelineQuery.error).message} />
      ) : (timelineQuery.data ?? []).length === 0 ? (
        <EmptyState message="رویدادی ثبت نشده است." />
      ) : (
        <Stack spacing={1} component="ol" sx={{ listStyle: "none", p: 0, m: 0 }}>
          {(timelineQuery.data ?? []).map((event, index) => (
            <Box
              key={`${event.event_type}-${event.occurred_at}-${index}`}
              component="li"
              sx={{ p: 1.5, bgcolor: "background.paper", borderRadius: 1 }}
            >
              <Typography sx={{ fontWeight: 600 }}>
                {EVENT_LABELS[event.event_type] ?? event.event_type}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {event.actor_display_name ?? "سامانه"} ·{" "}
                <Box component="span" dir="ltr">
                  {event.occurred_at}
                </Box>
              </Typography>
              {(event.from_status || event.to_status) && (
                <Typography variant="body2">
                  {event.from_status
                    ? orderStatusLabel(event.from_status)
                    : "—"}{" "}
                  ← {event.to_status ? orderStatusLabel(event.to_status) : "—"}
                </Typography>
              )}
            </Box>
          ))}
        </Stack>
      )}
    </Container>
  );
}
