import { Box, Button, Stack, TextField, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { apiFetch, mapApiError, type Customer } from "../../shared/api";
import { statusFromQueryError } from "../../shared/pageStatus";
import { queryKeys } from "../../shared/query/keys";
import {
  DataTable,
  ErrorState,
  ForbiddenState,
  LoadingState,
  SectionCard,
  TenantShell,
  type DataTableColumn,
} from "../../shared/ui";
import { CustomerEditDialog } from "./CustomerEditDialog";
import { filterCustomersBySearch } from "./customersFilter";

export function CustomersPage() {
  const { tenantId = "" } = useParams();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<Customer | null>(null);

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

  const filtered = useMemo(
    () => filterCustomersBySearch(customersQuery.data ?? [], search),
    [customersQuery.data, search],
  );

  if (customersQuery.isPending) {
    return (
      <TenantShell title="مشتریان">
        <LoadingState />
      </TenantShell>
    );
  }

  if (customersQuery.isError) {
    const status = statusFromQueryError(customersQuery.error);
    return (
      <TenantShell title="مشتریان">
        {status.kind === "forbidden" ? (
          <ForbiddenState message={status.message} />
        ) : (
          <ErrorState message={status.message} onRetry={() => void customersQuery.refetch()} />
        )}
      </TenantShell>
    );
  }

  const columns: DataTableColumn<Customer>[] = [
    {
      id: "name",
      header: "نام",
      render: (item) => item.name,
    },
    {
      id: "phone",
      header: "تلفن",
      render: (item) => (
        <Box component="span" dir="ltr" sx={{ display: "inline-block" }}>
          {item.phone ?? "بدون تلفن"}
        </Box>
      ),
    },
    {
      id: "actions",
      header: "عملیات",
      render: (item) => (
        <Button
          size="small"
          onClick={() => setEditing(item)}
          aria-label={`ویرایش ${item.name}`}
        >
          ویرایش
        </Button>
      ),
    },
  ];

  return (
    <TenantShell title="مشتریان">
      {formError ? <ErrorState message={formError} showIllustration={false} /> : null}

      <SectionCard>
        <Box component="form" onSubmit={onCreate} sx={{ display: "grid", gap: 1.5 }}>
          <Typography variant="subtitle1" component="h2" sx={{ fontWeight: 600 }}>
            ثبت مشتری جدید
          </Typography>
          <TextField label="نام" value={name} onChange={(e) => setName(e.target.value)} required />
          <TextField label="تلفن" value={phone} onChange={(e) => setPhone(e.target.value)} />
          <Button type="submit" variant="contained" disabled={createMutation.isPending}>
            ذخیره
          </Button>
        </Box>
      </SectionCard>

      <TextField
        label="جستجوی مشتری"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        sx={{ my: 2, maxWidth: 360 }}
        fullWidth
      />

      <DataTable
        columns={columns}
        rows={filtered}
        rowKey={(item) => item.id}
        emptyMessage="مشتری ثبت نشده است."
        renderMobileRow={(item) => (
          <Stack
            spacing={0.5}
            sx={{ p: 1.5, border: 1, borderColor: "divider", borderRadius: 1 }}
          >
            <Typography sx={{ fontWeight: 600 }}>{item.name}</Typography>
            <Typography variant="body2" color="text.secondary" dir="ltr">
              {item.phone ?? "بدون تلفن"}
            </Typography>
            <Button
              size="small"
              onClick={() => setEditing(item)}
              aria-label={`ویرایش ${item.name}`}
              sx={{ alignSelf: "flex-start" }}
            >
              ویرایش
            </Button>
          </Stack>
        )}
      />

      <CustomerEditDialog
        open={Boolean(editing)}
        tenantId={tenantId}
        customer={editing}
        onClose={() => setEditing(null)}
      />
    </TenantShell>
  );
}
