import AdminPanelSettingsOutlinedIcon from "@mui/icons-material/AdminPanelSettingsOutlined";
import Inventory2OutlinedIcon from "@mui/icons-material/Inventory2Outlined";
import PersonOutlineOutlinedIcon from "@mui/icons-material/PersonOutlineOutlined";
import PointOfSaleOutlinedIcon from "@mui/icons-material/PointOfSaleOutlined";
import { Chip, useTheme } from "@mui/material";
import type { ReactElement } from "react";
import { orderStatusTone, type OrderStatusCode } from "../../theme/palette";
import { roleLabel } from "./roleLabels";

/** Map org roles onto existing theme status tones (no ad-hoc colors). */
const ROLE_TONE_STATUS: Record<string, OrderStatusCode> = {
  admin: "CONFIRMED",
  sales: "SHIPPED",
  warehouse: "RESERVED",
  viewer: "DRAFT",
};

function RoleIcon({ role }: { role: string }): ReactElement {
  const props = { fontSize: "small" as const, "aria-hidden": true };
  switch (role) {
    case "admin":
      return <AdminPanelSettingsOutlinedIcon {...props} />;
    case "sales":
      return <PointOfSaleOutlinedIcon {...props} />;
    case "warehouse":
      return <Inventory2OutlinedIcon {...props} />;
    default:
      return <PersonOutlineOutlinedIcon {...props} />;
  }
}

type RoleChipProps = {
  role: string;
  /** Override visible label; defaults to Persian role name. */
  label?: string;
};

/** Role cue with color + text + icon (never color alone). */
export function RoleChip({ role, label }: RoleChipProps) {
  const theme = useTheme();
  const statusKey = ROLE_TONE_STATUS[role] ?? "DRAFT";
  const tone = orderStatusTone(statusKey, theme.palette.mode);
  const text = label ?? roleLabel(role);

  return (
    <Chip
      size="small"
      icon={<RoleIcon role={role} />}
      label={text}
      aria-label={`نقش: ${text}`}
      sx={{
        bgcolor: tone.bg,
        color: tone.fg,
        fontWeight: 600,
        "& .MuiChip-icon": { color: tone.fg },
      }}
    />
  );
}
