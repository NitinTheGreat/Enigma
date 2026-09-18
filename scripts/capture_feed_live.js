const { chromium } = require("playwright");
const path = require("path");

const TARGET = process.env.DASHBOARD_URL || "http://localhost:3000";
const OUT_DIR = process.env.SHOT_DIR || "F:/XAI Project/results/live/shots";

async function main() {
  const browser = await chromium.launch({ args: ["--no-sandbox"] });
  const page = await (await browser.newContext({ viewport: { width: 1600, height: 1000 } })).newPage();

  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });

  await page.goto(TARGET, { waitUntil: "domcontentloaded", timeout: 60000 });

  await page.waitForTimeout(6000);
  const seeded = await page.locator("text=/^device:synthetic-device-\\d+$/").count();
  console.log(`situations visible 6s after load (snapshot seeding): ${seeded}`);

  /* The first analysis push lands around ten seconds in, because the reasoning
     layer must finish a full Gemini pass before the dashboard hears anything.
     Clicking earlier lands on a placeholder and proves nothing. */
  await page.waitForTimeout(14000);

  await page.getByText(/^device:synthetic-device-\d+$/).first().click({ force: true });
  await page.waitForSelector("text=Back to Overview", { timeout: 20000 });

  for (const at of [5, 10, 15, 20]) {
    await page.waitForTimeout(5000);
    const rows = await page.locator(".feed-row").count();
    console.log(`  t+${at}s in detail view: ${rows} feed rows`);
  }

  const liveRows = await page.locator(".feed-row").count();
  console.log(`feed rows rendered WHILE STREAMING: ${liveRows}`);

  const shotLive = path.join(OUT_DIR, "04_feed_live.png");
  await page.screenshot({ path: shotLive, fullPage: true });
  console.log(`wrote ${shotLive}`);

  /* Scroll the feed itself, not the page, to reach history. */
  const feedScroller = page.locator(".feed-row").first();
  await feedScroller.hover().catch(() => {});
  await page.mouse.wheel(0, 600);
  await page.waitForTimeout(2500);

  const jump = page.getByRole("button", { name: /jump to latest/i });
  console.log(`jump-to-latest control appeared after scrolling: ${(await jump.count()) > 0}`);

  const shotHistory = path.join(OUT_DIR, "05_feed_history.png");
  await page.screenshot({ path: shotHistory, fullPage: true });
  console.log(`wrote ${shotHistory}`);

  console.log("--- console errors ---");
  console.log(errors.length ? errors.slice(0, 6).map((e) => `  ${e}`).join("\n") : "  none");

  await browser.close();
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
