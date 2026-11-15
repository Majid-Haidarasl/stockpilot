import { Alert, Stack, Typography } from "@mui/material";
import type { ReactNode } from "react";
import { StateIllustration, type StateIllustrationKind } from "./StateIllustration";

type EmptyStateProps = {
  message: string;
  /** Optional illustration; defaults to "empty". Pass `false` to hide. */
  illustration?: StateIllustrationKind | false;
  action?: ReactNode;
};

export function EmptyState({ message, illustration = "empty", action }: EmptyStateProps) {
  return (
    <Stack spacing={1.5} alignItems="center" sx={{ py: 2, px: 1 }} role="status">
      {illustration ? <StateIllustration kind={illustration} /> : null}
      <Alert
        severity="info"
        sx={{ width: "100%", maxWidth: 480, "& .MuiAlert-message": { width: "100%" } }}
      >
        <Typography component="span">{message}</Typography>
      </Alert>
      {action}
    </Stack>
  );
}
