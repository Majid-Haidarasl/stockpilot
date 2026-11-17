import { expect, test } from "@playwright/test";
import { loginAs, logout, pickOrg } from "../helpers/auth";
import { clickAction, createDraftOrder, expectStatus } from "../helpers/orders";

test("admin sees notification after confirm; warehouse sees OrderConfirmed only", async ({
  page,
}) => {
  await loginAs(page, "sales@aftab.test");
  await pickOrg(page, /Aftab/);
  await createDraftOrder(page, "1");
  await clickAction(page, "رزرو");
  await expectStatus(page, "رزروشده");
  await clickAction(page, "تأیید");
  await expectStatus(page, "تأییدشده");

  await page.getByRole("link", { name: "اعلان‌ها", exact: true }).click();
  await expect(page.getByTestId("notifications-list")).toBeVisible({ timeout: 60_000 });
  await expect(
    page.locator('[data-notification-type="OrderConfirmed"]').first(),
  ).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("سفارش تأیید شد").first()).toBeVisible({
    timeout: 60_000,
  });

  await logout(page);
  await loginAs(page, "warehouse@aftab.test");
  await pickOrg(page, /Aftab/);
  await page.getByRole("link", { name: "اعلان‌ها", exact: true }).click();
  await expect(
    page.locator('[data-notification-type="OrderConfirmed"]').first(),
  ).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("سفارش تأیید شد").first()).toBeVisible({
    timeout: 60_000,
  });
  // Warehouse must not see non-confirmed lifecycle types from this flow's reserve.
  await expect(page.locator('[data-notification-type="OrderReserved"]')).toHaveCount(0);
});
