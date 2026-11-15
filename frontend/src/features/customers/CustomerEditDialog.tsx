import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
} from "@mui/material";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { FormEvent, ReactNode } from "react";
import { useEffect, useId, useRef, useState } from "react";
import { apiFetch, mapApiError, type Customer } from "../../shared/api";
import { isApiProblemError } from "../../shared/api/problem";
import { queryKeys } from "../../shared/query/keys";
import { ErrorState } from "../../shared/ui";

type CustomerEditDialogProps = {
  open: boolean;
  tenantId: string;
  customer: Customer | null;
  onClose: () => void;
};

export function CustomerEditDialog({
  open,
  tenantId,
  customer,
  onClose,
}: CustomerEditDialogProps) {
  const queryClient = useQueryClient();
  const titleId = useId();
  const nameInputRef = useRef<HTMLInputElement>(null);
  const triggerRestoreRef = useRef<HTMLElement | null>(null);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [expectedVersion, setExpectedVersion] = useState(1);

  useEffect(() => {
    if (open && customer) {
      triggerRestoreRef.current = document.activeElement as HTMLElement | null;
      setName(customer.name);
      setPhone(customer.phone ?? "");
      setExpectedVersion(customer.version);
      setFormError(null);
      const t = window.setTimeout(() => nameInputRef.current?.focus(), 0);
      return () => window.clearTimeout(t);
    }
    return undefined;
  }, [open, customer]);

  const mutation = useMutation({
    mutationFn: async () => {
      if (!customer) throw new Error("مشتری انتخاب نشده است.");
      return apiFetch<Customer>(
        `/api/v1/tenants/${tenantId}/customers/${customer.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            expected_version: expectedVersion,
            name: name.trim(),
            phone: phone.trim() || null,
          }),
        },
      );
    },
    onSuccess: async () => {
      setFormError(null);
      await queryClient.invalidateQueries({ queryKey: queryKeys.customers(tenantId) });
      onClose();
    },
    onError: async (err) => {
      setFormError(mapApiError(err));
      if (isApiProblemError(err) && err.problem.code === "VERSION_CONFLICT") {
        await queryClient.invalidateQueries({ queryKey: queryKeys.customers(tenantId) });
        const refreshed = queryClient
          .getQueryData<Customer[]>(queryKeys.customers(tenantId))
          ?.find((c) => c.id === customer?.id);
        if (refreshed) {
          setExpectedVersion(refreshed.version);
          setName(refreshed.name);
          setPhone(refreshed.phone ?? "");
        } else {
          await queryClient.refetchQueries({ queryKey: queryKeys.customers(tenantId) });
        }
      }
    },
  });

  function handleClose() {
    onClose();
    const el = triggerRestoreRef.current;
    if (el && typeof el.focus === "function") {
      window.setTimeout(() => el.focus(), 0);
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    try {
      await mutation.mutateAsync();
    } catch {
      // Error mapped in onError; keep dialog open.
    }
  }

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      aria-labelledby={titleId}
      fullWidth
      maxWidth="xs"
    >
      <DialogTitle id={titleId}>ویرایش مشتری</DialogTitle>
      <BoxForm onSubmit={(e) => void onSubmit(e)}>
        <DialogContent sx={{ display: "grid", gap: 1.5, pt: 1 }}>
          {formError ? <ErrorState message={formError} showIllustration={false} /> : null}
          <TextField
            inputRef={nameInputRef}
            label="نام"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            fullWidth
          />
          <TextField
            label="تلفن"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            fullWidth
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={handleClose} color="inherit">
            انصراف
          </Button>
          <Button type="submit" variant="contained" disabled={mutation.isPending || !name.trim()}>
            ذخیره
          </Button>
        </DialogActions>
      </BoxForm>
    </Dialog>
  );
}

function BoxForm({
  children,
  onSubmit,
}: {
  children: ReactNode;
  onSubmit: (e: FormEvent) => void;
}) {
  return (
    <form onSubmit={onSubmit} style={{ display: "contents" }}>
      {children}
    </form>
  );
}
