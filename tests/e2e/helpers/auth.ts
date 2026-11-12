import type { Page } from "@playwright/test";

const password = process.env.E2E_PASSWORD ?? "Passw0rd!";

export async function loginAs(page: Page, email: string): Promise<void> {
  await page.goto("/login");
  await page.getByRole("button", { name: "ورود" }).click();

  // Keycloak login form
  await page.locator("#username, input[name='username']").first().fill(email);
  await page.locator("#password, input[name='password']").first().fill(password);
  await page.locator("#kc-login, input[type='submit'], button[type='submit']").first().click();

  // Match pathname only — avoid matching return_to=.../orgs on /auth/login.
  await page.waitForURL(
    (url) => url.pathname === "/orgs" || url.pathname.startsWith("/t/"),
    { timeout: 60_000 },
  );
}

export async function pickOrg(page: Page, orgName: string | RegExp): Promise<void> {
  if (!page.url().includes("/orgs")) {
    await page.goto("/orgs");
  }
  await page.getByText("انتخاب سازمان").waitFor({ timeout: 30_000 });
  // MUI ListItemButton exposes role=button; name includes primary org name.
  await page.getByRole("button", { name: orgName }).first().click();
  await page.waitForURL((url) => /\/t\/[^/]+/.test(url.pathname), { timeout: 30_000 });
}

export async function logout(page: Page): Promise<void> {
  // Clear browser storage / cookies for a fresh session between roles.
  await page.context().clearCookies();
  await page.goto("/login");
}
