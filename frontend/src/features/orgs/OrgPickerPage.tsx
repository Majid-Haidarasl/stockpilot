import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Container,
  List,
  ListItemButton,
  ListItemText,
  Paper,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch, loginUrl, type MeResponse } from "../../shared/api";
import { clearTenant, setTenant } from "../../shared/tenant";

export function OrgPickerPage() {
  const navigate = useNavigate();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    clearTenant();
    apiFetch<MeResponse>("/api/v1/me")
      .then(setMe)
      .catch((err: Error) => {
        setError(err.message);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error || !me) {
    return (
      <Container maxWidth="sm" sx={{ mt: 8 }}>
        <Alert severity="warning" sx={{ mb: 2 }}>
          {error ?? "نشست معتبر نیست"}
        </Alert>
        <Button variant="contained" onClick={() => (window.location.href = loginUrl())}>
          ورود دوباره
        </Button>
      </Container>
    );
  }

  return (
    <Container maxWidth="sm" sx={{ mt: 8 }}>
      <Paper sx={{ p: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
          انتخاب سازمان
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          {me.user.display_name ?? me.user.email ?? me.user.id}
        </Typography>
        {me.organizations.length === 0 ? (
          <Alert severity="info">
            هنوز عضویت سازمانی ندارید. از ابزار ops bootstrap استفاده کنید.
          </Alert>
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
                  navigate(`/t/${org.tenant_id}/products`);
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
