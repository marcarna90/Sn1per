// Browser end-to-end smoke test (Playwright + Chromium) against the stack started by run.sh.
// Drives the real UI served by nginx: login, authorisation, scan, results, reload (silent
// refresh through the HttpOnly cookie), mobile layout, logout. Fails on any CSP violation,
// console error, page error or unexpected HTTP error status.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const base = process.env.E2E_BASE_URL;
const email = process.env.E2E_UI_ADMIN_EMAIL;
const password = process.env.E2E_PASSWORD;
const shots = process.env.E2E_SHOTS || path.join(process.cwd(), "e2e-screenshots");
fs.mkdirSync(shots, { recursive: true });

const results = [];
function check(name, ok, detail = "") {
  results.push([name, Boolean(ok), String(detail)]);
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${name}${detail === "" ? "" : `  [${detail}]`}`);
  return Boolean(ok);
}

// HTTP errors the scenario provokes on purpose (anything else >= 400 is a failure).
const expectedErrors = [
  ["POST", 401, "/api/v1/auth/refresh"], // first visit / after logout: no session yet
  ["POST", 401, "/api/v1/auth/login"], // deliberate wrong password
  ["POST", 403, "/api/v1/scans"], // deliberate out-of-scope target
];

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: 2,
    locale: "fr-FR",
  });
  const page = await context.newPage();
  const problems = [];
  const httpErrors = [];
  await page.addInitScript(() => {
    window.__csp = [];
    document.addEventListener("securitypolicyviolation", (e) =>
      window.__csp.push(`${e.violatedDirective} ${e.blockedURI}`),
    );
  });
  page.on("console", (m) => {
    const text = m.text();
    // "Failed to load resource" lines mirror the HTTP errors tracked separately below.
    if (["error", "warning"].includes(m.type()) && !text.startsWith("Failed to load resource")) {
      problems.push(`console.${m.type()}: ${text}`);
    }
  });
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("requestfailed", (r) => problems.push(`requestfailed: ${r.url()} ${r.failure()?.errorText}`));
  page.on("response", (r) => {
    if (r.status() >= 400) {
      httpErrors.push([r.request().method(), r.status(), new URL(r.url()).pathname]);
    }
  });

  try {
    console.log("\n[ui 1] login screen and authentication");
    await page.goto(`${base}/`);
    await page.waitForURL(/\/login$/);
    check("unauthenticated visit redirects to /login", true, page.url());
    check("login heading", await page.getByRole("heading", { name: "Connexion" }).isVisible());
    check(
      "signature shown on the login screen",
      await page.getByText("Designed & Developed by Ronald TSR").isVisible(),
    );
    await page.locator("#email").fill(email);
    await page.locator("#password").fill("definitely-wrong-password");
    await page.getByRole("button", { name: "Se connecter" }).click();
    const alert = page.getByRole("alert").first();
    await alert.waitFor({ timeout: 10000 });
    const alertText = (await alert.innerText()).trim();
    check("wrong password shows a generic error", alertText.length > 0, alertText);
    check("rejected password cleared from the field", (await page.locator("#password").inputValue()) === "");
    await page.locator("#password").fill(password);
    await page.getByRole("button", { name: "Se connecter" }).click();
    const nav = page.getByRole("navigation", { name: "Navigation principale" });
    await nav.waitFor({ timeout: 15000 });
    check("login succeeds, main navigation visible", await nav.isVisible());
    const cookies = await context.cookies();
    const refresh = cookies.find((c) => c.name === "neo_refresh");
    check(
      "refresh cookie: HttpOnly, SameSite=Strict, scoped to /api/v1/auth",
      refresh && refresh.httpOnly && refresh.sameSite === "Strict" && refresh.path === "/api/v1/auth",
      refresh ? `${refresh.httpOnly} ${refresh.sameSite} ${refresh.path}` : "missing",
    );
    const leaked = await page.evaluate(() =>
      JSON.stringify({ ...localStorage }) + JSON.stringify({ ...sessionStorage }) + document.cookie,
    );
    check("no token in localStorage / sessionStorage / JS-readable cookies", !/ey[A-Za-z0-9_-]{10,}/.test(leaked), leaked.slice(0, 60));

    console.log("\n[ui 2] scope: authorise a domain, dry-run it");
    await nav.getByRole("link", { name: "Périmètre" }).click();
    await page.locator("#entry-value").fill("lab.test");
    await page.getByLabel("Inclure les sous-domaines").check();
    await page.getByRole("button", { name: "Ajouter", exact: true }).click();
    await page.getByRole("cell", { name: "lab.test" }).first().waitFor({ timeout: 10000 });
    check("authorisation lab.test listed", true);
    await page.locator("#check-input").fill("ui.lab.test");
    await page.getByRole("button", { name: "Tester" }).click();
    const verdict = page.getByRole("status", { name: "Résultat du test" });
    await verdict.waitFor({ timeout: 10000 });
    const verdictText = await verdict.innerText();
    check("dry run: allowed with the validated address", /Autorisée/.test(verdictText) && /93\.184\.216\.35/.test(verdictText), verdictText.replace(/\n/g, " | "));
    await page.locator("#check-input").fill("127.0.0.1");
    await page.getByRole("button", { name: "Tester" }).click();
    await page.getByText(/Refusée/).waitFor({ timeout: 10000 });
    check("dry run: loopback refused", true, (await page.getByText(/Refusée/).innerText()).trim());

    console.log("\n[ui 3] scan through the real worker");
    await nav.getByRole("link", { name: "Scans", exact: true }).click();
    await page.locator("#scan-target").fill("www.other.test");
    await page.getByRole("button", { name: "Lancer le scan" }).click();
    await page.getByRole("alert").first().waitFor({ timeout: 10000 });
    check("out-of-scope scan refused in the UI, stays on /scans", /\/scans$/.test(page.url()), (await page.getByRole("alert").first().innerText()).trim());
    await page.locator("#scan-target").fill("ui.lab.test");
    await page.getByRole("button", { name: "Lancer le scan" }).click();
    await page.waitForURL(/\/scans\/[0-9a-f-]{36}$/, { timeout: 15000 });
    const detailUrl = page.url();
    await page.getByText("Terminé", { exact: true }).first().waitFor({ timeout: 90000 });
    check("scan reaches « Terminé »", true, detailUrl);
    const table = page.getByRole("table", { name: "Résultats du scan" });
    await table.waitFor({ timeout: 15000 });
    const tableText = await table.innerText();
    check("findings table shows the DNS answers", /93\.184\.216\.35/.test(tableText) && /A record/.test(tableText), tableText.split("\n").length + " lines");
    await page.screenshot({ path: path.join(shots, "scan-detail-desktop.png"), fullPage: true });

    console.log("\n[ui 4] reload keeps the session (silent refresh via HttpOnly cookie)");
    await page.reload();
    await page.getByRole("table", { name: "Résultats du scan" }).waitFor({ timeout: 20000 });
    check("after F5 still authenticated on the same page", page.url() === detailUrl, page.url());

    console.log("\n[ui 5] mobile layout");
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(`${base}/scans`);
    await page.getByRole("heading", { name: "Scans" }).first().waitFor({ timeout: 15000 });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check("no horizontal page scroll at 375px", overflow <= 0, `overflow=${overflow}px`);
    await page.screenshot({ path: path.join(shots, "scans-mobile.png"), fullPage: true });
    await page.setViewportSize({ width: 1280, height: 800 });

    console.log("\n[ui 6] logout");
    await page.getByRole("button", { name: "Se déconnecter" }).click();
    await page.waitForURL(/\/login/, { timeout: 15000 });
    check("logout returns to /login", true, page.url());
    await page.goto(`${base}/scans`);
    await page.waitForURL(/\/login/, { timeout: 15000 });
    check("protected page redirects to /login after logout", true);
    await page.screenshot({ path: path.join(shots, "login-desktop.png") });

    console.log("\n[ui 7] cleanliness");
    const csp = await page.evaluate(() => window.__csp);
    check("zero CSP violations", csp.length === 0, csp.join("; "));
    const unexpected = httpErrors.filter(
      ([method, status, p]) => !expectedErrors.some(([m, s, ep]) => m === method && s === status && ep === p),
    );
    check("no unexpected HTTP error responses", unexpected.length === 0, JSON.stringify(unexpected));
    check("every provoked error actually happened", expectedErrors.every(([m, s, p]) => httpErrors.some(([hm, hs, hp]) => hm === m && hs === s && hp === p)), JSON.stringify(httpErrors.map((e) => e.join(" "))));
    check("no console errors/warnings, page errors or failed requests", problems.length === 0, problems.join(" | "));
  } catch (error) {
    check("browser scenario completed", false, String(error).split("\n")[0]);
    await page.screenshot({ path: path.join(shots, "failure.png"), fullPage: true }).catch(() => {});
  } finally {
    await browser.close();
  }

  const failed = results.filter(([, ok]) => !ok);
  console.log(`\n==== Browser smoke: ${results.length - failed.length} passed, ${failed.length} failed ====`);
  failed.forEach(([name]) => console.log(`  FAILED: ${name}`));
  console.log(`screenshots: ${shots}`);
  process.exit(failed.length ? 1 : 0);
})();
