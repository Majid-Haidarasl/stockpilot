/**
 * Capture Phase 4.5 Run 6 product-images screenshot gallery.
 * Prefer BASE_URL=http://localhost:5173 against the main compose.dev stack.
 */
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(
  __dirname,
  "..",
  "..",
  "..",
  "docs",
  "reports",
  "phase45-run6-screenshots",
);
fs.mkdirSync(outDir, { recursive: true });

const baseURL = process.env.BASE_URL ?? "http://localhost:5173";
const password = process.env.E2E_PASSWORD ?? "Passw0rd!";

async function login(page, email) {
  await page.goto("/login");
  await page.getByRole("button", { name: "ورود" }).click();
  await page.locator("#username, input[name='username']").first().fill(email);
  await page.locator("#password, input[name='password']").first().fill(password);
  await page.locator("#kc-login, input[type='submit'], button[type='submit']").first().click();
  await page.waitForURL(
    (url) => url.pathname === "/orgs" || url.pathname.startsWith("/t/"),
    { timeout: 60_000 },
  );
}

async function pickOrg(page, orgName) {
  if (!page.url().includes("/orgs")) await page.goto("/orgs");
  await page.getByText("انتخاب سازمان").waitFor({ timeout: 30_000 });
  await page.getByRole("button", { name: orgName }).first().click();
  await page.waitForURL((url) => /\/t\/[^/]+/.test(url.pathname), { timeout: 30_000 });
}

async function shot(page, name) {
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true });
  console.log("wrote", name);
}

async function main() {
  const browser = await chromium.launch({ headless: true });

  // Light desktop — admin gallery
  {
    const context = await browser.newContext({
      baseURL,
      locale: "fa-IR",
      viewport: { width: 1440, height: 900 },
      colorScheme: "light",
    });
    await context.addInitScript(() => localStorage.setItem("stockpilot.colorMode", "light"));
    const page = await context.newPage();
    await login(page, "admin@aftab.test");
    await pickOrg(page, /Aftab|آفتاب/);
    const tenantId = page.url().match(/\/t\/([^/]+)/)?.[1];
    await page.goto(`/t/${tenantId}/products`);
    await page.waitForLoadState("networkidle");
    await shot(page, "products-list-light-desktop");
    await page.getByRole("button", { name: "تصاویر" }).first().click();
    await page.getByRole("dialog").waitFor();
    await shot(page, "product-gallery-admin-light-desktop");
    // Force a client validation error
    const input = page.locator('input[type="file"]');
    await input.setInputFiles({
      name: "bad.gif",
      mimeType: "image/gif",
      buffer: Buffer.from("GIF89a"),
    });
    await page.waitForTimeout(400);
    await shot(page, "upload-error-light-desktop");
    await page.getByRole("button", { name: "بستن" }).click();
    await page.goto(`/t/${tenantId}/orders/new`);
    await page.waitForLoadState("networkidle");
    await shot(page, "draft-picker-light-desktop");
    await context.close();
  }

  // Viewer read-only gallery
  {
    const context = await browser.newContext({
      baseURL,
      locale: "fa-IR",
      viewport: { width: 1440, height: 900 },
      colorScheme: "light",
    });
    await context.addInitScript(() => localStorage.setItem("stockpilot.colorMode", "light"));
    const page = await context.newPage();
    await login(page, "viewer@baran.test");
    await pickOrg(page, /Baran|باران/);
    const tenantId = page.url().match(/\/t\/([^/]+)/)?.[1];
    await page.goto(`/t/${tenantId}/products`);
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: "تصاویر" }).first().click();
    await page.getByRole("dialog").waitFor();
    await shot(page, "product-gallery-viewer-light-desktop");
    await context.close();
  }

  // Dark desktop products
  {
    const context = await browser.newContext({
      baseURL,
      locale: "fa-IR",
      viewport: { width: 1440, height: 900 },
      colorScheme: "dark",
    });
    await context.addInitScript(() => localStorage.setItem("stockpilot.colorMode", "dark"));
    const page = await context.newPage();
    await login(page, "admin@aftab.test");
    await pickOrg(page, /Aftab|آفتاب/);
    const tenantId = page.url().match(/\/t\/([^/]+)/)?.[1];
    await page.goto(`/t/${tenantId}/products`);
    await page.waitForLoadState("networkidle");
    await shot(page, "products-list-dark-desktop");
    await page.getByRole("button", { name: "تصاویر" }).first().click();
    await page.getByRole("dialog").waitFor();
    await shot(page, "product-gallery-admin-dark-desktop");
    await context.close();
  }

  // Mobile 390
  {
    const context = await browser.newContext({
      baseURL,
      locale: "fa-IR",
      viewport: { width: 390, height: 844 },
      colorScheme: "light",
    });
    await context.addInitScript(() => localStorage.setItem("stockpilot.colorMode", "light"));
    const page = await context.newPage();
    await login(page, "admin@aftab.test");
    await pickOrg(page, /Aftab|آفتاب/);
    const tenantId = page.url().match(/\/t\/([^/]+)/)?.[1];
    await page.goto(`/t/${tenantId}/products`);
    await page.waitForLoadState("networkidle");
    await shot(page, "products-list-mobile-390");
    await page.getByRole("button", { name: "تصاویر" }).first().click();
    await page.getByRole("dialog").waitFor();
    await shot(page, "product-gallery-admin-mobile-390");
    await context.close();
  }

  await browser.close();
  console.log("done", outDir);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
