import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppProviders } from "../../app/providers";
import { AppThemeProvider } from "../../theme";
import { TenantShell } from "./TenantShell";

const getTenantMock = vi.fn();

vi.mock("../tenant", () => ({
  getTenant: () => getTenantMock(),
}));

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    apiFetch: vi.fn().mockResolvedValue({
      user: { id: "u1", email: "a@b.c", display_name: "کاربر تست" },
      organizations: [],
    }),
  };
});

function renderShell(role: string) {
  getTenantMock.mockReturnValue({ tenantId: "ten-1", name: "شرکت نمونه", role });
  return render(
    <AppThemeProvider>
      <AppProviders>
        <MemoryRouter initialEntries={["/t/ten-1/dashboard"]}>
          <Routes>
            <Route
              path="/t/:tenantId/dashboard"
              element={
                <TenantShell title="داشبورد">
                  <div>محتوا</div>
                </TenantShell>
              }
            />
          </Routes>
        </MemoryRouter>
      </AppProviders>
    </AppThemeProvider>,
  );
}

describe("TenantShell nav role visibility", () => {
  beforeEach(() => {
    getTenantMock.mockReset();
    // Force desktop drawer so nav links are in the tree without opening mobile menu.
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: String(query).includes("max-width") ? false : false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
  });

  it("shows members link only for admin", () => {
    renderShell("admin");
    expect(screen.getByRole("link", { name: "اعضا" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "سفارش‌ها" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "اعلان‌ها" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "نمایش اعلان‌ها" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "تغییر سازمان" })).toBeInTheDocument();
  });

  it("hides members link for non-admin roles", () => {
    renderShell("viewer");
    expect(screen.queryByRole("link", { name: "اعضا" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "موجودی" })).toBeInTheDocument();
  });
});
