import { expect, test } from "@playwright/test";
import { loginAs, pickOrg } from "../helpers/auth";
import { backdateReservation } from "../helpers/db";
import {
  clickAction,
  createDraftOrder,
  expectStatus,
} from "../helpers/orders";

test("confirm after backdated deadline expires order", async ({ page }) => {
  await loginAs(page, "sales@aftab.test");
  await pickOrg(page, /Aftab/);

  const orderId = await createDraftOrder(page, "1");
  await clickAction(page, "رزرو");
  await expectStatus(page, "رزروشده");

  await backdateReservation(orderId);
  await clickAction(page, "تأیید");

  await expect(page.getByText(/مهلت رزرو به پایان رسیده/)).toBeVisible({ timeout: 30_000 });
  await expectStatus(page, "منقضی‌شده");
});
