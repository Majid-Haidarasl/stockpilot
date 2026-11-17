import {
  Box,
  Button,
  Chip,
  List,
  ListItemButton,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { statusFromQueryError } from "../../shared/pageStatus";
import { queryKeys } from "../../shared/query/keys";
import { formatTehranDateTime } from "../../shared/tehranDisplay";
import {
  EmptyState,
  ErrorState,
  ForbiddenState,
  LoadingState,
  TenantShell,
} from "../../shared/ui";
import {
  listNotifications,
  markNotificationRead,
  notificationsRefetch,
  type Notification,
} from "./api";
import { notificationTypeLabel } from "./eventLabels";

const PAGE_SIZE = 50;

function orderIdFrom(n: Notification): string | null {
  const raw = n.data?.order_id;
  return typeof raw === "string" && raw.length > 0 ? raw : null;
}

export function NotificationsPage() {
  const { tenantId = "" } = useParams();
  const queryClient = useQueryClient();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [cursor, setCursor] = useState<{ created_at: string; id: string } | null>(null);
  const [pages, setPages] = useState<Notification[][]>([]);

  const listQuery = useQuery({
    queryKey: queryKeys.notifications(tenantId, unreadOnly, cursor?.id ?? null),
    queryFn: () =>
      listNotifications(tenantId, {
        limit: PAGE_SIZE,
        unreadOnly,
        cursorCreatedAt: cursor?.created_at,
        cursorId: cursor?.id,
      }),
    enabled: Boolean(tenantId),
    ...notificationsRefetch,
  });

  const markRead = useMutation({
    mutationFn: (id: string) => markNotificationRead(tenantId, id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["tenant", tenantId, "notifications"],
      });
    },
  });

  const items = useMemo(() => {
    const fromQuery = listQuery.data ?? [];
    if (!cursor) return fromQuery;
    return [...pages.flat(), ...fromQuery];
  }, [cursor, listQuery.data, pages]);

  function onFilterChange(nextUnreadOnly: boolean) {
    setUnreadOnly(nextUnreadOnly);
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

  async function onRowActivate(n: Notification) {
    if (!n.read_at) {
      try {
        await markRead.mutateAsync(n.id);
      } catch {
        /* error surfaced via mutation; keep row clickable */
      }
    }
  }

  if (listQuery.isPending && !cursor) {
    return (
      <TenantShell title="اعلان‌ها" subtitle="صندوق اعلان‌های سازمان">
        <LoadingState />
      </TenantShell>
    );
  }

  if (listQuery.isError) {
    const failure = statusFromQueryError(listQuery.error);
    return (
      <TenantShell title="اعلان‌ها" subtitle="صندوق اعلان‌های سازمان">
        {failure.kind === "forbidden" ? (
          <ForbiddenState message={failure.message} />
        ) : (
          <ErrorState message={failure.message} onRetry={() => void listQuery.refetch()} />
        )}
      </TenantShell>
    );
  }

  const page = listQuery.data ?? [];
  const canLoadMore = page.length >= PAGE_SIZE;

  return (
    <TenantShell title="اعلان‌ها" subtitle="صندوق اعلان‌های سازمان">
      <Stack spacing={2}>
        <Stack direction="row" spacing={1}>
          <Chip
            label="همه"
            color={!unreadOnly ? "primary" : "default"}
            onClick={() => onFilterChange(false)}
            clickable
          />
          <Chip
            label="خوانده‌نشده"
            color={unreadOnly ? "primary" : "default"}
            onClick={() => onFilterChange(true)}
            clickable
          />
        </Stack>

        {items.length === 0 ? (
          <EmptyState illustration="inbox" message="هنوز اعلانی ندارید." />
        ) : (
          <List disablePadding data-testid="notifications-list">
            {items.map((n) => {
              const orderId = orderIdFrom(n);
              const unread = !n.read_at;
              return (
                <ListItemButton
                  key={n.id}
                  alignItems="flex-start"
                  onClick={() => void onRowActivate(n)}
                  sx={{
                    borderBottom: 1,
                    borderColor: "divider",
                    bgcolor: unread ? "action.hover" : "transparent",
                  }}
                  data-testid={`notification-${n.id}`}
                  data-notification-type={n.type}
                >
                  <ListItemText
                    primary={
                      <Stack direction="row" spacing={1} alignItems="center">
                        <Typography fontWeight={unread ? 700 : 500}>
                          {notificationTypeLabel(n.type)}
                        </Typography>
                        {unread ? (
                          <Chip size="small" label="جدید" color="primary" variant="outlined" />
                        ) : null}
                      </Stack>
                    }
                    secondary={
                      <Box component="span" sx={{ display: "block", mt: 0.5 }}>
                        <Typography variant="body2" color="text.secondary" component="span">
                          {n.created_at ? formatTehranDateTime(n.created_at) : "—"}
                        </Typography>
                        {orderId ? (
                          <Typography variant="body2" component="span" sx={{ display: "block" }}>
                            <RouterLink to={`/t/${tenantId}/orders/${orderId}`}>
                              مشاهده سفارش
                            </RouterLink>
                          </Typography>
                        ) : null}
                      </Box>
                    }
                  />
                </ListItemButton>
              );
            })}
          </List>
        )}

        {canLoadMore ? (
          <Button variant="outlined" onClick={loadMore} disabled={listQuery.isFetching}>
            موارد بیشتر
          </Button>
        ) : null}
      </Stack>
    </TenantShell>
  );
}
