const { chromium } = require("playwright");

const TARGET = process.env.DASHBOARD_URL || "http://localhost:3000";

async function main() {
  const browser = await chromium.launch({ args: ["--no-sandbox"] });
  const page = await (await browser.newContext({ viewport: { width: 1600, height: 1000 } })).newPage();

  const perUrl = new Map();
  const samples = [];
  const started = Date.now();

  page.on("websocket", (ws) => {
    const url = ws.url();
    const stat = perUrl.get(url) || { opened: 0, frames: 0, closed: 0, errors: 0, firstAt: null };
    stat.opened += 1;
    perUrl.set(url, stat);

    ws.on("framereceived", (f) => {
      stat.frames += 1;
      if (stat.firstAt === null) stat.firstAt = (Date.now() - started) / 1000;
      if (samples.length < 2 && url.includes("/ws/dashboard") && typeof f.payload === "string") {
        samples.push(`${url}\n    ${f.payload.slice(0, 700)}`);
      }
    });
    ws.on("socketerror", () => { stat.errors += 1; });
    ws.on("close", () => { stat.closed += 1; });
  });

  page.on("console", (m) => {
    const t = m.text();
    if (m.type() === "error" || t.startsWith("[WS]")) console.log(`console ${m.type()}: ${t.slice(0, 160)}`);
  });

  await page.goto(TARGET, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(25000);

  console.log("\n--- per socket url ---");
  for (const [url, s] of perUrl) {
    console.log(`${url}`);
    console.log(`    opened ${s.opened}  frames ${s.frames}  closed ${s.closed}  errors ${s.errors}  first ${s.firstAt ?? "never"}`);
  }

  console.log("\n--- sample payloads ---");
  console.log(samples.length ? samples.join("\n") : "  none over 40 chars");

  await browser.close();
}

main().catch((error) => { console.error(error.message); process.exit(1); });
