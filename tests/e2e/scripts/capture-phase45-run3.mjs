/**
 * Capture Phase 4.5 Run 3 Part A screenshot gallery.
 * Run inside the Playwright e2e container against edge-e2e.
 */
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, "..", "artifacts", "phase45-run3-screenshots");
fs.mkdirSync(outDir, { recursive: true });

const baseURL = process.env.BASE_URL ?? "http://edge-e2e";
const password = process.env.E2E_PASSWORD ?? "Passw0rd!";

const VARIANTS = [
  { label: "light-desktop", mode: "light", viewport: { width: 1440, height: 900 } },
  { label: "dark-desktop", mode: "dark", viewport: { width: 1440, height: 900 } },
  { label: "mobile-390", mode: "light", viewport: { width: 390, height: 844 } },
];

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
  await page.waitForTimeout(350);
  await page.screenshot({
    path: path.join(outDir, `${name}.png`),
    fullPage: true,
  });
  console.log("wrote", name);
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
  await shot(page, `login-${label}`);
  await page.goto("/no-such-top-level");
  await shot(page, `404-${label}`);
  await page.goto("/error");
  await shot(page, `error-${label}`);

  await login(page, "admin@aftab.test");
  await shot(page, `orgs-${label}`);
  await pickOrg(page, /Aftab/);
  const tenantMatch = page.url().match(/\/t\/([^/]+)/);
  const tenantId = tenantMatch?.[1];
  if (!tenantId) throw new Error("no tenant id");

  const paths = [
    ["dashboard", `/t/${tenantId}/dashboard`],
    ["orders", `/t/${tenantId}/orders`],
    ["orders-new", `/t/${tenantId}/orders/new`],
    ["products", `/t/${tenantId}/products`],
    ["inventory", `/t/${tenantId}/inventory`],
    ["customers", `/t/${tenantId}/customers`],
    ["members", `/t/${tenantId}/members`],
    ["notifications", `/t/${tenantId}/notifications`],
    ["tenant-404", `/t/${tenantId}/does-not-exist`],
  ];

  for (const [name, url] of paths) {
    await page.goto(url);
    await page.waitForLoadState("networkidle");
    await shot(page, `${name}-${label}`);
  }

  await page.goto(`/t/${tenantId}/orders`);
  await page.waitForLoadState("networkidle");
  const orderLink = page.locator('a[href*="/orders/"]').first();
  if (await orderLink.count()) {
    await orderLink.click();
    await page.waitForLoadState("networkidle");
  }
  await shot(page, `orders-detail-${label}`);

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
