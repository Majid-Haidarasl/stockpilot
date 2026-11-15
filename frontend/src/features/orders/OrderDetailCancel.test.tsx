import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppThemeProvider } from "../../theme";
import { ConfirmDialog } from "../../shared/ui";

/**
 * Mirrors OrderDetailPage cancel wiring: request/Idempotency-Key only on confirm.
 */
describe("Order cancel ConfirmDialog", () => {
  it("انصراف closes without calling the cancel action", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();

    render(
      <AppThemeProvider>
        <ConfirmDialog
          open
          title="لغو سفارش"
          description="آیا از لغو این سفارش مطمئن هستید؟"
          confirmLabel="لغو سفارش"
          cancelLabel="انصراف"
          confirmColor="error"
          onConfirm={onConfirm}
          onCancel={onCancel}
        />
      </AppThemeProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "انصراف" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("لغو سفارش invokes the confirm handler (request starts only then)", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();

    render(
      <AppThemeProvider>
        <ConfirmDialog
          open
          title="لغو سفارش"
          description="آیا از لغو این سفارش مطمئن هستید؟"
          confirmLabel="لغو سفارش"
          cancelLabel="انصراف"
          confirmColor="error"
          onConfirm={onConfirm}
          onCancel={onCancel}
        />
      </AppThemeProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "لغو سفارش" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onCancel).not.toHaveBeenCalled();
  });
});
