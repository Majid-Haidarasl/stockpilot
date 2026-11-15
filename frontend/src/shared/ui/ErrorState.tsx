import { Alert, Button, Stack } from "@mui/material";
import { StateIllustration } from "./StateIllustration";

type ErrorStateProps = {
  message: string;
  onRetry?: () => void;
  /** Hide decorative illustration when nested tightly. */
  showIllustration?: boolean;
};

export function ErrorState({ message, onRetry, showIllustration = true }: ErrorStateProps) {
  return (
    <Stack spacing={1.5} alignItems="center" role="alert" sx={{ py: 1 }}>
      {showIllustration ? <StateIllustration kind="error" /> : null}
      <Alert severity="error" sx={{ width: "100%", maxWidth: 560 }}>
        {message}
      </Alert>
      {onRetry ? (
        <Button variant="outlined" onClick={onRetry} sx={{ alignSelf: "center" }}>
          تلاش دوباره
        </Button>
      ) : null}
    </Stack>
  );
}
