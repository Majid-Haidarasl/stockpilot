import { Box, Button, Container, Stack, TextField, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { apiFetch, mapApiError, type Customer } from "../../shared/api";
import { statusFromQueryError } from "../../shared/pageStatus";
import { queryKeys } from "../../shared/query/keys";
import { EmptyState, ErrorState, ForbiddenState, LoadingState } from "../../shared/ui";

export function CustomersPage() {
  const { tenantId = "" } = useParams();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const customersQuery = useQuery({
    queryKey: queryKeys.customers(tenantId),
    queryFn: () => apiFetch<Customer[]>(`/api/v1/tenants/${tenantId}/customers`),
    enabled: Boolean(tenantId),
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      await apiFetch(`/api/v1/tenants/${tenantId}/customers`, {
        method: "POST",
        body: JSON.stringify({ name, phone: phone || null }),
      });
    },
    onSuccess: async () => {
      setName("");
      setPhone("");
      setFormError(null);
      await queryClient.invalidateQueries({ queryKey: queryKeys.customers(tenantId) });
    },
    onError: (err) => {
      setFormError(mapApiError(err));
    },
  });

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    await createMutation.mutateAsync();
  }

  if (customersQuery.isPending) {
    return (
      <Container maxWidth="md" sx={{ py: 4 }}>
        <LoadingState />
      </Container>
    );
  }

  if (customersQuery.isError) {
    const status = statusFromQueryError(customersQuery.error);
    return (
      <Container maxWidth="md" sx={{ py: 4 }}>
        {status.kind === "forbidden" ? (
          <ForbiddenState message={status.message} />
        ) : (
          <ErrorState message={status.message} onRetry={() => void customersQuery.refetch()} />
        )}
      </Container>
    );
  }

  const items = customersQuery.data ?? [];

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

      {formError ? <ErrorState message={formError} /> : null}

      <Box component="form" onSubmit={onCreate} sx={{ mb: 3, display: "grid", gap: 1.5 }}>
        <TextField label="نام" value={name} onChange={(e) => setName(e.target.value)} required />
        <TextField label="تلفن" value={phone} onChange={(e) => setPhone(e.target.value)} />
        <Button type="submit" variant="contained" disabled={createMutation.isPending}>
          ذخیره
        </Button>
      </Box>

      {items.length === 0 ? (
        <EmptyState message="مشتری ثبت نشده است." />
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
