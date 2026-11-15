import { Box, Button, Container, Stack, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import { getTenant } from "../../shared/tenant";
import { PageHeader, StateIllustration } from "../../shared/ui";

type ErrorFallbackPageProps = {
  /** Optional retry (error boundary). Omitted on the static /error route. */
  onReset?: () => void;
};

/**
 * Generic Persian error presentation — never shows message/stack/details.
 */
export function ErrorFallbackPage({ onReset }: ErrorFallbackPageProps) {
  const tenant = getTenant();
  const homeTo = "/";
  const dashboardTo = tenant?.tenantId ? `/t/${tenant.tenantId}/dashboard` : null;

  return (
    <Box
      component="main"
      sx={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        bgcolor: "background.default",
      }}
    >
      <Container maxWidth="sm">
        <Stack spacing={2} alignItems="center" sx={{ textAlign: "center", py: 4 }}>
          <PageHeader title="خطایی رخ داد" />
          <StateIllustration kind="error" />
          <Typography color="text.secondary">
            مشکلی در نمایش این صفحه پیش آمد. لطفاً دوباره تلاش کنید یا به صفحه اصلی بازگردید.
          </Typography>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
            {onReset ? (
              <Button variant="outlined" onClick={onReset}>
                تلاش دوباره
              </Button>
            ) : (
              <Button component={RouterLink} to={homeTo} variant="outlined">
                بازگشت به خانه
              </Button>
            )}
            <Button
              component={RouterLink}
              to={dashboardTo ?? homeTo}
              variant="contained"
              onClick={onReset}
            >
              بازگشت
            </Button>
          </Stack>
        </Stack>
      </Container>
    </Box>
  );
}
