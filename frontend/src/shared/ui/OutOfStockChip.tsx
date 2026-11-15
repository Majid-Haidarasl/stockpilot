import Inventory2OutlinedIcon from "@mui/icons-material/Inventory2Outlined";
import { Chip, useTheme } from "@mui/material";
import { OUT_OF_STOCK_TONES } from "../../theme/palette";

export const OUT_OF_STOCK_LABEL = "ناموجود";

type OutOfStockChipProps = {
  /** When false, render nothing. */
  show?: boolean;
};

/** Out-of-stock cue: color + icon + text (never color alone). */
export function OutOfStockChip({ show = true }: OutOfStockChipProps) {
  const theme = useTheme();
  if (!show) return null;
  const tone = OUT_OF_STOCK_TONES[theme.palette.mode];
  return (
    <Chip
      size="small"
      icon={<Inventory2OutlinedIcon fontSize="small" aria-hidden />}
      label={OUT_OF_STOCK_LABEL}
      aria-label={OUT_OF_STOCK_LABEL}
      sx={{
        bgcolor: tone.bg,
        color: tone.fg,
        fontWeight: 600,
        "& .MuiChip-icon": { color: tone.fg },
      }}
    />
  );
}
