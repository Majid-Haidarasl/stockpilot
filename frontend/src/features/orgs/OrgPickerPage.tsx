import {
  Avatar,
  Box,
  Button,
  Container,
  Stack,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { apiFetch, loginUrl, type MeResponse } from "../../shared/api";
import { useLogout } from "../../shared/auth/useLogout";
import { statusFromQueryError } from "../../shared/pageStatus";
import { queryKeys } from "../../shared/query/keys";
import { useClearTenantCacheOnOrgSwitch } from "../../shared/query/useClearTenantCacheOnOrgSwitch";
import { setTenant } from "../../shared/tenant";
import { transition } from "../../theme/shape";
import {
  EmptyState,
  ErrorState,
  ForbiddenState,
  LoadingState,
  RoleChip,
} from "../../shared/ui";

function orgInitial(name: string): string {
  const trimmed = name.trim();
  return trimmed ? trimmed.charAt(0) : "?";
}

export function OrgPickerPage() {
  const navigate = useNavigate();
  useClearTenantCacheOnOrgSwitch();
  const { logout, pending: logoutPending, error: logoutError } = useLogout();

  const meQuery = useQuery({
    queryKey: queryKeys.me(),
    queryFn: () => apiFetch<MeResponse>("/api/v1/me"),
  });

  if (meQuery.isPending) {
    return (
      <Box component="main" sx={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
        <LoadingState />
      </Box>
    );
  }

  if (meQuery.isError) {
    const status = statusFromQueryError(meQuery.error);
    return (
      <Box component="main" sx={{ minHeight: "100vh", bgcolor: "background.default" }}>
        <Container maxWidth="sm" sx={{ mt: 8 }}>
          {status.kind === "forbidden" ? (
            <ForbiddenState message={status.message} />
          ) : (
            <ErrorState message={status.message} />
          )}
          <Button
            variant="contained"
            sx={{ mt: 2 }}
            onClick={() => {
              window.location.href = loginUrl();
            }}
          >
            ورود دوباره
          </Button>
        </Container>
      </Box>
    );
  }

  const me = meQuery.data;
  const displayName = me.user.display_name ?? me.user.email ?? me.user.id;

  return (
    <Box
      component="main"
      sx={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        bgcolor: "background.default",
        backgroundImage: (theme) =>
          theme.palette.mode === "light"
            ? `radial-gradient(circle at top right, ${theme.palette.secondary.main}18, transparent 45%),
               linear-gradient(180deg, ${theme.palette.background.default}, ${theme.palette.divider}33)`
            : `radial-gradient(circle at top right, ${theme.palette.primary.main}22, transparent 45%),
               linear-gradient(180deg, ${theme.palette.background.default}, ${theme.palette.background.paper})`,
        py: { xs: 4, sm: 6 },
      }}
    >
      <Container maxWidth="sm">
        <Stack spacing={3} alignItems="stretch">
          <Box textAlign="center">
            <Typography component="h1" variant="h4" sx={{ fontWeight: 800, mb: 0.75 }}>
              سلام، {displayName}
            </Typography>
            <Typography variant="h6" color="text.secondary" sx={{ fontWeight: 500 }}>
              انتخاب سازمان
            </Typography>
          </Box>

          {logoutError ? (
            <ErrorState message={logoutError} showIllustration={false} />
          ) : null}

          {me.organizations.length === 0 ? (
            <EmptyState
              illustration="empty"
              message="هنوز عضویت سازمانی ندارید. از ابزار ops bootstrap استفاده کنید."
            />
          ) : (
            <Stack
              component="ul"
              spacing={1.5}
              aria-label="فهرست سازمان‌ها"
              sx={{ listStyle: "none", m: 0, p: 0 }}
            >
              {me.organizations.map((org) => (
                <Box
                  key={org.tenant_id}
                  component="li"
                  sx={{ listStyle: "none" }}
                >
                  <Button
                    fullWidth
                    variant="outlined"
                    onClick={() => {
                      setTenant({
                        tenantId: org.tenant_id,
                        name: org.name,
                        role: org.role,
                      });
                      navigate(`/t/${org.tenant_id}/dashboard`);
                    }}
                    sx={{
                      justifyContent: "flex-start",
                      textAlign: "start",
                      p: 2,
                      borderRadius: 2,
                      borderColor: "divider",
                      bgcolor: "background.paper",
                      color: "text.primary",
                      gap: 1.5,
                      transition: transition(["transform", "border-color", "box-shadow"]),
                      "&:hover": {
                        borderColor: "primary.main",
                        bgcolor: "background.paper",
                        transform: "translateY(-1px)",
                      },
                    }}
                  >
                    <Avatar
                      aria-hidden
                      sx={{
                        bgcolor: "primary.main",
                        color: "primary.contrastText",
                        fontWeight: 700,
                        width: 48,
                        height: 48,
                      }}
                    >
                      {orgInitial(org.name)}
                    </Avatar>
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography sx={{ fontWeight: 700 }} noWrap>
                        {org.name}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" noWrap>
                        {org.slug}
                      </Typography>
                    </Box>
                    <RoleChip role={org.role} />
                  </Button>
                </Box>
              ))}
            </Stack>
          )}

          <Box textAlign="center">
            <Button variant="text" color="inherit" disabled={logoutPending} onClick={() => void logout()}>
              خروج
            </Button>
          </Box>
        </Stack>
      </Container>
    </Box>
  );
}
