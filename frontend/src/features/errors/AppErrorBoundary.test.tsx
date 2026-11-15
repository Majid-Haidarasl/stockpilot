import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AppThemeProvider } from "../../theme";
import { AppErrorBoundary } from "./AppErrorBoundary";

function Boom(): null {
  throw new Error("secret internal stack should not appear");
}

describe("AppErrorBoundary", () => {
  it("shows generic Persian fallback without error details", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);

    render(
      <AppThemeProvider>
        <MemoryRouter>
          <AppErrorBoundary resetKey="/">
            <Boom />
          </AppErrorBoundary>
        </MemoryRouter>
      </AppThemeProvider>,
    );

    expect(screen.getByRole("heading", { name: "خطایی رخ داد" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "تلاش دوباره" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "بازگشت" })).toBeInTheDocument();
    expect(screen.queryByText(/secret internal/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/stack/i)).not.toBeInTheDocument();

    spy.mockRestore();
  });

  it("resets when resetKey changes", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);

    function Flaky({ blow }: { blow: boolean }) {
      if (blow) throw new Error("boom");
      return <p>سالم</p>;
    }

    const { rerender } = render(
      <AppThemeProvider>
        <MemoryRouter>
          <AppErrorBoundary resetKey="/a">
            <Flaky blow />
          </AppErrorBoundary>
        </MemoryRouter>
      </AppThemeProvider>,
    );

    expect(screen.getByRole("heading", { name: "خطایی رخ داد" })).toBeInTheDocument();

    rerender(
      <AppThemeProvider>
        <MemoryRouter>
          <AppErrorBoundary resetKey="/b">
            <Flaky blow={false} />
          </AppErrorBoundary>
        </MemoryRouter>
      </AppThemeProvider>,
    );

    expect(screen.getByText("سالم")).toBeInTheDocument();
    spy.mockRestore();
  });
});
