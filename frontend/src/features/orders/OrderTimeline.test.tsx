import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AppThemeProvider } from "../../theme";
import { OrderTimeline } from "./OrderTimeline";

describe("OrderTimeline", () => {
  it("renders event label, actor, and Tehran display time", () => {
    render(
      <AppThemeProvider>
        <OrderTimeline
          events={[
            {
              event_type: "order.reserved",
              occurred_at: "2024-03-20T12:00:00.000Z",
              actor_display_name: "سارا",
              from_status: "DRAFT",
              to_status: "RESERVED",
            },
          ]}
        />
      </AppThemeProvider>,
    );

    expect(screen.getByText("رزرو")).toBeInTheDocument();
    expect(screen.getByText(/سارا/)).toBeInTheDocument();
    expect(screen.getByText(/پیش‌نویس/)).toBeInTheDocument();
    expect(screen.getByText(/رزروشده/)).toBeInTheDocument();
  });

  it("shows empty state when there are no events", () => {
    render(
      <AppThemeProvider>
        <OrderTimeline events={[]} />
      </AppThemeProvider>,
    );
    expect(screen.getByText(/رویدادی ثبت نشده/)).toBeInTheDocument();
  });
});
