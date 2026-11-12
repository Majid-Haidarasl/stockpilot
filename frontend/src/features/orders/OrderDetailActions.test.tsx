import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { allowedOrderActions } from "./allowedActions";

vi.mock("../../shared/tenant", () => ({
  getTenant: () => ({ tenantId: "t1", name: "Org", role: "warehouse" }),
}));

describe("action buttons match status and role", () => {
  it("warehouse on CONFIRMED sees ship only among cycle actions", () => {
    const actions = allowedOrderActions("CONFIRMED", "warehouse");
    render(
      <div>
        {actions.reserve ? <button type="button">رزرو</button> : null}
        {actions.confirm ? <button type="button">تأیید</button> : null}
        {actions.ship ? <button type="button">ارسال</button> : null}
        {actions.cancel ? <button type="button">لغو</button> : null}
      </div>,
    );
    expect(screen.getByRole("button", { name: "ارسال" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "تأیید" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "رزرو" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "لغو" })).not.toBeInTheDocument();
  });

  it("sales on RESERVED sees confirm and cancel, not ship", () => {
    const actions = allowedOrderActions("RESERVED", "sales");
    render(
      <div>
        {actions.reserve ? <button type="button">رزرو</button> : null}
        {actions.confirm ? <button type="button">تأیید</button> : null}
        {actions.ship ? <button type="button">ارسال</button> : null}
        {actions.cancel ? <button type="button">لغو</button> : null}
      </div>,
    );
    expect(screen.getByRole("button", { name: "تأیید" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "لغو" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "ارسال" })).not.toBeInTheDocument();
  });
});
