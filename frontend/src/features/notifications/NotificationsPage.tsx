import { EmptyState, TenantShell } from "../../shared/ui";

export function NotificationsPage() {
  return (
    <TenantShell title="اعلان‌ها" subtitle="صندوق اعلان‌های سازمان">
      <EmptyState
        illustration="inbox"
        message="هنوز اعلانی ندارید."
      />
    </TenantShell>
  );
}
