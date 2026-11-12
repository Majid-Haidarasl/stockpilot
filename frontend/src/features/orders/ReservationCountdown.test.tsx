import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { allowedOrderActions } from "./allowedActions";
import { confirmEnabledByCountdown } from "./countdownPolicy";
import { ReservationCountdown } from "./ReservationCountdown";

describe("reservation countdown", () => {
  it("does not decide confirm — local expiry leaves confirm eligibility to status/role only", () => {
    expect(confirmEnabledByCountdown(-1)).toBe(true);
    expect(confirmEnabledByCountdown(0)).toBe(true);
    expect(confirmEnabledByCountdown(60_000)).toBe(true);

    const actions = allowedOrderActions("RESERVED", "sales");
    expect(actions.confirm).toBe(true);

    const past = new Date(Date.now() - 60_000).toISOString();
    render(<ReservationCountdown expiresAt={past} />);
    const node = screen.getByTestId("reservation-countdown");
    expect(node.getAttribute("data-expired-locally")).toBe("true");
    // Confirm remains allowed by role/status; countdown is guidance only.
    expect(actions.confirm && confirmEnabledByCountdown(-1)).toBe(true);
  });
});
