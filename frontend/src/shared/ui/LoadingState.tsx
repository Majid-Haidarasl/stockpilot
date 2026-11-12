import { Box, CircularProgress, Typography } from "@mui/material";

type LoadingStateProps = {
  message?: string;
};

export function LoadingState({ message = "در حال بارگذاری…" }: LoadingStateProps) {
  return (
    <Box
      role="status"
      aria-live="polite"
      sx={{
        display: "grid",
        placeItems: "center",
        gap: 1.5,
        py: 6,
        width: "100%",
      }}
    >
      <CircularProgress aria-label={message} />
      <Typography color="text.secondary">{message}</Typography>
    </Box>
  );
}
