const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const TARGET = process.env.DASHBOARD_URL || "http://localhost:3000";
const OUT_DIR = process.env.SHOT_DIR || "F:/XAI Project/results/live/shots";
const SETTLE_MS = Number(process.env.SETTLE_MS || 25000);

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const browser = await chromium.launch({ args: ["--no-sandbox"] });
  const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  const page = await context.newPage();

  const consoleErrors = [];
  const pageErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(String(error)));

  console.log(`navigating to ${TARGET}`);
  await page.goto(TARGET, { waitUntil: "domcontentloaded", timeout: 60000 });

  await page.waitForTimeout(SETTLE_MS);

  const overview = path.join(OUT_DIR, "01_overview.png");
  await page.screenshot({ path: overview, fullPage: true });
  console.log(`wrote ${overview}`);

  const sidebarItems = await page.locator("aside button, [class*='sidebar'] button").count();
  console.log(`sidebar buttons found: ${sidebarItems}`);

  const bodyText = await page.locator("body").innerText();
  const headline = bodyText.split("\n").filter((line) => line.trim()).slice(0, 40);
  console.log("--- visible text, first 40 lines ---");
  headline.forEach((line) => console.log(`  ${line}`));

  const entityBadge = page.getByText(/^device:synthetic-device-\d+$/).first();
  const badgeCount = await entityBadge.count();
  console.log(`entity badges found: ${badgeCount}`);

  if (badgeCount > 0) {
    try {
      await entityBadge.click({ timeout: 15000, force: true });
      await page.waitForSelector("text=Back to Overview", { timeout: 20000 });
      await page.waitForTimeout(6000);
      const detail = path.join(OUT_DIR, "02_detail.png");
      await page.screenshot({ path: detail, fullPage: true });
      console.log(`wrote ${detail}`);

      const hypothesesPanel = page.locator("text=HYPOTHESES").first();
      if (await hypothesesPanel.count()) {
        const panelText = await page
          .locator("div")
          .filter({ hasText: /HYPOTHESES/ })
          .last()
          .innerText();
        console.log("--- hypotheses panel text ---");
        panelText
          .split("\n")
          .filter((line) => line.trim())
          .slice(0, 12)
          .forEach((line) => console.log(`  ${line}`));
      }
    } catch (error) {
      console.log(`could not open a situation detail view: ${error.message}`);
    }
  }

  console.log("--- console errors ---");
  if (consoleErrors.length === 0 && pageErrors.length === 0) {
    console.log("  none");
  } else {
    consoleErrors.slice(0, 10).forEach((line) => console.log(`  console: ${line}`));
    pageErrors.slice(0, 10).forEach((line) => console.log(`  pageerror: ${line}`));
  }

  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
