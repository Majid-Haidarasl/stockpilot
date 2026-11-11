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
import { apiFetch, type Product } from "../../shared/api";

export function ProductsPage() {
  const { tenantId = "" } = useParams();
  const [items, setItems] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sku, setSku] = useState("");
  const [title, setTitle] = useState("");
  const [price, setPrice] = useState("");
  const [saving, setSaving] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await apiFetch<Product[]>(`/api/v1/tenants/${tenantId}/products`);
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
      await apiFetch(`/api/v1/tenants/${tenantId}/products`, {
        method: "POST",
        body: JSON.stringify({
          sku,
          title,
          unit_price_rial: price,
          is_active: true,
        }),
      });
      setSku("");
      setTitle("");
      setPrice("");
      setReloadToken((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطا در ایجاد کالا");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>
          کالاها
        </Typography>
        <Stack direction="row" spacing={1}>
          <Button component={RouterLink} to={`/t/${tenantId}/customers`}>
            مشتریان
          </Button>
          <Button component={RouterLink} to="/orgs">
            تغییر سازمان
          </Button>
        </Stack>
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Box component="form" onSubmit={onCreate} sx={{ mb: 3, display: "grid", gap: 1.5 }}>
        <Typography variant="subtitle1">ایجاد کالای جدید</Typography>
        <TextField label="کد کالا (SKU)" value={sku} onChange={(e) => setSku(e.target.value)} required />
        <TextField label="عنوان" value={title} onChange={(e) => setTitle(e.target.value)} required />
        <TextField
          label="قیمت (ریال)"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          required
          helperText="عدد صحیح به‌صورت رشته؛ بدون اعشار"
        />
        <Button type="submit" variant="contained" disabled={saving}>
          ذخیره
        </Button>
      </Box>

      {loading ? (
        <CircularProgress />
      ) : items.length === 0 ? (
        <Alert severity="info">کالایی ثبت نشده است.</Alert>
      ) : (
        <Stack spacing={1}>
          {items.map((item) => (
            <Box key={item.id} sx={{ p: 2, bgcolor: "background.paper", borderRadius: 1 }}>
              <Typography sx={{ fontWeight: 600 }}>
                {item.title}{" "}
                <Box component="span" sx={{ direction: "ltr", display: "inline-block" }}>
                  ({item.sku})
                </Box>
              </Typography>
              <Typography color="text.secondary">
                قیمت: {item.unit_price.amount} ریال · نسخه {item.version}
                {item.is_active ? "" : " · غیرفعال"}
              </Typography>
            </Box>
          ))}
        </Stack>
      )}
    </Container>
  );
}
