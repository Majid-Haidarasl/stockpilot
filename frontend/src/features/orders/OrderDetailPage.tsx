import { Box, Button, Stack, Typography } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import {
  apiFetch,
  type Customer,
  type Order,
  type OrderLine,
  type OrderTimelineEvent,
  type Product,
} from "../../shared/api";
import { ProductThumb } from "../../shared/media/ProductThumb";
import { formatRial, toPersianDigits } from "../../shared/money";
import { statusFromQueryError } from "../../shared/pageStatus";
import { queryKeys } from "../../shared/query/keys";
import { formatTehranDateTime } from "../../shared/tehranDisplay";
import { getTenant } from "../../shared/tenant";
import {
  ConfirmDialog,
  DataTable,
  EmptyState,
  ErrorState,
  ForbiddenState,
  LoadingState,
  SectionCard,
  TenantShell,
  type DataTableColumn,
} from "../../shared/ui";
import { allowedOrderActions } from "./allowedActions";
import { OrderTimeline } from "./OrderTimeline";
import { ReservationCountdown } from "./ReservationCountdown";
import { OrderStatusBadge } from "./status";
import { useOrderCycleAction } from "./useOrderCycleAction";

export function OrderDetailPage() {
  const { tenantId = "", orderId = "" } = useParams();
  const role = getTenant()?.role ?? "viewer";
  const [cancelOpen, setCancelOpen] = useState(false);

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

  const productsQuery = useQuery({
    queryKey: queryKeys.products(tenantId),
    queryFn: () => apiFetch<Product[]>(`/api/v1/tenants/${tenantId}/products`),
    enabled: Boolean(tenantId),
  });

  const productThumbById = useMemo(() => {
    const map = new Map<string, string | null>();
    for (const p of productsQuery.data ?? []) {
      map.set(p.id, p.primary_thumbnail_url ?? null);
    }
    return map;
  }, [productsQuery.data]);

  const titleBySku = useMemo(() => {
    const map: Record<string, string> = {};
    for (const line of orderQuery.data?.lines ?? []) {
      map[line.product_sku] = line.product_title;
    }
    return map;
  }, [orderQuery.data?.lines]);

  const cycle = useOrderCycleAction({ tenantId, orderId, titleBySku });

  const listAction = (
    <Button component={RouterLink} to={`/t/${tenantId}/orders`}>
      فهرست
    </Button>
  );

  if (orderQuery.isPending) {
    return (
      <TenantShell title="جزئیات سفارش" actions={listAction}>
        <LoadingState />
      </TenantShell>
    );
  }

  if (orderQuery.isError) {
    const failure = statusFromQueryError(orderQuery.error);
    return (
      <TenantShell title="جزئیات سفارش" actions={listAction}>
        {failure.kind === "forbidden" ? (
          <ForbiddenState message={failure.message} />
        ) : (
          <ErrorState message={failure.message} onRetry={() => void orderQuery.refetch()} />
        )}
      </TenantShell>
    );
  }

  const order = orderQuery.data;
  if (!order) {
    return (
      <TenantShell title="جزئیات سفارش" actions={listAction}>
        <EmptyState message="سفارش یافت نشد." />
      </TenantShell>
    );
  }

  const actions = allowedOrderActions(order.status, role);
  const frozen = order.status !== "DRAFT";
  const customerName =
    customersQuery.data?.find((c) => c.id === order.customer_id)?.name ?? "مشتری";
  const busy = cycle.pendingAction !== null;

  async function onAction(action: "reserve" | "confirm" | "ship") {
    await cycle.run(action, order.version);
  }

  async function onConfirmCancel() {
    setCancelOpen(false);
    await cycle.run("cancel", order.version);
  }

  const lineColumns: DataTableColumn<OrderLine>[] = [
    {
      id: "title",
      header: "کالا",
      render: (line) => (
        <Stack direction="row" spacing={1.5} alignItems="center">
          <ProductThumb
            tenantId={tenantId}
            srcPath={productThumbById.get(line.product_id)}
            alt={line.product_title}
            decorative
          />
          <Box>
            <Typography sx={{ fontWeight: 600 }}>{line.product_title}</Typography>
            <Typography variant="body2" color="text.secondary" dir="ltr">
              {line.product_sku}
            </Typography>
          </Box>
        </Stack>
      ),
    },
    {
      id: "qty",
      header: "تعداد",
      render: (line) => toPersianDigits(String(line.quantity)),
    },
    {
      id: "price",
      header: "قیمت واحد",
      render: (line) => formatRial(line.unit_price.amount),
    },
  ];

  return (
    <TenantShell title="جزئیات سفارش" actions={listAction}>
      <SectionCard>
        <Stack spacing={1.5}>
          <Stack
            direction={{ xs: "column", sm: "row" }}
            spacing={1.5}
            alignItems={{ sm: "center" }}
            justifyContent="space-between"
          >
            <OrderStatusBadge status={order.status} />
            <Typography variant="body2" color="text.secondary" dir="ltr">
              {order.id}
            </Typography>
          </Stack>
          <Typography>مشتری: {customerName}</Typography>
          {order.status === "RESERVED" ? (
            <>
              {order.expires_at ? (
                <Typography variant="body2">
                  مهلت رزرو: {formatTehranDateTime(order.expires_at)}
                </Typography>
              ) : null}
              <ReservationCountdown expiresAt={order.expires_at} />
            </>
          ) : null}
          {cycle.errorMessage ? <ErrorState message={cycle.errorMessage} /> : null}

          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ pt: 1 }}>
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
                onClick={() => setCancelOpen(true)}
                data-testid="action-cancel"
              >
                لغو
              </Button>
            ) : null}
          </Stack>
          {cycle.lastConflictCode === "VERSION_CONFLICT" ? (
            <Typography variant="body2" color="text.secondary">
              داده تازه بارگذاری شد؛ در صورت نیاز دوباره اقدام کنید (ارسال خودکار انجام نمی‌شود).
            </Typography>
          ) : null}
        </Stack>
      </SectionCard>

      <Typography variant="h6" sx={{ mt: 3, mb: 1, fontWeight: 600 }}>
        سطرهای سفارش {frozen ? "(قفل‌شده پس از رزرو)" : ""}
      </Typography>
      <DataTable
        columns={lineColumns}
        rows={order.lines}
        rowKey={(line) => line.id}
        emptyMessage="سطری ثبت نشده است."
        renderMobileRow={(line) => (
          <Stack
            direction="row"
            spacing={1.5}
            sx={{ p: 1.5, border: 1, borderColor: "divider", borderRadius: 1 }}
          >
            <ProductThumb
              tenantId={tenantId}
              srcPath={productThumbById.get(line.product_id)}
              alt={line.product_title}
              decorative
            />
            <Box>
              <Typography sx={{ fontWeight: 600 }}>{line.product_title}</Typography>
              <Typography variant="body2" color="text.secondary" dir="ltr">
                {line.product_sku}
              </Typography>
              <Typography variant="body2">
                تعداد: {toPersianDigits(String(line.quantity))} · قیمت واحد:{" "}
                {formatRial(line.unit_price.amount)}
              </Typography>
            </Box>
          </Stack>
        )}
      />

      <Typography sx={{ my: 2 }}>
        {order.total_is_estimate ? "جمع تخمینی (قیمت جاری): " : "جمع (قیمت فریزشده): "}
        {formatRial(order.total.amount)}
      </Typography>

      <Typography variant="h6" sx={{ mb: 1, fontWeight: 600 }}>
        تاریخچه تغییرات
      </Typography>
      <OrderTimeline
        events={timelineQuery.data}
        loading={timelineQuery.isPending}
        errorMessage={
          timelineQuery.isError ? statusFromQueryError(timelineQuery.error).message : null
        }
      />

      <ConfirmDialog
        open={cancelOpen}
        title="لغو سفارش"
        description="آیا از لغو این سفارش مطمئن هستید؟ موجودی رزروشده آزاد می‌شود."
        confirmLabel="لغو سفارش"
        cancelLabel="انصراف"
        confirmColor="error"
        confirming={cycle.pendingAction === "cancel"}
        onConfirm={() => void onConfirmCancel()}
        onCancel={() => setCancelOpen(false)}
      />
    </TenantShell>
  );
}
