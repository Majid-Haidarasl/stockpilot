import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Container,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { apiFetch, type Customer } from "../../shared/api";

export function CustomersPage() {
  const { tenantId = "" } = useParams();
  const [items, setItems] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [saving, setSaving] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await apiFetch<Customer[]>(`/api/v1/tenants/${tenantId}/customers`);
        if (!cancelled) {
          setItems(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "خطا");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [tenantId, reloadToken]);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await apiFetch(`/api/v1/tenants/${tenantId}/customers`, {
        method: "POST",
        body: JSON.stringify({ name, phone: phone || null }),
      });
      setName("");
      setPhone("");
      setReloadToken((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطا در ایجاد مشتری");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>
          مشتریان
        </Typography>
        <Button component={RouterLink} to={`/t/${tenantId}/products`}>
          کالاها
        </Button>
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Box component="form" onSubmit={onCreate} sx={{ mb: 3, display: "grid", gap: 1.5 }}>
        <TextField label="نام" value={name} onChange={(e) => setName(e.target.value)} required />
        <TextField label="تلفن" value={phone} onChange={(e) => setPhone(e.target.value)} />
        <Button type="submit" variant="contained" disabled={saving}>
          ذخیره
        </Button>
      </Box>

      {loading ? (
        <CircularProgress />
      ) : items.length === 0 ? (
        <Alert severity="info">مشتری ثبت نشده است.</Alert>
      ) : (
        <Stack spacing={1}>
          {items.map((item) => (
            <Box key={item.id} sx={{ p: 2, bgcolor: "background.paper", borderRadius: 1 }}>
              <Typography sx={{ fontWeight: 600 }}>{item.name}</Typography>
              <Typography color="text.secondary">{item.phone ?? "بدون تلفن"}</Typography>
            </Box>
          ))}
        </Stack>
      )}
    </Container>
  );
}
