const { chromium } = require("playwright");
const path = require("path");

const TARGET = process.env.DASHBOARD_URL || "http://localhost:3000";
const OUT_DIR = process.env.SHOT_DIR || "F:/XAI Project/results/live/shots";

/* Text of the newest row. Pausing must hold this steady while the socket keeps
   delivering, which is the whole point of the control: an operator reading a
   row should not have it scroll away mid sentence. */
async function topRow(page) {
  return page.locator(".feed-row").first().innerText().catch(() => "");
}

async function main() {
  const browser = await chromium.launch({ args: ["--no-sandbox"] });
  const page = await (await browser.newContext({ viewport: { width: 1600, height: 1000 } })).newPage();

  await page.goto(TARGET, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(20000);

  await page.getByText(/^device:synthetic-device-\d+$/).first().click({ force: true });
  await page.waitForSelector("text=Back to Overview", { timeout: 20000 });
  await page.waitForTimeout(6000);

  const beforePause = await topRow(page);
  await page.waitForTimeout(3000);
  const streamingMoved = (await topRow(page)) !== beforePause;
  console.log(`newest row changes while streaming (proves live): ${streamingMoved}`);

  const pause = page.getByRole("button", { name: /^pause$/i }).first();
  await pause.click({ force: true });
  const atPause = await topRow(page);
  await page.waitForTimeout(8000);
  const afterWait = await topRow(page);
  console.log(`newest row held still for 8s while paused: ${atPause === afterWait}`);

  const pendingBadge = page.locator("text=/^\\d+ new$/");
  const pendingCount = await pendingBadge.count();
  console.log(`pending-while-paused badge shown: ${pendingCount > 0}`);
  if (pendingCount > 0) console.log(`  badge reads: ${await pendingBadge.first().innerText()}`);

  const shot = path.join(OUT_DIR, "03_feed_paused.png");
  await page.screenshot({ path: shot, fullPage: true });
  console.log(`wrote ${shot}`);

  const resume = page.getByRole("button", { name: /^resume$/i }).first();
  console.log(`resume control present while paused: ${(await resume.count()) > 0}`);
  await resume.click({ force: true });
  await page.waitForTimeout(3000);
  console.log(`newest row moves again after resume: ${(await topRow(page)) !== afterWait}`);

  await browser.close();
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
