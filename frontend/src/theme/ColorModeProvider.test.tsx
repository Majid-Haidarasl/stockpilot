import { Button } from "@mui/material";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppThemeProvider, COLOR_MODE_KEY, useColorMode } from "./ColorModeProvider";

function Probe() {
  const { mode, toggleColorMode } = useColorMode();
  return (
    <Button onClick={toggleColorMode} aria-label="toggle-theme">
      {mode}
    </Button>
  );
}

describe("ColorModeProvider", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("persists theme toggle to localStorage", () => {
    render(
      <AppThemeProvider>
        <Probe />
      </AppThemeProvider>,
    );

    expect(screen.getByRole("button", { name: "toggle-theme" })).toHaveTextContent("light");
    fireEvent.click(screen.getByRole("button", { name: "toggle-theme" }));
    expect(screen.getByRole("button", { name: "toggle-theme" })).toHaveTextContent("dark");
    expect(localStorage.getItem(COLOR_MODE_KEY)).toBe("dark");
  });

  it("respects prefers-color-scheme when unset", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("prefers-color-scheme: dark"),
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    );

    render(
      <AppThemeProvider>
        <Probe />
      </AppThemeProvider>,
    );

    expect(screen.getByRole("button", { name: "toggle-theme" })).toHaveTextContent("dark");
  });
});
