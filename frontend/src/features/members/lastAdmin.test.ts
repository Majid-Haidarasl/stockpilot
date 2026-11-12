import { describe, expect, it } from "vitest";
import type { Member } from "../../shared/api";
import { canSelfDemoteLastAdmin, isLastAdminDemotion } from "./lastAdmin";

const members: Member[] = [
  {
    id: "m1",
    user_id: "u1",
    role: "admin",
    display_name: "Admin One",
  },
  {
    id: "m2",
    user_id: "u2",
    role: "sales",
    display_name: "Sales",
  },
];

describe("last-admin rule", () => {
  it("blocks demoting the sole admin", () => {
    expect(isLastAdminDemotion(members, "m1", "viewer")).toBe(true);
    expect(canSelfDemoteLastAdmin(members, "u1", "m1", "viewer")).toBe(false);
  });

  it("allows demotion when another admin exists", () => {
    const twoAdmins: Member[] = [
      ...members,
      { id: "m3", user_id: "u3", role: "admin", display_name: "Admin Two" },
    ];
    expect(isLastAdminDemotion(twoAdmins, "m1", "viewer")).toBe(false);
    expect(canSelfDemoteLastAdmin(twoAdmins, "u1", "m1", "viewer")).toBe(true);
  });

  it("maps LAST_ADMIN to a clear Persian message", async () => {
    const { mapApiProblem } = await import("../../shared/api/mapApiError");
    expect(
      mapApiProblem({
        status: 409,
        code: "LAST_ADMIN",
        title: "Cannot remove the last admin",
      }),
    ).toMatch(/آخرین مدیر/);
  });
});
