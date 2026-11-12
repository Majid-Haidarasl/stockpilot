import { expect, test } from "@playwright/test";
import { loginAs, logout, pickOrg } from "../helpers/auth";
import { createDraftOrder, tenantIdFromUrl } from "../helpers/orders";

test("org A order is invisible to org B in UI and API returns 404", async ({
  page,
  request,
}) => {
  await loginAs(page, "sales@aftab.test");
  await pickOrg(page, /Aftab/);
  const aftabTenantId = tenantIdFromUrl(page.url());
  const orderId = await createDraftOrder(page, "1");
  const aftabOrderUrl = page.url();

  await logout(page);
  await loginAs(page, "admin@baran.test");
  await pickOrg(page, /Baran/);
  const baranTenantId = tenantIdFromUrl(page.url());
  expect(baranTenantId).not.toBe(aftabTenantId);

  await page.getByRole("link", { name: "سفارش‌ها" }).click();
  await expect(page.getByText(orderId.slice(0, 8))).toHaveCount(0);

  await page.goto(`/t/${baranTenantId}/orders/${orderId}`);
  await expect(page.getByText(/یافت نشد|اجازه/).first()).toBeVisible({
    timeout: 30_000,
  });

  const apiBase = process.env.API_BASE_URL ?? "http://api:8000";
  const cookies = await page.context().cookies();
  const cookieHeader = cookies.map((c) => `${c.name}=${c.value}`).join("; ");
  const response = await request.get(
    `${apiBase}/api/v1/tenants/${baranTenantId}/orders/${orderId}`,
    { headers: { Cookie: cookieHeader } },
  );
  expect(response.status()).toBe(404);
});
