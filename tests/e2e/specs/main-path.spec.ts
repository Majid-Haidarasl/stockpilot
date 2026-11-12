import { expect, test } from "@playwright/test";
import { loginAs, logout, pickOrg } from "../helpers/auth";
import {
  clickAction,
  createDraftOrder,
  expectStatus,
} from "../helpers/orders";

test("sales draft → reserve → confirm; warehouse ships", async ({ page }) => {
  await loginAs(page, "sales@aftab.test");
  await pickOrg(page, /Aftab/);
  const tenantId = page.url().match(/\/t\/([^/]+)/)?.[1];
  if (!tenantId) throw new Error(`No tenant in ${page.url()}`);

  const orderId = await createDraftOrder(page, "3");
  await expect(page.getByText(/ریال/).first()).toBeVisible();
  await expect(page.getByText(/جمع تخمینی/).first()).toBeVisible();

  await clickAction(page, "رزرو");
  await expectStatus(page, "رزروشده");
  await expect(page.getByTestId("reservation-countdown")).toBeVisible();
  await expect(page.getByText(/قفل‌شده پس از رزرو/).first()).toBeVisible();

  await clickAction(page, "تأیید");
  await expectStatus(page, "تأییدشده");

  await logout(page);
  await loginAs(page, "warehouse@aftab.test");
  await pickOrg(page, /Aftab/);

  await page.goto(`/t/${tenantId}/orders/${orderId}`);
  await expectStatus(page, "تأییدشده");
  await clickAction(page, "ارسال");
  await expectStatus(page, "ارسال‌شده");
});
