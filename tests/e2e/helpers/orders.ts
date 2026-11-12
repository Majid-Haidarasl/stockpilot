import type { Page } from "@playwright/test";

export async function createDraftOrder(page: Page, quantity = "2"): Promise<string> {
  await page.getByRole("link", { name: "سفارش‌ها" }).click();
  await page.getByRole("link", { name: "سفارش جدید" }).click();
  await page.getByLabel("مشتری").click();
  await page.getByRole("option", { name: /E2E Customer/ }).click();
  await page.getByLabel("کالا").click();
  await page.getByRole("option", { name: /E2E Product/ }).click();
  await page.getByLabel("تعداد").fill(quantity);
  await page.getByRole("button", { name: "ذخیره پیش‌نویس" }).click();
  await page.waitForURL(/\/orders\/[0-9a-f-]+$/i, { timeout: 30_000 });
  const match = page.url().match(/\/orders\/([0-9a-f-]+)/i);
  if (!match) throw new Error(`Expected order detail URL, got ${page.url()}`);
  return match[1];
}

export async function clickAction(page: Page, name: "رزرو" | "تأیید" | "ارسال" | "لغو"): Promise<void> {
  await page.getByTestId(
    name === "رزرو"
      ? "action-reserve"
      : name === "تأیید"
        ? "action-confirm"
        : name === "ارسال"
          ? "action-ship"
          : "action-cancel",
  ).click();
  // Wait for in-flight to clear
  await page.waitForTimeout(500);
  await page.getByTestId(
    name === "رزرو"
      ? "action-reserve"
      : name === "تأیید"
        ? "action-confirm"
        : name === "ارسال"
          ? "action-ship"
          : "action-cancel",
  ).waitFor({ state: "detached", timeout: 30_000 }).catch(() => undefined);
}

export async function expectStatus(page: Page, label: string): Promise<void> {
  await page.getByLabel(`وضعیت: ${label}`).waitFor({ timeout: 30_000 });
}

export function tenantIdFromUrl(url: string): string {
  const match = url.match(/\/t\/([^/]+)/);
  if (!match) throw new Error(`No tenant id in ${url}`);
  return match[1];
}
