import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import CancelOutlinedIcon from "@mui/icons-material/CancelOutlined";
import HourglassBottomOutlinedIcon from "@mui/icons-material/HourglassBottomOutlined";
import LocalShippingOutlinedIcon from "@mui/icons-material/LocalShippingOutlined";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import { Chip, useTheme } from "@mui/material";
import type { ReactElement } from "react";
import { orderStatusTone } from "../../theme/palette";

function StatusIcon({ status }: { status: string }): ReactElement {
  const props = { fontSize: "small" as const, "aria-hidden": true };
  switch (status) {
    case "DRAFT":
      return <DescriptionOutlinedIcon {...props} />;
    case "RESERVED":
      return <LockOutlinedIcon {...props} />;
    case "CONFIRMED":
      return <CheckCircleOutlineIcon {...props} />;
    case "SHIPPED":
      return <LocalShippingOutlinedIcon {...props} />;
    case "CANCELLED":
      return <CancelOutlinedIcon {...props} />;
    case "EXPIRED":
      return <HourglassBottomOutlinedIcon {...props} />;
    default:
      return <DescriptionOutlinedIcon {...props} />;
  }
}

type StatusChipProps = {
  status: string;
  /** Visible Persian label (and used in aria-label). */
  label: string;
};

/** Status cue with color + text label + icon (never color alone). */
export function StatusChip({ status, label }: StatusChipProps) {
  const theme = useTheme();
  const tone = orderStatusTone(status, theme.palette.mode);

  return (
    <Chip
      size="small"
      icon={<StatusIcon status={status} />}
      label={label}
      aria-label={`وضعیت: ${label}`}
      sx={{
        bgcolor: tone.bg,
        color: tone.fg,
        fontWeight: 600,
        "& .MuiChip-icon": { color: tone.fg },
      }}
    />
  );
}
