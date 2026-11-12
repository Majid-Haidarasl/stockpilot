import { Box, Stack, TextField, Typography } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { apiFetch, type Dashboard } from "../../shared/api";
import { formatRial, toPersianDigits } from "../../shared/money";
import { statusFromQueryError } from "../../shared/pageStatus";
import { queryKeys } from "../../shared/query/keys";
import {
  EmptyState,
  ErrorState,
  ForbiddenState,
  LoadingState,
  TenantShell,
} from "../../shared/ui";
import { orderStatusLabel } from "../orders/statusLabels";
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

  return (
    <TenantShell title="داشبورد">
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={1.5}
        sx={{ mb: 2 }}
        useFlexGap
      >
        <TextField
          type="date"
          label="از تاریخ (تهران)"
          value={fromYmd}
          onChange={(e) => setFromYmd(e.target.value)}
          InputLabelProps={{ shrink: true }}
          inputProps={{ "aria-label": "از تاریخ به وقت تهران" }}
          error={!rangeValid}
          helperText={!rangeValid ? "تاریخ شروع باید قبل یا برابر تاریخ پایان باشد." : " "}
          sx={{ minWidth: 180 }}
        />
        <TextField
          type="date"
          label="تا تاریخ (تهران)"
          value={toYmd}
          onChange={(e) => setToYmd(e.target.value)}
          InputLabelProps={{ shrink: true }}
          inputProps={{ "aria-label": "تا تاریخ به وقت تهران" }}
          error={!rangeValid}
          sx={{ minWidth: 180 }}
        />
      </Stack>

      {!rangeValid ? null : dashboardQuery.isPending ? (
        <LoadingState />
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
        <DashboardBody data={dashboardQuery.data} />
      )}
    </TenantShell>
  );
}

function DashboardBody({ data }: { data: Dashboard | undefined }) {
  if (!data) {
    return <EmptyState message="داده‌ای برای نمایش نیست." />;
  }

  const counts = data.order_counts_by_status;
  const totalOrders = STATUS_ORDER.reduce((sum, key) => sum + (counts[key] ?? 0), 0);

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h6" component="h2" sx={{ fontWeight: 600, mb: 1 }}>
          تعداد سفارش‌ها بر اساس وضعیت
        </Typography>
        {totalOrders === 0 ? (
          <EmptyState message="هنوز سفارشی ثبت نشده است." />
        ) : (
          <Stack spacing={0.75}>
            {STATUS_ORDER.map((status) => (
              <Typography key={status}>
                {orderStatusLabel(status)}: {toPersianDigits(String(counts[status] ?? 0))}
              </Typography>
            ))}
          </Stack>
        )}
      </Box>

      <Box>
        <Typography variant="h6" component="h2" sx={{ fontWeight: 600, mb: 1 }}>
          جمع مبلغ سفارش‌های ارسال‌شده در بازه
        </Typography>
        <Typography>{formatRial(data.shipped_total.amount)}</Typography>
      </Box>

      <Box>
        <Typography variant="h6" component="h2" sx={{ fontWeight: 600, mb: 1 }}>
          کالاهای زیر آستانه هشدار موجودی
        </Typography>
        {data.low_stock.length === 0 ? (
          <EmptyState message="کالایی زیر آستانه هشدار نیست." />
        ) : (
          <Stack spacing={1}>
            {data.low_stock.map((item) => (
              <Box key={item.product_id} sx={{ p: 1.5, bgcolor: "background.paper", borderRadius: 1 }}>
                <Typography sx={{ fontWeight: 600 }}>{item.title}</Typography>
                <Typography variant="body2" color="text.secondary" dir="ltr">
                  {item.sku}
                </Typography>
                <Typography variant="body2">
                  قابل فروش: {toPersianDigits(String(item.available))} · آستانه:{" "}
                  {toPersianDigits(String(item.stock_warning_threshold))}
                </Typography>
              </Box>
            ))}
          </Stack>
        )}
      </Box>
    </Stack>
  );
}
