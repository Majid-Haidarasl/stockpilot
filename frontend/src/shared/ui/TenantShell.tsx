import { AppBar, Box, Button, Container, Stack, Toolbar, Typography } from "@mui/material";
import type { ReactNode } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { getTenant } from "../tenant";

type TenantShellProps = {
  title: string;
  children: ReactNode;
  actions?: ReactNode;
};

export function TenantShell({ title, children, actions }: TenantShellProps) {
  const { tenantId = "" } = useParams();
  const role = getTenant()?.role ?? "";
  const isAdmin = role === "admin";

  const links = [
    { to: `/t/${tenantId}/dashboard`, label: "داشبورد" },
    { to: `/t/${tenantId}/orders`, label: "سفارش‌ها" },
    { to: `/t/${tenantId}/products`, label: "کالاها" },
    { to: `/t/${tenantId}/customers`, label: "مشتریان" },
    { to: `/t/${tenantId}/inventory`, label: "موجودی" },
    { to: `/t/${tenantId}/notifications`, label: "اعلان‌ها" },
  ];
  if (isAdmin) {
    links.push({ to: `/t/${tenantId}/members`, label: "اعضا" });
  }

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "background.default" }}>
      <AppBar position="static" color="transparent" elevation={0} sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Toolbar
          sx={{
            flexWrap: "wrap",
            gap: 1,
            py: 1,
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <Typography variant="h6" component="p" sx={{ fontWeight: 700, m: 0 }}>
            StockPilot
          </Typography>
          <Stack
            direction="row"
            component="nav"
            aria-label="منوی سازمان"
            spacing={0.5}
            useFlexGap
            flexWrap="wrap"
            sx={{ maxWidth: "100%" }}
          >
            {links.map((link) => (
              <Button
                key={link.to}
                component={RouterLink}
                to={link.to}
                size="small"
                sx={{ minHeight: 40 }}
              >
                {link.label}
              </Button>
            ))}
            <Button component={RouterLink} to="/orgs" size="small" sx={{ minHeight: 40 }}>
              تغییر سازمان
            </Button>
          </Stack>
        </Toolbar>
      </AppBar>
      <Container maxWidth="md" sx={{ py: { xs: 2, sm: 4 }, px: { xs: 2, sm: 3 } }}>
        <Stack
          direction={{ xs: "column", sm: "row" }}
          justifyContent="space-between"
          alignItems={{ xs: "stretch", sm: "center" }}
          spacing={1.5}
          sx={{ mb: 2 }}
        >
          <Typography variant="h5" component="h1" sx={{ fontWeight: 700 }}>
            {title}
          </Typography>
          {actions ? (
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {actions}
            </Stack>
          ) : null}
        </Stack>
        {children}
      </Container>
    </Box>
  );
}
