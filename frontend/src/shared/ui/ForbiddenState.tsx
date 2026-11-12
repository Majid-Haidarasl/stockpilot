import { Alert } from "@mui/material";

type ForbiddenStateProps = {
  message?: string;
};

export function ForbiddenState({
  message = "اجازه مشاهده یا انجام این کار را ندارید.",
}: ForbiddenStateProps) {
  return (
    <Alert severity="warning" role="alert">
      {message}
    </Alert>
  );
}
