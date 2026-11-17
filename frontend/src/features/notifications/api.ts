import { apiFetch } from "../../shared/api";
import type { components } from "../../generated/api/schema";

export type Notification = components["schemas"]["NotificationOut"];

const REFETCH_MS = 20_000;

export const notificationsRefetch = {
  refetchInterval: REFETCH_MS,
  refetchOnWindowFocus: true as const,
};

export async function listNotifications(
  tenantId: string,
  params: {
    limit?: number;
    unreadOnly?: boolean;
    cursorCreatedAt?: string | null;
    cursorId?: string | null;
  } = {},
): Promise<Notification[]> {
  const qs = new URLSearchParams();
  qs.set("limit", String(params.limit ?? 50));
  if (params.unreadOnly) qs.set("unread_only", "true");
  if (params.cursorCreatedAt) qs.set("cursor_created_at", params.cursorCreatedAt);
  if (params.cursorId) qs.set("cursor_id", params.cursorId);
  return apiFetch<Notification[]>(
    `/api/v1/tenants/${tenantId}/notifications?${qs.toString()}`,
  );
}

export async function markNotificationRead(
  tenantId: string,
  notificationId: string,
): Promise<Notification> {
  return apiFetch<Notification>(
    `/api/v1/tenants/${tenantId}/notifications/${notificationId}/read`,
    { method: "POST" },
  );
}

export function unreadBadgeLabel(count: number): string {
  if (count <= 0) return "";
  if (count >= 100) return "99+";
  return String(count);
}
