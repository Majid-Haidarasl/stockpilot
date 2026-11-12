import {
  Alert,
  Box,
  Button,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { apiFetch, mapApiError, type MeResponse, type Member } from "../../shared/api";
import { statusFromQueryError } from "../../shared/pageStatus";
import { queryKeys } from "../../shared/query/keys";
import { getTenant } from "../../shared/tenant";
import {
  EmptyState,
  ErrorState,
  ForbiddenState,
  LoadingState,
  TenantShell,
} from "../../shared/ui";
import { isLastAdminDemotion } from "./lastAdmin";

const ROLES = [
  { value: "admin", label: "مدیر" },
  { value: "sales", label: "فروش" },
  { value: "warehouse", label: "انبار" },
  { value: "viewer", label: "ناظر" },
] as const;

export function MembersPage() {
  const { tenantId = "" } = useParams();
  const role = getTenant()?.role ?? "";
  const queryClient = useQueryClient();
  const [draftRoles, setDraftRoles] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);

  const meQuery = useQuery({
    queryKey: queryKeys.me(),
    queryFn: () => apiFetch<MeResponse>("/api/v1/me"),
  });

  const membersQuery = useQuery({
    queryKey: queryKeys.members(tenantId),
    queryFn: () => apiFetch<Member[]>(`/api/v1/tenants/${tenantId}/members`),
    enabled: Boolean(tenantId) && role === "admin",
  });

  const currentUserId = meQuery.data?.user.id ?? "";

  const patchMutation = useMutation({
    mutationFn: async ({ memberId, nextRole }: { memberId: string; nextRole: string }) => {
      return apiFetch(`/api/v1/tenants/${tenantId}/members/${memberId}`, {
        method: "PATCH",
        body: JSON.stringify({ role: nextRole }),
      });
    },
    onSuccess: async () => {
      setFormError(null);
      await queryClient.invalidateQueries({ queryKey: queryKeys.members(tenantId) });
    },
    onError: (err) => {
      setFormError(mapApiError(err));
    },
  });

  const members = useMemo(() => membersQuery.data ?? [], [membersQuery.data]);
  const adminCount = useMemo(
    () => members.filter((m) => m.role === "admin").length,
    [members],
  );

  if (role !== "admin") {
    return (
      <TenantShell title="اعضای سازمان">
        <ForbiddenState message="فقط مدیر سازمان می‌تواند اعضا را مدیریت کند." />
      </TenantShell>
    );
  }

  if (membersQuery.isPending || meQuery.isPending) {
    return (
      <TenantShell title="اعضای سازمان">
        <LoadingState />
      </TenantShell>
    );
  }

  if (membersQuery.isError) {
    const failure = statusFromQueryError(membersQuery.error);
    return (
      <TenantShell title="اعضای سازمان">
        {failure.kind === "forbidden" ? (
          <ForbiddenState message={failure.message} />
        ) : (
          <ErrorState message={failure.message} onRetry={() => void membersQuery.refetch()} />
        )}
      </TenantShell>
    );
  }

  return (
    <TenantShell title="اعضای سازمان">
      <Alert severity="info" sx={{ mb: 2 }} role="status">
        آخرین مدیر فعال سازمان را نمی‌توان به نقش دیگر تغییر داد. این محدودیت هم در رابط و هم در
        سرور اعمال می‌شود.
      </Alert>

      {formError ? (
        <Box sx={{ mb: 2 }}>
          <ErrorState message={formError} />
        </Box>
      ) : null}

      {members.length === 0 ? (
        <EmptyState message="عضوی یافت نشد." />
      ) : (
        <Stack spacing={1.5}>
          {members.map((member) => {
            const selected = draftRoles[member.id] ?? member.role;
            const blocked =
              member.user_id === currentUserId &&
              isLastAdminDemotion(members, member.id, selected);
            const isSelfLastAdmin = member.user_id === currentUserId && adminCount <= 1 && member.role === "admin";

            return (
              <Box
                key={member.id}
                sx={{
                  p: 2,
                  bgcolor: "background.paper",
                  borderRadius: 1,
                  display: "grid",
                  gap: 1.5,
                }}
              >
                <Typography sx={{ fontWeight: 600 }}>
                  {member.display_name ?? member.email ?? member.user_id}
                </Typography>
                {member.email ? (
                  <Typography variant="body2" color="text.secondary" dir="ltr">
                    {member.email}
                  </Typography>
                ) : null}
                <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }}>
                  <TextField
                    select
                    label="نقش"
                    value={selected}
                    onChange={(e) =>
                      setDraftRoles((prev) => ({ ...prev, [member.id]: e.target.value }))
                    }
                    disabled={isSelfLastAdmin}
                    helperText={
                      isSelfLastAdmin
                        ? "شما آخرین مدیر هستید؛ تغییر نقش خودتان غیرفعال است."
                        : " "
                    }
                    sx={{ minWidth: 180 }}
                  >
                    {ROLES.map((opt) => (
                      <MenuItem
                        key={opt.value}
                        value={opt.value}
                        disabled={
                          member.user_id === currentUserId &&
                          member.role === "admin" &&
                          adminCount <= 1 &&
                          opt.value !== "admin"
                        }
                      >
                        {opt.label}
                      </MenuItem>
                    ))}
                  </TextField>
                  <Button
                    variant="contained"
                    disabled={
                      blocked ||
                      isSelfLastAdmin ||
                      selected === member.role ||
                      savingId === member.id
                    }
                    onClick={() => {
                      setSavingId(member.id);
                      void patchMutation
                        .mutateAsync({ memberId: member.id, nextRole: selected })
                        .finally(() => setSavingId(null));
                    }}
                  >
                    ذخیره نقش
                  </Button>
                </Stack>
              </Box>
            );
          })}
        </Stack>
      )}
    </TenantShell>
  );
}
