import { expect, test } from "@playwright/test";
import { loginAs, pickOrg } from "../helpers/auth";
import { getAvailableForSku } from "../helpers/db";
import {
  clickAction,
  createDraftOrder,
  expectStatus,
  tenantIdFromUrl,
} from "../helpers/orders";

test("cancel reserved order releases stock", async ({ page }) => {
  await loginAs(page, "sales@aftab.test");
  await pickOrg(page, /Aftab/);
  const tenantId = tenantIdFromUrl(page.url());
  const before = await getAvailableForSku(tenantId, "E2E-SKU-1");

  await createDraftOrder(page, "2");
  await clickAction(page, "رزرو");
  await expectStatus(page, "رزروشده");
  const afterReserve = await getAvailableForSku(tenantId, "E2E-SKU-1");
  expect(afterReserve).toBe(before - 2);

  await clickAction(page, "لغو");
  await expectStatus(page, "لغوشده");
  const afterCancel = await getAvailableForSku(tenantId, "E2E-SKU-1");
  expect(afterCancel).toBe(before);
});

test("cancel confirmed order releases stock", async ({ page }) => {
  await loginAs(page, "sales@aftab.test");
  await pickOrg(page, /Aftab/);
  const tenantId = tenantIdFromUrl(page.url());
  const before = await getAvailableForSku(tenantId, "E2E-SKU-1");

  await createDraftOrder(page, "1");
  await clickAction(page, "رزرو");
  await clickAction(page, "تأیید");
  await expectStatus(page, "تأییدشده");
  const held = await getAvailableForSku(tenantId, "E2E-SKU-1");
  expect(held).toBe(before - 1);

  await clickAction(page, "لغو");
  await expectStatus(page, "لغوشده");
  const afterCancel = await getAvailableForSku(tenantId, "E2E-SKU-1");
  expect(afterCancel).toBe(before);
});
