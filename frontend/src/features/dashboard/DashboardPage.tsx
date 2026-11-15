import Inventory2OutlinedIcon from "@mui/icons-material/Inventory2Outlined";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import ReceiptLongOutlinedIcon from "@mui/icons-material/ReceiptLongOutlined";
import LocalShippingOutlinedIcon from "@mui/icons-material/LocalShippingOutlined";
import {
  Box,
  Button,
  Chip,
  Skeleton,
  Stack,
  Typography,
} from "@mui/material";
import { AdapterDateFnsJalali } from "@mui/x-date-pickers/AdapterDateFnsJalali";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import {
  apiFetch,
  type Dashboard,
  type DashboardLowStock,
  type OrderListItem,
} from "../../shared/api";
import { formatRial, toPersianDigits } from "../../shared/money";
import { statusFromQueryError } from "../../shared/pageStatus";
import { queryKeys } from "../../shared/query/keys";
import {
  DataTable,
  EmptyState,
  ErrorState,
  ForbiddenState,
  isLowStock,
  LoadingState,
  LowStockMark,
  SectionCard,
  StatCard,
  TenantShell,
  type DataTableColumn,
} from "../../shared/ui";
import { OrderStatusBadge } from "../orders/status";
import {
  dateToTehranYmd,
  tehranDatePresets,
  ymdToUtcNoon,
  type DatePresetId,
} from "./jalaliRange";
import {
  isValidYmdRange,
  tehranDayEndUtcIso,
  tehranDayStartUtcIso,
  todayTehranYmd,
} from "./tehranRange";

const STATUS_ORDER = [
  "DRAFT",
  "RESERVED",
  "CONFIRMED",
  "SHIPPED",
  "CANCELLED",
  "EXPIRED",
] as const;

const RECENT_ORDERS_LIMIT = 5;

function DateRangeFields({
  fromYmd,
  toYmd,
  rangeValid,
  onFrom,
  onTo,
  onPreset,
}: {
  fromYmd: string;
  toYmd: string;
  rangeValid: boolean;
  onFrom: (v: string) => void;
  onTo: (v: string) => void;
  onPreset: (id: DatePresetId) => void;
}) {
  const presets = useMemo(() => tehranDatePresets(), []);
  const fromDate = ymdToUtcNoon(fromYmd);
  const toDate = ymdToUtcNoon(toYmd);

  return (
    <LocalizationProvider dateAdapter={AdapterDateFnsJalali}>
      <Stack spacing={1.25}>
        <Stack direction="row" flexWrap="wrap" useFlexGap spacing={0.75}>
          {presets.map((preset) => (
            <Chip
              key={preset.id}
              label={preset.label}
              size="small"
              clickable
              onClick={() => onPreset(preset.id)}
              variant="outlined"
            />
          ))}
        </Stack>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} useFlexGap>
          <DatePicker
            label="از تاریخ (تهران)"
            value={fromDate}
            onChange={(value) => {
              if (value) onFrom(dateToTehranYmd(value));
            }}
            slotProps={{
              textField: {
                size: "small",
                error: !rangeValid,
                helperText: !rangeValid
                  ? "تاریخ شروع باید قبل یا برابر تاریخ پایان باشد."
                  : " ",
                inputProps: { "aria-label": "از تاریخ به وقت تهران" },
                sx: { minWidth: 180 },
              },
            }}
          />
          <DatePicker
            label="تا تاریخ (تهران)"
            value={toDate}
            onChange={(value) => {
              if (value) onTo(dateToTehranYmd(value));
            }}
            slotProps={{
              textField: {
                size: "small",
                error: !rangeValid,
                inputProps: { "aria-label": "تا تاریخ به وقت تهران" },
                sx: { minWidth: 180 },
              },
            }}
          />
        </Stack>
      </Stack>
    </LocalizationProvider>
  );
}

function DashboardSkeleton() {
  return (
    <Stack spacing={2}>
      <Box
        sx={{
          display: "grid",
          gap: 1.5,
          gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", md: "repeat(4, 1fr)" },
        }}
      >
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} variant="rounded" height={96} />
        ))}
      </Box>
      <Skeleton variant="rounded" height={160} />
      <Skeleton variant="rounded" height={180} />
      <LoadingState />
    </Stack>
  );
}

export function DashboardPage() {
  const { tenantId = "" } = useParams();
  const today = useMemo(() => todayTehranYmd(), []);
  const [fromYmd, setFromYmd] = useState(today);
  const [toYmd, setToYmd] = useState(today);
  const rangeValid = isValidYmdRange(fromYmd, toYmd);

  const fromUtc = rangeValid ? tehranDayStartUtcIso(fromYmd) : "";
  const toUtc = rangeValid ? tehranDayEndUtcIso(toYmd) : "";

  const dashboardQuery = useQuery({
    queryKey: queryKeys.dashboard(tenantId, fromUtc, toUtc),
    queryFn: () => {
      const params = new URLSearchParams({ from: fromUtc, to: toUtc });
      return apiFetch<Dashboard>(`/api/v1/tenants/${tenantId}/dashboard?${params}`);
    },
    enabled: Boolean(tenantId) && rangeValid,
  });

  function applyPreset(id: DatePresetId) {
    const preset = tehranDatePresets().find((p) => p.id === id);
    if (!preset) return;
    setFromYmd(preset.fromYmd);
    setToYmd(preset.toYmd);
  }

  const dateActions = (
    <DateRangeFields
      fromYmd={fromYmd}
      toYmd={toYmd}
      rangeValid={rangeValid}
      onFrom={setFromYmd}
      onTo={setToYmd}
      onPreset={applyPreset}
    />
  );

  return (
    <TenantShell title="داشبورد" actions={dateActions}>
      {!rangeValid ? null : dashboardQuery.isPending ? (
        <DashboardSkeleton />
      ) : dashboardQuery.isError ? (
        statusFromQueryError(dashboardQuery.error).kind === "forbidden" ? (
          <ForbiddenState message={statusFromQueryError(dashboardQuery.error).message} />
        ) : (
          <ErrorState
            message={statusFromQueryError(dashboardQuery.error).message}
            onRetry={() => void dashboardQuery.refetch()}
          />
        )
      ) : (
        <DashboardBody data={dashboardQuery.data} tenantId={tenantId} />
      )}
    </TenantShell>
  );
}

function DashboardBody({
  data,
  tenantId,
}: {
  data: Dashboard | undefined;
  tenantId: string;
}) {
  const recentQuery = useQuery({
    queryKey: queryKeys.recentOrders(tenantId, RECENT_ORDERS_LIMIT),
    queryFn: () => {
      const params = new URLSearchParams({ limit: String(RECENT_ORDERS_LIMIT) });
      return apiFetch<OrderListItem[]>(
        `/api/v1/tenants/${tenantId}/orders?${params.toString()}`,
      );
    },
    enabled: Boolean(tenantId),
  });

  if (!data) {
    return <EmptyState message="داده‌ای برای نمایش نیست." />;
  }

  const counts = data.order_counts_by_status;
  const totalOrders = STATUS_ORDER.reduce((sum, key) => sum + (counts[key] ?? 0), 0);
  const reservedCount = counts.RESERVED ?? 0;
  const lowStockCount = data.low_stock.length;

  const lowStockColumns: DataTableColumn<DashboardLowStock>[] = [
    {
      id: "title",
      header: "کالا",
      render: (row) => row.title,
    },
    {
      id: "sku",
      header: "کد",
      render: (row) => (
        <Box component="span" dir="ltr" sx={{ display: "inline-block" }}>
          {row.sku}
        </Box>
      ),
    },
    {
      id: "available",
      header: "قابل فروش",
      render: (row) => toPersianDigits(String(row.available)),
    },
    {
      id: "threshold",
      header: "آستانه",
      render: (row) => toPersianDigits(String(row.stock_warning_threshold)),
    },
    {
      id: "warn",
      header: "وضعیت",
      render: (row) => (
        <LowStockMark show={isLowStock(row.available, row.stock_warning_threshold)} />
      ),
    },
  ];

  const recent = recentQuery.data ?? [];

  return (
    <Stack spacing={3}>
      <Box
        sx={{
          display: "grid",
          gap: 1.5,
          gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", md: "repeat(4, 1fr)" },
        }}
      >
        <StatCard
          label="تعداد سفارش‌ها"
          value={toPersianDigits(String(totalOrders))}
          icon={<ReceiptLongOutlinedIcon />}
        />
        <StatCard
          label="جمع ارسال‌شده"
          value={formatRial(data.shipped_total.amount)}
          hint="در بازه انتخاب‌شده"
          icon={<LocalShippingOutlinedIcon />}
        />
        <StatCard
          label="سفارش‌های رزروشده"
          value={toPersianDigits(String(reservedCount))}
          icon={<LockOutlinedIcon />}
        />
        <StatCard
          label="کمبود موجودی"
          value={toPersianDigits(String(lowStockCount))}
          icon={<Inventory2OutlinedIcon />}
        />
      </Box>

      <Box
        sx={{
          display: "grid",
          gap: 2,
          gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
          alignItems: "stretch",
        }}
      >
        <SectionCard>
          <Typography variant="h6" component="h2" sx={{ fontWeight: 600, mb: 1.5 }}>
            تعداد سفارش‌ها بر اساس وضعیت
          </Typography>
          {totalOrders === 0 ? (
            <EmptyState message="هنوز سفارشی ثبت نشده است." />
          ) : (
            <Stack direction="row" flexWrap="wrap" useFlexGap spacing={1}>
              {STATUS_ORDER.map((status) => (
                <Stack key={status} direction="row" spacing={0.75} alignItems="center">
                  <OrderStatusBadge status={status} />
                  <Typography variant="body2" color="text.secondary">
                    {toPersianDigits(String(counts[status] ?? 0))}
                  </Typography>
                </Stack>
              ))}
            </Stack>
          )}
        </SectionCard>

        <SectionCard>
          <Stack
            direction="row"
            alignItems="center"
            justifyContent="space-between"
            sx={{ mb: 1.5 }}
          >
            <Typography variant="h6" component="h2" sx={{ fontWeight: 600 }}>
              سفارش‌های اخیر
            </Typography>
            <Button
              component={RouterLink}
              to={`/t/${tenantId}/orders`}
              size="small"
            >
              همه
            </Button>
          </Stack>
          {recentQuery.isPending ? (
            <Skeleton variant="rounded" height={120} />
          ) : recentQuery.isError ? (
            <Typography variant="body2" color="text.secondary">
              بارگذاری سفارش‌های اخیر ممکن نشد.
            </Typography>
          ) : recent.length === 0 ? (
            <EmptyState message="هنوز سفارشی ثبت نشده است." />
          ) : (
            <Stack spacing={1}>
              {recent.map((order) => (
                <Button
                  key={order.id}
                  component={RouterLink}
                  to={`/t/${tenantId}/orders/${order.id}`}
                  variant="text"
                  color="inherit"
                  sx={{
                    justifyContent: "space-between",
                    textAlign: "start",
                    px: 1,
                    py: 1,
                    borderRadius: 1.5,
                    border: 1,
                    borderColor: "divider",
                  }}
                >
                  <Typography variant="body2" sx={{ fontWeight: 600 }} dir="ltr">
                    {order.id.slice(0, 8)}…
                  </Typography>
                  <OrderStatusBadge status={order.status} />
                </Button>
              ))}
            </Stack>
          )}
        </SectionCard>
      </Box>

      <Box>
        <Typography variant="h6" component="h2" sx={{ fontWeight: 600, mb: 1.5 }}>
          کالاهای زیر آستانه هشدار موجودی
        </Typography>
        <DataTable
          columns={lowStockColumns}
          rows={data.low_stock}
          rowKey={(row) => row.product_id}
          emptyMessage="کالایی زیر آستانه هشدار نیست."
          renderMobileRow={(row) => (
            <Box
              sx={{
                p: 1.5,
                border: 1,
                borderColor: "divider",
                borderRadius: 1,
              }}
            >
              <Typography sx={{ fontWeight: 600 }}>{row.title}</Typography>
              <Typography variant="body2" color="text.secondary" dir="ltr">
                {row.sku}
              </Typography>
              <Typography variant="body2">
                قابل فروش: {toPersianDigits(String(row.available))} · آستانه:{" "}
                {toPersianDigits(String(row.stock_warning_threshold))}
              </Typography>
              <LowStockMark show={isLowStock(row.available, row.stock_warning_threshold)} />
            </Box>
          )}
        />
      </Box>
    </Stack>
  );
}
