import { Box, Button, Container, Stack, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import { getTenant } from "../../shared/tenant";
import { PageHeader, StateIllustration, TenantShell } from "../../shared/ui";

type NotFoundPageProps = {
  /** When true, render inside TenantShell (unknown /t/:tenantId/* paths). */
  embedded?: boolean;
};

function NotFoundBody({ showHeader }: { showHeader: boolean }) {
  const tenant = getTenant();
  const dashboardTo = tenant?.tenantId ? `/t/${tenant.tenantId}/dashboard` : null;

  return (
    <Stack spacing={2} alignItems="center" sx={{ py: { xs: 4, sm: 6 }, textAlign: "center" }}>
      {showHeader ? <PageHeader title="صفحه یافت نشد" /> : null}
      <StateIllustration kind="notFound" />
      <Typography color="text.secondary" sx={{ maxWidth: 420 }}>
        مسیری که درخواست کرده‌اید وجود ندارد یا منتقل شده است.
      </Typography>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
        <Button component={RouterLink} to="/" variant="outlined">
          بازگشت به خانه
        </Button>
        {dashboardTo ? (
          <Button component={RouterLink} to={dashboardTo} variant="contained">
            بازگشت به داشبورد
          </Button>
        ) : null}
      </Stack>
    </Stack>
  );
}

/** Standalone 404 for top-level unknown routes. */
export function NotFoundPage({ embedded = false }: NotFoundPageProps) {
  if (embedded) {
    return (
      <TenantShell title="صفحه یافت نشد">
        <NotFoundBody showHeader={false} />
      </TenantShell>
    );
  }

  return (
    <Box
      component="main"
      sx={{
        minHeight: "100vh",
        bgcolor: "background.default",
        backgroundImage: (theme) =>
          theme.palette.mode === "light"
            ? `radial-gradient(circle at top right, ${theme.palette.secondary.main}22, transparent 45%), linear-gradient(160deg, ${theme.palette.background.default} 0%, ${theme.palette.divider} 100%)`
            : `radial-gradient(circle at top right, ${theme.palette.primary.main}33, transparent 45%), linear-gradient(160deg, ${theme.palette.background.default} 0%, ${theme.palette.background.paper} 100%)`,
      }}
    >
      <Container maxWidth="sm">
        <NotFoundBody showHeader />
      </Container>
    </Box>
  );
}

export function TenantNotFoundPage() {
  return <NotFoundPage embedded />;
}
