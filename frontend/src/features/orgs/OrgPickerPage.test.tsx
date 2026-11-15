import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppThemeProvider } from "../../theme";
import { OrgPickerPage } from "./OrgPickerPage";

const fetchMock = vi.fn();
const clearTenant = vi.fn();

vi.mock("../../shared/api", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api")>("../../shared/api");
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => fetchMock(...args),
  };
});

vi.mock("../../shared/tenant", () => ({
  setTenant: vi.fn(),
  getTenant: () => null,
  clearTenant: () => clearTenant(),
}));

vi.mock("../../shared/query/useClearTenantCacheOnOrgSwitch", () => ({
  useClearTenantCacheOnOrgSwitch: () => undefined,
}));

vi.mock("../../shared/auth/useLogout", () => ({
  useLogout: () => ({ logout: vi.fn(), pending: false, error: null }),
}));

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <AppThemeProvider>
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <OrgPickerPage />
        </MemoryRouter>
      </QueryClientProvider>
    </AppThemeProvider>,
  );
}

describe("OrgPickerPage", () => {
  beforeEach(() => {
    fetchMock.mockReset();
  });

  it("renders org cards with role chips", async () => {
    fetchMock.mockResolvedValue({
      user: { id: "u1", email: "a@b.c", display_name: "سارا" },
      organizations: [
        {
          tenant_id: "t1",
          name: "آفتاب",
          slug: "aftab",
          role: "admin",
          membership_id: "m1",
        },
        {
          tenant_id: "t2",
          name: "مهتاب",
          slug: "mahtab",
          role: "sales",
          membership_id: "m2",
        },
      ],
    });

    renderPage();

    expect(await screen.findByRole("heading", { name: "انتخاب سازمان" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /آفتاب/ })).toBeInTheDocument();
    expect(screen.getByLabelText("نقش: مدیر")).toBeInTheDocument();
    expect(screen.getByLabelText("نقش: فروش")).toBeInTheDocument();
  });

  it("shows empty state when user has no orgs", async () => {
    fetchMock.mockResolvedValue({
      user: { id: "u1", email: "a@b.c", display_name: "سارا" },
      organizations: [],
    });

    renderPage();

    await waitFor(() => {
      expect(
        screen.getByText(/هنوز عضویت سازمانی ندارید/),
      ).toBeInTheDocument();
    });
  });
});
