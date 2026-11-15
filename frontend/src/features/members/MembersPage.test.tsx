import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiProblemError } from "../../shared/api";
import { AppThemeProvider } from "../../theme";
import { MembersPage } from "./MembersPage";

const fetchMock = vi.fn();

vi.mock("../../shared/api", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api")>("../../shared/api");
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => fetchMock(...args),
  };
});

vi.mock("../../shared/tenant", () => ({
  getTenant: () => ({ tenantId: "ten-1", name: "Org", role: "admin" }),
}));

const meResponse = {
  user: { id: "u-admin", email: "admin@x.com", display_name: "مدیر" },
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
        <MemoryRouter initialEntries={["/t/ten-1/members"]}>
          <Routes>
            <Route path="/t/:tenantId/members" element={<MembersPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </AppThemeProvider>,
  );
}

describe("MembersPage", () => {
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

  it("renders role chips for members", async () => {
    fetchMock.mockImplementation((path: unknown) => {
      const p = typeof path === "string" ? path : "";
      if (isMePath(p)) return Promise.resolve(meResponse);
      return Promise.resolve([
        {
          id: "m1",
          user_id: "u-admin",
          role: "admin",
          display_name: "مدیر یک",
          email: "admin@x.com",
        },
        {
          id: "m2",
          user_id: "u2",
          role: "sales",
          display_name: "فروشنده",
          email: "s@x.com",
        },
      ]);
    });

    renderPage();

    expect(await screen.findByLabelText("نقش: مدیر")).toBeInTheDocument();
    expect(screen.getByLabelText("نقش: فروش")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/آخرین مدیر/);
  });

  it("shows LAST_ADMIN Persian message from API", async () => {
    fetchMock.mockImplementation((path: unknown, init?: RequestInit) => {
      const p = typeof path === "string" ? path : "";
      if (isMePath(p)) return Promise.resolve(meResponse);
      if (typeof init?.method === "string" && init.method.toUpperCase() === "PATCH") {
        return Promise.reject(
          new ApiProblemError({
            status: 409,
            code: "LAST_ADMIN",
            title: "last admin",
          }),
        );
      }
      return Promise.resolve([
        {
          id: "m1",
          user_id: "u-admin",
          role: "admin",
          display_name: "مدیر یک",
          email: "admin@x.com",
        },
        {
          id: "m2",
          user_id: "u2",
          role: "admin",
          display_name: "مدیر دو",
          email: "a2@x.com",
        },
      ]);
    });

    renderPage();
    await screen.findByText("مدیر دو");

    const row = screen.getByText("مدیر دو").closest("tr");
    expect(row).toBeTruthy();
    const select = within(row as HTMLElement).getByLabelText("نقش");
    fireEvent.mouseDown(select);
    fireEvent.click(await screen.findByRole("option", { name: "ناظر" }));
    fireEvent.click(within(row as HTMLElement).getByRole("button", { name: "ذخیره نقش" }));

    await waitFor(() => {
      expect(
        screen.getByText("نمی‌توانید نقش آخرین مدیر سازمان را تغییر دهید."),
      ).toBeInTheDocument();
    });
  });
});
