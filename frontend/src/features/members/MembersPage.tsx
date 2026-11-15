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
  DataTable,
  ErrorState,
  ForbiddenState,
  LoadingState,
  RoleChip,
  roleLabel,
  TenantShell,
  type DataTableColumn,
} from "../../shared/ui";
import { isLastAdminDemotion } from "./lastAdmin";

const ROLES = [
  { value: "admin", label: "مدیر" },
  { value: "sales", label: "فروش" },
  { value: "warehouse", label: "انبار" },
  { value: "viewer", label: "ناظر" },
] as const;

function MemberRoleEditor({
  member,
  selected,
  blocked,
  isSelfLastAdmin,
  saving,
  onSelect,
  onSave,
}: {
  member: Member;
  selected: string;
  blocked: boolean;
  isSelfLastAdmin: boolean;
  saving: boolean;
  onSelect: (role: string) => void;
  onSave: () => void;
}) {
  return (
    <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }}>
      <TextField
        select
        label="نقش"
        value={selected}
        onChange={(e) => onSelect(e.target.value)}
        disabled={isSelfLastAdmin}
        helperText={
          isSelfLastAdmin ? "شما آخرین مدیر هستید؛ تغییر نقش خودتان غیرفعال است." : " "
        }
        sx={{ minWidth: 160 }}
        size="small"
      >
        {ROLES.map((opt) => (
          <MenuItem
            key={opt.value}
            value={opt.value}
            disabled={isSelfLastAdmin && opt.value !== "admin"}
          >
            {opt.label}
          </MenuItem>
        ))}
      </TextField>
      <Button
        variant="contained"
        disabled={blocked || isSelfLastAdmin || selected === member.role || saving}
        onClick={onSave}
      >
        ذخیره نقش
      </Button>
    </Stack>
  );
}

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

  const members = useMemo(
    () => (Array.isArray(membersQuery.data) ? membersQuery.data : []),
    [membersQuery.data],
  );
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

  function editorProps(member: Member) {
    const selected = draftRoles[member.id] ?? member.role;
    const blocked =
      member.user_id === currentUserId && isLastAdminDemotion(members, member.id, selected);
    const isSelfLastAdmin =
      member.user_id === currentUserId && adminCount <= 1 && member.role === "admin";
    return {
      member,
      selected,
      blocked,
      isSelfLastAdmin,
      saving: savingId === member.id,
      onSelect: (next: string) => setDraftRoles((prev) => ({ ...prev, [member.id]: next })),
      onSave: () => {
        setSavingId(member.id);
        void patchMutation
          .mutateAsync({ memberId: member.id, nextRole: selected })
          .catch(() => undefined)
          .finally(() => setSavingId(null));
      },
    };
  }

  const columns: DataTableColumn<Member>[] = [
    {
      id: "name",
      header: "عضو",
      render: (m) => (
        <Box>
          <Typography sx={{ fontWeight: 600 }}>
            {m.display_name ?? m.email ?? m.user_id}
          </Typography>
          {m.email ? (
            <Typography variant="body2" color="text.secondary" dir="ltr">
              {m.email}
            </Typography>
          ) : null}
        </Box>
      ),
    },
    {
      id: "role",
      header: "نقش فعلی",
      render: (m) => <RoleChip role={m.role} label={roleLabel(m.role)} />,
    },
    {
      id: "actions",
      header: "تغییر نقش",
      render: (m) => <MemberRoleEditor {...editorProps(m)} />,
    },
  ];

  return (
    <TenantShell title="اعضای سازمان">
      <Alert severity="info" sx={{ mb: 2 }} role="status">
        آخرین مدیر فعال سازمان را نمی‌توان به نقش دیگر تغییر داد. این محدودیت هم در رابط و هم در
        سرور اعمال می‌شود.
      </Alert>

      {formError ? (
        <Box sx={{ mb: 2 }}>
          <ErrorState message={formError} showIllustration={false} />
        </Box>
      ) : null}

      <DataTable
        columns={columns}
        rows={members}
        rowKey={(m) => m.id}
        emptyMessage="عضوی یافت نشد."
        renderMobileRow={(m) => {
          const props = editorProps(m);
          return (
            <Stack
              spacing={1.5}
              sx={{ p: 1.5, border: 1, borderColor: "divider", borderRadius: 1 }}
            >
              <Stack direction="row" justifyContent="space-between" alignItems="flex-start" gap={1}>
                <Box sx={{ minWidth: 0 }}>
                  <Typography sx={{ fontWeight: 600 }}>
                    {m.display_name ?? m.email ?? m.user_id}
                  </Typography>
                  {m.email ? (
                    <Typography variant="body2" color="text.secondary" dir="ltr">
                      {m.email}
                    </Typography>
                  ) : null}
                </Box>
                <RoleChip role={m.role} />
              </Stack>
              <MemberRoleEditor {...props} />
            </Stack>
          );
        }}
      />
    </TenantShell>
  );
}
