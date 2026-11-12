import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { mapApiProblem } from "../../shared/api/mapApiError";
import {
  canWriteInventory,
  INVENTORY_WRITE_DENIED_MESSAGE,
} from "./inventoryPermissions";

vi.mock("../../shared/tenant", () => ({
  getTenant: () => ({ tenantId: "t1", name: "Org", role: "viewer" }),
}));

describe("viewer inventory denial", () => {
  it("hides write capability for viewer and sales", () => {
    expect(canWriteInventory("viewer")).toBe(false);
    expect(canWriteInventory("sales")).toBe(false);
    expect(canWriteInventory("warehouse")).toBe(true);
    expect(canWriteInventory("admin")).toBe(true);
  });

  it("shows a clear Persian denial message", () => {
    render(
      <div role="status" data-testid="inventory-write-denied">
        {INVENTORY_WRITE_DENIED_MESSAGE}
      </div>,
    );
    expect(screen.getByTestId("inventory-write-denied")).toHaveTextContent(
      /اجازه تغییر موجودی/,
    );
  });

  it("maps API 403 FORBIDDEN to Persian for scenario 11", () => {
    expect(
      mapApiProblem({ status: 403, code: "FORBIDDEN", title: "Forbidden" }),
    ).toMatch(/اجازه انجام این کار را ندارید/);
  });
});
