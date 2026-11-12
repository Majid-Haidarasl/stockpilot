import { Alert } from "@mui/material";

type EmptyStateProps = {
  message: string;
};

export function EmptyState({ message }: EmptyStateProps) {
  return (
    <Alert severity="info" role="status">
      {message}
    </Alert>
  );
}
