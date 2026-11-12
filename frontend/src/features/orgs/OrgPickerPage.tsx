import {
  Box,
  Button,
  Container,
  List,
  ListItemButton,
  ListItemText,
  Paper,
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
import { EmptyState, ErrorState, ForbiddenState, LoadingState } from "../../shared/ui";

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
      <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
        <LoadingState />
      </Box>
    );
  }

  if (meQuery.isError) {
    const status = statusFromQueryError(meQuery.error);
    return (
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
    );
  }

  const me = meQuery.data;

  return (
    <Container maxWidth="sm" sx={{ mt: 8 }}>
      <Paper sx={{ p: 3 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" sx={{ mb: 2 }}>
          <Box>
            <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
              انتخاب سازمان
            </Typography>
            <Typography color="text.secondary">
              {me.user.display_name ?? me.user.email ?? me.user.id}
            </Typography>
          </Box>
          <Button variant="outlined" disabled={logoutPending} onClick={() => void logout()}>
            خروج
          </Button>
        </Stack>

        {logoutError ? (
          <Box sx={{ mb: 2 }}>
            <ErrorState message={logoutError} />
          </Box>
        ) : null}

        {me.organizations.length === 0 ? (
          <EmptyState message="هنوز عضویت سازمانی ندارید. از ابزار ops bootstrap استفاده کنید." />
        ) : (
          <List>
            {me.organizations.map((org) => (
              <ListItemButton
                key={org.tenant_id}
                onClick={() => {
                  setTenant({
                    tenantId: org.tenant_id,
                    name: org.name,
                    role: org.role,
                  });
                  navigate(`/t/${org.tenant_id}/orders`);
                }}
              >
                <ListItemText primary={org.name} secondary={`${org.slug} · ${org.role}`} />
              </ListItemButton>
            ))}
          </List>
        )}
      </Paper>
    </Container>
  );
}
