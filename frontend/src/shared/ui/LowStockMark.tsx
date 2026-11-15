import WarningAmberOutlinedIcon from "@mui/icons-material/WarningAmberOutlined";
import { Stack, Typography } from "@mui/material";

const LOW_STOCK_LABEL = "هشدار کمبود";

type LowStockMarkProps = {
  /** When false, render nothing. */
  show?: boolean;
};

/** Warning cue for low stock: color + icon + text (never color alone). */
export function LowStockMark({ show = true }: LowStockMarkProps) {
  if (!show) return null;
  return (
    <Stack
      direction="row"
      spacing={0.5}
      alignItems="center"
      component="span"
      sx={{ color: "warning.main", display: "inline-flex" }}
    >
      <WarningAmberOutlinedIcon fontSize="small" aria-hidden />
      <Typography component="span" variant="body2" sx={{ fontWeight: 600, color: "inherit" }}>
        {LOW_STOCK_LABEL}
      </Typography>
    </Stack>
  );
}

export { LOW_STOCK_LABEL };
