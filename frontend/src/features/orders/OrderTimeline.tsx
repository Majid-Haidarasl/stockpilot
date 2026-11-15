import CancelOutlinedIcon from "@mui/icons-material/CancelOutlined";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import HourglassBottomOutlinedIcon from "@mui/icons-material/HourglassBottomOutlined";
import LocalShippingOutlinedIcon from "@mui/icons-material/LocalShippingOutlined";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import { Box, Stack, Typography } from "@mui/material";
import type { ReactElement } from "react";
import type { OrderTimelineEvent } from "../../shared/api";
import { formatTehranDateTime } from "../../shared/tehranDisplay";
import { EmptyState } from "../../shared/ui/EmptyState";
import { ErrorState } from "../../shared/ui/ErrorState";
import { LoadingState } from "../../shared/ui/LoadingState";
import { SectionCard } from "../../shared/ui/SectionCard";
import { EVENT_LABELS } from "./eventLabels";
import { orderStatusLabel } from "./statusLabels";

function EventIcon({ eventType }: { eventType: string }): ReactElement {
  const props = { fontSize: "small" as const, "aria-hidden": true };
  switch (eventType) {
    case "order.draft_created":
      return <DescriptionOutlinedIcon {...props} />;
    case "order.draft_updated":
      return <EditOutlinedIcon {...props} />;
    case "order.reserved":
      return <LockOutlinedIcon {...props} />;
    case "order.confirmed":
      return <CheckCircleOutlineIcon {...props} />;
    case "order.cancelled":
      return <CancelOutlinedIcon {...props} />;
    case "order.shipped":
      return <LocalShippingOutlinedIcon {...props} />;
    case "order.expired":
      return <HourglassBottomOutlinedIcon {...props} />;
    default:
      return <DescriptionOutlinedIcon {...props} />;
  }
}

type OrderTimelineProps = {
  events: OrderTimelineEvent[] | undefined;
  loading?: boolean;
  errorMessage?: string | null;
};

export function OrderTimeline({ events, loading = false, errorMessage = null }: OrderTimelineProps) {
  if (loading) {
    return <LoadingState message="در حال بارگذاری تاریخچه…" />;
  }
  if (errorMessage) {
    return <ErrorState message={errorMessage} />;
  }
  if (!events || events.length === 0) {
    return <EmptyState message="رویدادی ثبت نشده است." />;
  }

  return (
    <SectionCard>
      <Stack component="ol" spacing={0} sx={{ listStyle: "none", m: 0, p: 0 }}>
        {events.map((event, index) => (
          <Box
            key={`${event.event_type}-${event.occurred_at}-${index}`}
            component="li"
            sx={{
              display: "flex",
              gap: 1.5,
              pb: index === events.length - 1 ? 0 : 2,
              position: "relative",
              "&::before":
                index === events.length - 1
                  ? undefined
                  : {
                      content: '""',
                      position: "absolute",
                      right: 11,
                      top: 28,
                      bottom: 0,
                      width: 2,
                      bgcolor: "divider",
                    },
            }}
          >
            <Box
              sx={{
                width: 24,
                height: 24,
                borderRadius: "50%",
                bgcolor: "action.hover",
                color: "primary.main",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                zIndex: 1,
              }}
            >
              <EventIcon eventType={event.event_type} />
            </Box>
            <Stack spacing={0.25} sx={{ minWidth: 0 }}>
              <Typography sx={{ fontWeight: 600 }}>
                {EVENT_LABELS[event.event_type] ?? event.event_type}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {event.actor_display_name ?? "سامانه"} · {formatTehranDateTime(event.occurred_at)}
              </Typography>
              {event.from_status || event.to_status ? (
                <Typography variant="body2">
                  {event.from_status ? orderStatusLabel(event.from_status) : "—"} ←{" "}
                  {event.to_status ? orderStatusLabel(event.to_status) : "—"}
                </Typography>
              ) : null}
            </Stack>
          </Box>
        ))}
      </Stack>
    </SectionCard>
  );
}
