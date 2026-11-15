import { Alert, Stack } from "@mui/material";
import { StateIllustration } from "./StateIllustration";

type ForbiddenStateProps = {
  message?: string;
  showIllustration?: boolean;
};

export function ForbiddenState({
  message = "اجازه مشاهده یا انجام این کار را ندارید.",
  showIllustration = true,
}: ForbiddenStateProps) {
  return (
    <Stack spacing={1.5} alignItems="center" role="alert" sx={{ py: 1 }}>
      {showIllustration ? <StateIllustration kind="forbidden" /> : null}
      <Alert severity="warning" sx={{ width: "100%", maxWidth: 560 }}>
        {message}
      </Alert>
    </Stack>
  );
}
