import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiProblemError } from "../../shared/api";
import { AppThemeProvider } from "../../theme";
import { unreadBadgeLabel } from "./api";
import { NotificationsPage } from "./NotificationsPage";

const fetchMock = vi.fn();

vi.mock("../../shared/api", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api")>("../../shared/api");
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => fetchMock(...args),
  };
});

vi.mock("../../shared/tenant", () => ({
  getTenant: () => ({ tenantId: "ten-1", name: "Org", role: "viewer" }),
}));

const meResponse = {
  user: { id: "u1", email: "a@b.c", display_name: "کاربر" },
  organizations: [],
};

function isMePath(path: string): boolean {
  return path === "/api/v1/me" || path.endsWith("/me");
}

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
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
}

describe("NotificationsPage", () => {
  beforeEach(() => {
    fetchMock.mockReset();
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
    fetchMock.mockImplementation((path: unknown) => {
      const p = typeof path === "string" ? path : "";
      if (isMePath(p)) return Promise.resolve(meResponse);
      if (p.includes("/notifications")) return Promise.resolve([]);
      return Promise.resolve(meResponse);
    });
    renderPage();
    expect(await screen.findByRole("heading", { name: "اعلان‌ها" })).toBeInTheDocument();
    expect(await screen.findByText("هنوز اعلانی ندارید.")).toBeInTheDocument();
  });

  it("renders notification labels from API", async () => {
    fetchMock.mockImplementation((path: unknown) => {
      const p = typeof path === "string" ? path : "";
      if (isMePath(p)) return Promise.resolve(meResponse);
      if (p.includes("/notifications")) {
        return Promise.resolve([
          {
            id: "n1",
            tenant_id: "ten-1",
            type: "OrderConfirmed",
            data: { order_id: "ord-1" },
            created_at: "2026-11-16T10:00:00Z",
            read_at: null,
          },
        ]);
      }
      return Promise.resolve([]);
    });
    renderPage();
    expect(await screen.findByText("سفارش تأیید شد")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "مشاهده سفارش" })).toHaveAttribute(
      "href",
      "/t/ten-1/orders/ord-1",
    );
  });

  it("mark-as-read posts to read endpoint", async () => {
    fetchMock.mockImplementation((path: unknown, init?: RequestInit) => {
      const p = typeof path === "string" ? path : "";
      if (isMePath(p)) return Promise.resolve(meResponse);
      if (p.includes("/read") && init?.method === "POST") {
        return Promise.resolve({
          id: "n1",
          tenant_id: "ten-1",
          type: "OrderReserved",
          data: {},
          created_at: "2026-11-16T10:00:00Z",
          read_at: "2026-11-16T11:00:00Z",
        });
      }
      if (p.includes("/notifications")) {
        return Promise.resolve([
          {
            id: "n1",
            tenant_id: "ten-1",
            type: "OrderReserved",
            data: { order_id: "ord-1" },
            created_at: "2026-11-16T10:00:00Z",
            read_at: null,
          },
        ]);
      }
      return Promise.resolve([]);
    });
    renderPage();
    const row = await screen.findByTestId("notification-n1");
    fireEvent.click(row);
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/tenants/ten-1/notifications/n1/read",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("shows error state on API failure", async () => {
    fetchMock.mockImplementation((path: unknown) => {
      const p = typeof path === "string" ? path : "";
      if (isMePath(p)) return Promise.resolve(meResponse);
      if (p.includes("/notifications")) {
        return Promise.reject(
          new ApiProblemError({
            status: 500,
            code: "INTERNAL",
            title: "error",
            detail: "شکست سرور",
          }),
        );
      }
      return Promise.resolve([]);
    });
    renderPage();
    expect(await screen.findByText(/شکست|خطا|مجدد/i)).toBeInTheDocument();
  });

  it("load more requests next cursor page", async () => {
    const firstPage = Array.from({ length: 50 }, (_, i) => ({
      id: `n-${i}`,
      tenant_id: "ten-1",
      type: "OrderReserved",
      data: {},
      created_at: `2026-11-16T10:00:${String(i).padStart(2, "0")}Z`,
      read_at: null,
    }));
    fetchMock.mockImplementation((path: unknown) => {
      const p = typeof path === "string" ? path : "";
      if (isMePath(p)) return Promise.resolve(meResponse);
      if (p.includes("cursor_id=")) {
        return Promise.resolve([
          {
            id: "n-next",
            tenant_id: "ten-1",
            type: "OrderShipped",
            data: {},
            created_at: "2026-11-15T10:00:00Z",
            read_at: null,
          },
        ]);
      }
      if (p.includes("/notifications")) return Promise.resolve(firstPage);
      return Promise.resolve([]);
    });
    renderPage();
    expect(await screen.findByRole("button", { name: "موارد بیشتر" })).toBeInTheDocument();
    expect(screen.getAllByText("سفارش رزرو شد").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "موارد بیشتر" }));
    expect(await screen.findByText("سفارش ارسال شد")).toBeInTheDocument();
  });
});

describe("unreadBadgeLabel", () => {
  it("shows 99+ when count >= 100", () => {
    expect(unreadBadgeLabel(0)).toBe("");
    expect(unreadBadgeLabel(3)).toBe("3");
    expect(unreadBadgeLabel(99)).toBe("99");
    expect(unreadBadgeLabel(100)).toBe("99+");
    expect(unreadBadgeLabel(250)).toBe("99+");
  });
});
