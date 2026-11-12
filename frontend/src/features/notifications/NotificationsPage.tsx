import { TenantShell, EmptyState } from "../../shared/ui";

export function NotificationsPage() {
  return (
    <TenantShell title="اعلان‌ها">
      <EmptyState message="هنوز اعلانی ندارید." />
    </TenantShell>
  );
}
