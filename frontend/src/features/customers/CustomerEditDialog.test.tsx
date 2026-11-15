import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiProblemError, type Customer } from "../../shared/api";
import { AppThemeProvider } from "../../theme";
import { CustomerEditDialog } from "./CustomerEditDialog";

const fetchMock = vi.fn();

vi.mock("../../shared/api", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api")>("../../shared/api");
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => fetchMock(...args),
  };
});

const customer: Customer = {
  id: "c1",
  tenant_id: "ten-1",
  name: "علی",
  phone: "09120000000",
  email: null,
  notes: null,
  version: 1,
};

function renderDialog(onClose = vi.fn()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    onClose,
    ...render(
      <AppThemeProvider>
        <QueryClientProvider client={client}>
          <CustomerEditDialog
            open
            tenantId="ten-1"
            customer={customer}
            onClose={onClose}
          />
        </QueryClientProvider>
      </AppThemeProvider>,
    ),
  };
}

describe("CustomerEditDialog", () => {
  beforeEach(() => {
    fetchMock.mockReset();
  });

  it("submits PATCH with expected_version", async () => {
    fetchMock.mockResolvedValue({ ...customer, name: "علی جدید", version: 2 });
    const { onClose } = renderDialog();

    fireEvent.change(screen.getByLabelText(/نام/), { target: { value: "علی جدید" } });
    fireEvent.click(screen.getByRole("button", { name: "ذخیره" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    const [path, init] = fetchMock.mock.calls[0];
    expect(String(path)).toContain("/customers/c1");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body)).toMatchObject({
      expected_version: 1,
      name: "علی جدید",
    });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("shows Persian message on 409 version conflict", async () => {
    fetchMock
      .mockRejectedValueOnce(
        new ApiProblemError({
          status: 409,
          code: "VERSION_CONFLICT",
          title: "Version conflict",
        }),
      )
      .mockResolvedValueOnce([{ ...customer, version: 3, name: "تازه‌شده" }]);

    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "ذخیره" }));

    expect(await screen.findByText(/نسخه داده تغییر کرده است/)).toBeInTheDocument();
  });
});
