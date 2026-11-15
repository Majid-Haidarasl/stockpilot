import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Product, ProductImage } from "../../shared/api";
import { AppThemeProvider } from "../../theme";
import { ProductImagesDialog } from "./ProductImagesDialog";

const apiFetch = vi.fn();
const apiUpload = vi.fn();
const mapApiError = vi.fn((err: unknown) => {
  if (err && typeof err === "object" && "problem" in (err as object)) {
    return "شما اجازه انجام این کار را ندارید.";
  }
  return "خطا";
});

vi.mock("../../shared/api", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api")>("../../shared/api");
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => apiFetch(...args),
    apiUpload: (...args: unknown[]) => apiUpload(...args),
    mapApiError: (err: unknown) => mapApiError(err),
  };
});

vi.mock("../../shared/media/useAuthMediaUrl", () => ({
  useAuthMediaUrl: () => ({ url: null, isError: false, isPending: false }),
}));

vi.mock("../../shared/media/ProductThumb", () => ({
  ProductThumb: ({ alt }: { alt: string }) => <div data-testid="product-thumb">{alt}</div>,
}));

const product: Product = {
  id: "p1",
  tenant_id: "t1",
  sku: "SKU-1",
  title: "کالای تست",
  unit_price: { amount: "1000", currency: "IRR" },
  is_active: true,
  stock_warning_threshold: 5,
  version: 1,
  primary_thumbnail_url: null,
};

const sampleImage: ProductImage = {
  id: "img1",
  product_id: "p1",
  content_type: "image/webp",
  width: 800,
  height: 800,
  size_bytes: 1000,
  sha256: "abc",
  is_primary: true,
  sort_order: 0,
  url: "/api/v1/tenants/t1/images/img1/file",
  thumbnail_url: "/api/v1/tenants/t1/images/img1/thumbnail",
  created_at: "2026-01-01T00:00:00Z",
};

function wrap(ui: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <AppThemeProvider>
      <QueryClientProvider client={client}>{ui}</QueryClientProvider>
    </AppThemeProvider>,
  );
}

describe("ProductImagesDialog roles", () => {
  beforeEach(() => {
    apiFetch.mockReset();
    apiUpload.mockReset();
    mapApiError.mockClear();
    apiFetch.mockResolvedValue([sampleImage]);
  });

  it("hides upload for viewer and warehouse; shows read-only gallery", async () => {
    for (const role of ["viewer", "warehouse"] as const) {
      const { unmount } = wrap(
        <ProductImagesDialog
          open
          tenantId="t1"
          product={product}
          role={role}
          onClose={() => undefined}
        />,
      );
      await screen.findByText(/مشاهده تصاویر/);
      expect(screen.queryByRole("button", { name: /بارگذاری تصویر/ })).not.toBeInTheDocument();
      expect(screen.queryByLabelText("حذف تصویر")).not.toBeInTheDocument();
      unmount();
    }
  });

  it("shows upload for sales and does not break on list 403", async () => {
    apiFetch.mockRejectedValueOnce({
      problem: { status: 403, code: "FORBIDDEN", title: "Forbidden" },
    });
    wrap(
      <ProductImagesDialog
        open
        tenantId="t1"
        product={product}
        role="sales"
        onClose={() => undefined}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText(/اجازه انجام این کار/)).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "بستن" })).toBeInTheDocument();
  });

  it("opens ConfirmDialog حذف تصویر for admin", async () => {
    wrap(
      <ProductImagesDialog
        open
        tenantId="t1"
        product={product}
        role="admin"
        onClose={() => undefined}
      />,
    );
    const deleteBtn = await screen.findByLabelText("حذف تصویر");
    fireEvent.click(deleteBtn);
    const dialog = await screen.findByRole("dialog", { name: "حذف تصویر" });
    expect(within(dialog).getByText(/مطمئن هستید/)).toBeInTheDocument();
  });

  it("shows placeholder when there is no image and Persian client type error", async () => {
    apiFetch.mockResolvedValueOnce([]);
    wrap(
      <ProductImagesDialog
        open
        tenantId="t1"
        product={product}
        role="sales"
        onClose={() => undefined}
      />,
    );
    await screen.findByText("بدون تصویر");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const bad = new File(["x"], "x.gif", { type: "image/gif" });
    Object.defineProperty(input, "files", { value: [bad], configurable: true });
    fireEvent.change(input);
    await waitFor(() => {
      expect(screen.getByText(/JPEG، PNG یا WebP/)).toBeInTheDocument();
    });
    expect(apiUpload).not.toHaveBeenCalled();
  });
});
