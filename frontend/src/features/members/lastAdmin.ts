import type { Member } from "../../shared/api";

/** True when demoting this member would leave the org with zero admins. */
export function isLastAdminDemotion(
  members: Member[],
  memberId: string,
  nextRole: string,
): boolean {
  if (nextRole === "admin") return false;
  const target = members.find((m) => m.id === memberId);
  if (!target || target.role !== "admin") return false;
  const adminCount = members.filter((m) => m.role === "admin").length;
  return adminCount <= 1;
}

export function canSelfDemoteLastAdmin(
  members: Member[],
  currentUserId: string,
  memberId: string,
  nextRole: string,
): boolean {
  if (nextRole === "admin") return true;
  const target = members.find((m) => m.id === memberId);
  if (!target) return true;
  if (target.user_id !== currentUserId) return true;
  return !isLastAdminDemotion(members, memberId, nextRole);
}
