import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Container,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import {
  apiFetch,
  type InventoryItem,
  type InventoryMovement,
  type Product,
} from "../../shared/api";

export function InventoryPage() {
  const { tenantId = "" } = useParams();
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [movements, setMovements] = useState<InventoryMovement[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [reference, setReference] = useState("");
  const [reason, setReason] = useState("");
  const [mode, setMode] = useState<"receipt" | "adjustment">("receipt");
  const [saving, setSaving] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [stock, ledger, catalog] = await Promise.all([
          apiFetch<InventoryItem[]>(`/api/v1/tenants/${tenantId}/inventory`),
          apiFetch<InventoryMovement[]>(
            `/api/v1/tenants/${tenantId}/inventory/movements?limit=50`,
          ),
          apiFetch<Product[]>(`/api/v1/tenants/${tenantId}/products`),
        ]);
        if (!cancelled) {
          setItems(stock);
          setMovements(ledger);
          setProducts(catalog);
          setProductId((current) => current || catalog[0]?.id || "");
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

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (mode === "receipt") {
        await apiFetch(`/api/v1/tenants/${tenantId}/inventory/receipts`, {
          method: "POST",
          body: JSON.stringify({
            product_id: productId,
            quantity: Number(quantity),
            reference,
          }),
        });
      } else {
        await apiFetch(`/api/v1/tenants/${tenantId}/inventory/adjustments`, {
          method: "POST",
          body: JSON.stringify({
            product_id: productId,
            quantity: Number(quantity),
            reason,
            reference: reference || null,
          }),
        });
      }
      setQuantity("");
      setReference("");
      setReason("");
      setReloadToken((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطا در ثبت موجودی");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>
          موجودی
        </Typography>
        <Stack direction="row" spacing={1}>
          <Button component={RouterLink} to={`/t/${tenantId}/products`}>
            کالاها
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

      <Box component="form" onSubmit={onSubmit} sx={{ mb: 3, display: "grid", gap: 1.5 }}>
        <Typography variant="subtitle1">ثبت رسید / تعدیل</Typography>
        <TextField
          select
          label="نوع"
          value={mode}
          onChange={(e) => setMode(e.target.value as "receipt" | "adjustment")}
        >
          <MenuItem value="receipt">رسید ورود</MenuItem>
          <MenuItem value="adjustment">تعدیل</MenuItem>
        </TextField>
        <TextField
          select
          label="کالا"
          value={productId}
          onChange={(e) => setProductId(e.target.value)}
          required
        >
          {products.map((product) => (
            <MenuItem key={product.id} value={product.id}>
              {product.title} ({product.sku})
            </MenuItem>
          ))}
        </TextField>
        <TextField
          label={mode === "receipt" ? "تعداد (مثبت)" : "تعداد (مثبت یا منفی)"}
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          required
        />
        <TextField
          label="مرجع"
          value={reference}
          onChange={(e) => setReference(e.target.value)}
          required={mode === "receipt"}
        />
        {mode === "adjustment" && (
          <TextField
            label="دلیل (الزامی)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            required
          />
        )}
        <Button type="submit" variant="contained" disabled={saving || !productId}>
          ذخیره
        </Button>
      </Box>

      {loading ? (
        <CircularProgress />
      ) : (
        <>
          <Typography variant="h6" sx={{ mb: 1, fontWeight: 700 }}>
            موقعیت‌های موجودی
          </Typography>
          {items.length === 0 ? (
            <Alert severity="info" sx={{ mb: 3 }}>
              هنوز موجودی ثبت نشده است.
            </Alert>
          ) : (
            <Stack spacing={1} sx={{ mb: 3 }}>
              {items.map((item) => (
                <Box key={`${item.product_id}-${item.warehouse_code}`} sx={{ p: 2, bgcolor: "background.paper" }}>
                  <Typography sx={{ fontWeight: 600 }}>
                    {item.title}{" "}
                    <Box component="span" sx={{ direction: "ltr", display: "inline-block" }}>
                      ({item.sku})
                    </Box>
                  </Typography>
                  <Typography color="text.secondary">
                    فیزیکی: {item.on_hand} · رزرو: {item.reserved} · قابل فروش: {item.available}
                    {item.on_hand <= item.stock_warning_threshold ? " · هشدار کمبود" : ""}
                  </Typography>
                </Box>
              ))}
            </Stack>
          )}

          <Typography variant="h6" sx={{ mb: 1, fontWeight: 700 }}>
            دفتر حرکت موجودی
          </Typography>
          {movements.length === 0 ? (
            <Alert severity="info">حرکتی ثبت نشده است.</Alert>
          ) : (
            <Stack spacing={1}>
              {movements.map((movement) => (
                <Box key={movement.id} sx={{ p: 2, bgcolor: "background.paper" }}>
                  <Typography sx={{ fontWeight: 600 }}>
                    {movement.title} ({movement.sku})
                  </Typography>
                  <Typography color="text.secondary">
                    فیزیکی {movement.physical_delta} · رزرو {movement.reserved_delta} ·{" "}
                    {movement.reason}
                    {movement.reference ? ` · ${movement.reference}` : ""}
                  </Typography>
                </Box>
              ))}
            </Stack>
          )}
        </>
      )}
    </Container>
  );
}
