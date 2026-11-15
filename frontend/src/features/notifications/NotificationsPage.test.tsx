import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppThemeProvider } from "../../theme";
import { NotificationsPage } from "./NotificationsPage";

vi.mock("../../shared/api", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api")>("../../shared/api");
  return {
    ...actual,
    apiFetch: vi.fn().mockResolvedValue({
      user: { id: "u1", email: "a@b.c", display_name: "کاربر" },
      organizations: [],
    }),
  };
});

vi.mock("../../shared/tenant", () => ({
  getTenant: () => ({ tenantId: "ten-1", name: "Org", role: "viewer" }),
}));

describe("NotificationsPage", () => {
  beforeEach(() => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
  });

  it("shows polished empty inbox copy", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <AppThemeProvider>
        <QueryClientProvider client={client}>
          <MemoryRouter initialEntries={["/t/ten-1/notifications"]}>
            <Routes>
              <Route path="/t/:tenantId/notifications" element={<NotificationsPage />} />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      </AppThemeProvider>,
    );

    expect(await screen.findByRole("heading", { name: "اعلان‌ها" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("هنوز اعلانی ندارید.");
  });
});
