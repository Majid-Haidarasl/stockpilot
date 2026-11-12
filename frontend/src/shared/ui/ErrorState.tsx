import { Alert, Button, Stack } from "@mui/material";

type ErrorStateProps = {
  message: string;
  onRetry?: () => void;
};

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <Stack spacing={1.5} role="alert">
      <Alert severity="error">{message}</Alert>
      {onRetry ? (
        <Button variant="outlined" onClick={onRetry} sx={{ alignSelf: "flex-start" }}>
          تلاش دوباره
        </Button>
      ) : null}
    </Stack>
  );
}
