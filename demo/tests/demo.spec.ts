import { expect, test, type Page } from "@playwright/test";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const ORIGIN = "http://127.0.0.1:4173";
const VIEWPORTS = [
  { width: 1366, height: 768 },
  { width: 1920, height: 1080 },
];
const NAMES = ["start", "question", "system", "case", "flip", "clock", "findings"];
const OUT = join(__dirname, "..", "screenshots");
const FALLBACK = join(__dirname, "..", "fallback");

type Configuration = {
  configuration: string;
  overall: { abstention_rate: { value: number } };
  per_regime: Record<string, { abstention_rate: { value: number } }>;
};
const configurations: Configuration[] = JSON.parse(
  readFileSync(join(__dirname, "..", "public", "data", "configurations.json"), "utf-8"),
).configurations;
const rate = (name: string, regime: string) =>
  configurations.find((c) => c.configuration === name)!.per_regime[regime].abstention_rate.value;

async function layoutProblems(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const problems: string[] = [];
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const root = document.documentElement;
    if (root.scrollWidth > vw + 1) problems.push(`page scrolls sideways: ${root.scrollWidth} > ${vw}`);
    if (root.scrollHeight > vh + 1) problems.push(`page scrolls down: ${root.scrollHeight} > ${vh}`);
    const stage = document.querySelector(".stage") as HTMLElement | null;
    if (stage && stage.scrollHeight > stage.clientHeight + 1) problems.push(`stage clipped: ${stage.scrollHeight} > ${stage.clientHeight}`);
    const stageBox = stage?.getBoundingClientRect();
    const visible = (el: Element) => {
      const style = getComputedStyle(el);
      if (style.display === "none" || style.visibility === "hidden") return false;
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    };
    const describe = (el: Element) => `${el.tagName.toLowerCase()}.${(el.getAttribute("class") || "").split(" ")[0]} "${(el.textContent || "").trim().slice(0, 40)}"`;
    document.querySelectorAll(".topbar *, .stage *, .footbar *").forEach((el) => {
      if (!visible(el)) return;
      if (el.closest(".term-tip")) return;
      const hasText = Array.from(el.childNodes).some((n) => n.nodeType === 3 && (n.textContent || "").trim().length > 0);
      if (!hasText) return;
      const r = el.getBoundingClientRect();
      if (r.right > vw + 1 || r.left < -1 || r.bottom > vh + 1) problems.push(`off screen: ${describe(el)}`);
      if (stageBox && el.closest(".stage") && r.bottom > stageBox.bottom + 1) problems.push(`below stage: ${describe(el)}`);
      const html = el as HTMLElement;
      if (html.clientWidth > 0 && !html.classList.contains("source")) {
        const style = getComputedStyle(html);
        if (html.scrollWidth > html.clientWidth + 1 && style.overflowX !== "visible") problems.push(`text clipped: ${describe(el)}`);
      }
    });
    return problems;
  });
}

async function visibleWords(page: Page): Promise<number> {
  return page.evaluate(() => {
    const stage = document.querySelector(".stage") as HTMLElement | null;
    return stage ? stage.innerText.split(/\s+/).filter((w) => /[A-Za-z]/.test(w)).length : 0;
  });
}

async function open(page: Page, index: number) {
  await page.goto(`/#${index}`);
  await page.evaluate(() => document.fonts.ready);
  await expect(page.getByTestId(`screen-${index}`)).toBeVisible();
  await expect(page.locator(".loading")).toHaveCount(0);
  await page.waitForTimeout(700);
}

const STATES: Record<number, { suffix: string; act: (page: Page) => Promise<void> }> = {
  1: { suffix: "after", act: async (p) => { await p.getByTestId("remove-guardrail").click(); await p.waitForTimeout(1000); } },
  2: { suffix: "sensor", act: async (p) => { await p.locator('[data-block="sensor"]').first().click(); await p.waitForTimeout(300); } },
  3: { suffix: "verdict", act: async (p) => { for (let i = 0; i < 3; i++) await p.getByTestId("case-step").click(); await p.waitForTimeout(800); } },
  4: { suffix: "unknown-off", act: async (p) => { await p.locator('[data-switch="U"]').click(); await p.waitForTimeout(800); } },
  5: { suffix: "bug-on", act: async (p) => { await p.getByTestId("clock-switch").click(); await p.waitForTimeout(400); } },
};

for (const viewport of VIEWPORTS) {
  test(`every screen at ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.emulateMedia({ reducedMotion: "reduce" });
    const errors: string[] = [];
    const requests: string[] = [];
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("request", (r) => requests.push(r.url()));

    const folder = join(OUT, `${viewport.width}x${viewport.height}`);
    mkdirSync(folder, { recursive: true });
    mkdirSync(FALLBACK, { recursive: true });
    const report: Record<string, unknown>[] = [];

    for (let i = 0; i < NAMES.length; i++) {
      await open(page, i);
      const file = `${String(i)}-${NAMES[i]}.png`;
      await page.screenshot({ path: join(folder, file) });
      if (viewport.width === 1920) await page.screenshot({ path: join(FALLBACK, file) });
      const problems = await layoutProblems(page);
      const words = await visibleWords(page);
      report.push({ screen: i, state: "initial", words, problems });
      const state = STATES[i];
      if (state) {
        await state.act(page);
        const after = `${String(i)}-${NAMES[i]}-${state.suffix}.png`;
        await page.screenshot({ path: join(folder, after) });
        if (viewport.width === 1920) await page.screenshot({ path: join(FALLBACK, after) });
        report.push({ screen: i, state: state.suffix, words: await visibleWords(page), problems: await layoutProblems(page) });
      }
    }

    await open(page, 0);
    await page.keyboard.press("p");
    await expect(page.locator(".notes")).toBeVisible();
    await page.keyboard.press("p");
    await page.keyboard.press("ArrowRight");
    await expect(page.getByTestId("screen-1")).toBeVisible();
    await page.keyboard.press("4");
    await expect(page.getByTestId("screen-4")).toBeVisible();
    await page.getByRole("button", { name: "Why this matters" }).click();
    await expect(page.locator("#why-panel")).toBeVisible();
    report.push({ screen: 4, state: "drawer-open", words: await visibleWords(page), problems: await layoutProblems(page) });

    const external = requests.filter((u) => !u.startsWith(ORIGIN) && !u.startsWith("data:") && !u.startsWith("blob:"));
    writeFileSync(join(folder, "report.json"), JSON.stringify({ viewport, errors, requests, external, report }, null, 1));
    const allProblems = report.flatMap((r) => (r.problems as string[]).map((p) => `screen ${r.screen} ${r.state}: ${p}`));
    expect(errors, "console errors").toEqual([]);
    expect(external, "external requests").toEqual([]);
    expect(allProblems, "layout problems").toEqual([]);
  });
}

test("screen 4 numbers move only when a wired guardrail is flipped", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await open(page, 4);
  const number = page.getByTestId("flip-number");
  const message = page.getByTestId("flip-message");
  const log: string[] = [];

  for (const regime of ["sparse", "unknown_attack"]) {
    await page.locator(`.readout [data-regime="${regime}"]`).click();
    const start = rate("allon", regime).toFixed(4);
    await expect(number).toHaveText(start);

    await page.locator('[data-switch="P"]').click();
    await expect(number).toHaveText(start);
    await expect(message).toContainText("not connected");
    log.push(`${regime}: flip P   ${start} -> ${await number.textContent()}  "${await message.textContent()}"`);
    await page.locator('[data-switch="P"]').click();

    await page.locator('[data-switch="flag"]').click();
    await expect(number).toHaveText(start);
    await expect(message).toContainText("not connected");
    log.push(`${regime}: flip flag ${start} -> ${await number.textContent()}  "${await message.textContent()}"`);
    await page.locator('[data-switch="flag"]').click();

    const expected = rate("U", regime);
    const delta = expected - rate("allon", regime);
    await page.locator('[data-switch="U"]').click();
    await expect(number).toHaveText(expected.toFixed(4));
    log.push(`${regime}: flip U   ${start} -> ${await number.textContent()}  measured change ${delta.toFixed(4)}  "${await message.textContent()}"`);
    await page.locator('[data-switch="U"]').click();
    await expect(number).toHaveText(start);
  }
  writeFileSync(join(OUT, "screen4-test.txt"), log.join("\n") + "\n");
});
