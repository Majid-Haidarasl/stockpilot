import { expect, test } from "@playwright/test";
import { loginAs, pickOrg } from "../helpers/auth";

test("viewer sees Persian denial and no inventory write form", async ({ page }) => {
  await loginAs(page, "viewer@baran.test");
  await pickOrg(page, /Baran/);
  await page.getByRole("link", { name: "موجودی" }).click();

  await expect(page.getByTestId("inventory-write-denied")).toBeVisible();
  await expect(page.getByTestId("inventory-write-denied")).toContainText(
    /اجازه تغییر موجودی/,
  );
  await expect(page.getByRole("button", { name: "ذخیره" })).toHaveCount(0);
});
