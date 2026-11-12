import { Box, Stack, Typography } from "@mui/material";
import type { ReactElement } from "react";
import { orderStatusLabel } from "./statusLabels";

function StatusGlyph({ status }: { status: string }): ReactElement {
  const common = {
    width: 18,
    height: 18,
    viewBox: "0 0 24 24",
    "aria-hidden": true as const,
    focusable: false as const,
  };
  switch (status) {
    case "DRAFT":
      return (
        <svg {...common}>
          <path
            fill="currentColor"
            d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm1 7V3.5L18.5 9H15z"
          />
        </svg>
      );
    case "RESERVED":
      return (
        <svg {...common}>
          <path
            fill="currentColor"
            d="M12 1a5 5 0 0 0-5 5v3H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V11a2 2 0 0 0-2-2h-1V6a5 5 0 0 0-5-5zm0 2a3 3 0 0 1 3 3v3H9V6a3 3 0 0 1 3-3z"
          />
        </svg>
      );
    case "CONFIRMED":
      return (
        <svg {...common}>
          <path
            fill="currentColor"
            d="M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4L9 16.2z"
          />
        </svg>
      );
    case "SHIPPED":
      return (
        <svg {...common}>
          <path
            fill="currentColor"
            d="M3 7h11v8H3V7zm12 2h3l3 3v3h-6V9zm-9 9a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm12 0a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"
          />
        </svg>
      );
    case "CANCELLED":
      return (
        <svg {...common}>
          <path
            fill="currentColor"
            d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm4.3 13.3-1.4 1.4L12 13.4l-2.9 2.9-1.4-1.4 2.9-2.9-2.9-2.9 1.4-1.4 2.9 2.9 2.9-2.9 1.4 1.4-2.9 2.9 2.9 2.9z"
          />
        </svg>
      );
    case "EXPIRED":
      return (
        <svg {...common}>
          <path
            fill="currentColor"
            d="M12 2a10 10 0 1 0 .001 20.001A10 10 0 0 0 12 2zm1 11H7v-2h4V6h2v7z"
          />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8" fill="currentColor" />
        </svg>
      );
  }
}

/** Status cue with text + icon (colour alone is never the only signal). */
export function OrderStatusBadge({ status }: { status: string }) {
  const label = orderStatusLabel(status);
  return (
    <Stack
      direction="row"
      spacing={0.75}
      alignItems="center"
      component="span"
      aria-label={`وضعیت: ${label}`}
    >
      <Box component="span" sx={{ display: "inline-flex", color: "text.secondary" }}>
        <StatusGlyph status={status} />
      </Box>
      <Typography component="span" variant="body2" sx={{ fontWeight: 600 }}>
        {label}
      </Typography>
    </Stack>
  );
}
