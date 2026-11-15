/**
 * Capture Phase 4.5 Run 3.5 screenshot gallery.
 * Run inside the Playwright e2e container against edge-e2e.
 */
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, "..", "artifacts", "phase45-run3_5-screenshots");
fs.mkdirSync(outDir, { recursive: true });

const baseURL = process.env.BASE_URL ?? "http://edge-e2e";
const password = process.env.E2E_PASSWORD ?? "Passw0rd!";

const VARIANTS = [
  { label: "light-desktop", mode: "light", viewport: { width: 1440, height: 900 } },
  { label: "dark-desktop", mode: "dark", viewport: { width: 1440, height: 900 } },
  { label: "mobile-390", mode: "light", viewport: { width: 390, height: 844 } },
];

async function openKeycloak(page) {
  await page.goto("/login");
  await page.getByRole("button", { name: "ورود" }).click();
  await page.locator("#username, input[name='username']").first().waitFor({ timeout: 60_000 });
}

async function loginFromKeycloak(page, email) {
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
  await page.waitForTimeout(400);
  await page.screenshot({
    path: path.join(outDir, `${name}.png`),
    fullPage: true,
  });
  console.log("wrote", name);
}

async function ensureZeroStockProduct(page, tenantId) {
  await page.goto(`/t/${tenantId}/products`);
  await page.waitForLoadState("networkidle");
  const sku = `Z0-${Date.now().toString().slice(-6)}`;
  await page.getByLabel("کد کالا (SKU)").fill(sku);
  await page.getByLabel("عنوان").fill("کالای بدون موجودی");
  await page.getByLabel("قیمت (ریال)").fill("1000");
  await page.getByRole("button", { name: "ذخیره" }).click();
  await page.waitForTimeout(800);
  return sku;
}

async function captureVariant(browser, { label, mode, viewport }) {
  const context = await browser.newContext({
    baseURL,
    locale: "fa-IR",
    viewport,
    colorScheme: mode === "dark" ? "dark" : "light",
  });
  await context.addInitScript((m) => {
    localStorage.setItem("stockpilot.colorMode", m);
  }, mode);

  const page = await context.newPage();

  await page.goto("/");
  await shot(page, `landing-${label}`);

  await page.goto("/login");
  await shot(page, `login-app-${label}`);

  await openKeycloak(page);
  await shot(page, `login-keycloak-${label}`);
  await loginFromKeycloak(page, "admin@aftab.test");
  await shot(page, `orgs-${label}`);

  await pickOrg(page, /Aftab/);
  const tenantMatch = page.url().match(/\/t\/([^/]+)/);
  const tenantId = tenantMatch?.[1];
  if (!tenantId) throw new Error("no tenant id");

  // Sidebar expanded / collapsed (desktop only)
  if (viewport.width >= 900) {
    await page.goto(`/t/${tenantId}/dashboard`);
    await page.waitForLoadState("networkidle");
    await shot(page, `sidebar-expanded-${label}`);
    const collapse = page.getByRole("button", { name: "جمع کردن منو" });
    if (await collapse.count()) {
      await collapse.click();
      await page.waitForTimeout(300);
      await shot(page, `sidebar-collapsed-${label}`);
      await page.getByRole("button", { name: "باز کردن منو" }).click();
    }
  }

  await page.goto(`/t/${tenantId}/dashboard`);
  await page.waitForLoadState("networkidle");
  await shot(page, `dashboard-${label}`);
  const fromField = page.getByLabel("از تاریخ به وقت تهران");
  if (await fromField.count()) {
    await fromField.click();
    await page.waitForTimeout(400);
    await shot(page, `dashboard-jalali-open-${label}`);
    await page.keyboard.press("Escape");
  }

  await page.goto(`/t/${tenantId}/orders`);
  await page.waitForLoadState("networkidle");
  await shot(page, `orders-${label}`);

  await ensureZeroStockProduct(page, tenantId);
  await page.goto(`/t/${tenantId}/products`);
  await page.waitForLoadState("networkidle");
  await shot(page, `products-zero-stock-${label}`);

  await page.goto(`/t/${tenantId}/inventory`);
  await page.waitForLoadState("networkidle");
  await shot(page, `inventory-zero-stock-${label}`);

  await page.goto(`/t/${tenantId}/customers`);
  await page.waitForLoadState("networkidle");
  const editBtn = page.getByRole("button", { name: /ویرایش/ }).first();
  if (await editBtn.count()) {
    await editBtn.click();
    await page.getByRole("dialog").waitFor({ timeout: 10_000 });
    await shot(page, `customers-edit-${label}`);
    await page.getByRole("button", { name: "انصراف" }).click();
  } else {
    await shot(page, `customers-${label}`);
  }

  await context.close();
}

const browser = await chromium.launch();
try {
  for (const variant of VARIANTS) {
    console.log("variant", variant.label);
    await captureVariant(browser, variant);
  }
} finally {
  await browser.close();
}

console.log("done →", outDir);
