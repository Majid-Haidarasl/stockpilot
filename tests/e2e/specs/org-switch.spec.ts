import { expect, test } from "@playwright/test";
import { loginAs, pickOrg } from "../helpers/auth";
import { createDraftOrder, tenantIdFromUrl } from "../helpers/orders";

test("dual-org user switches org and does not see previous org orders", async ({
  page,
}) => {
  await loginAs(page, "sales@aftab.test");
  await pickOrg(page, /Aftab/);
  const aftabTenantId = tenantIdFromUrl(page.url());
  const orderId = await createDraftOrder(page, "1");

  // Order detail has no shell nav; switch via org picker route.
  await page.goto("/orgs");
  await pickOrg(page, /Baran/);
  const baranTenantId = tenantIdFromUrl(page.url());
  expect(baranTenantId).not.toBe(aftabTenantId);

  await page.getByRole("link", { name: "سفارش‌ها" }).click();
  await expect(page.getByText(orderId.slice(0, 8))).toHaveCount(0);
  await page.goto(`/t/${baranTenantId}/orders/${orderId}`);
  await expect(page.getByText(/یافت نشد|اجازه/).first()).toBeVisible({
    timeout: 30_000,
  });
});
