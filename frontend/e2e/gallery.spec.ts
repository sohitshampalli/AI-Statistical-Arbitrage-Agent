// Gallery screenshots at 1280, 1440 and 1920 px, the provenance drawer and
// hover, and a check that the page logs no console errors.
import { expect, test, type Page } from "@playwright/test";

const OUT = "../reports/screenshots";

async function openGallery(page: Page, errors: string[]) {
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(String(err)));
  await page.goto("/#/dev/components");
  await page.waitForSelector(".js-plotly-plot .main-svg");
  await page.evaluate(() => document.fonts.ready);
  await page.waitForLoadState("networkidle");
}

for (const width of [1280, 1440, 1920]) {
  test(`gallery at ${width}`, async ({ page }) => {
    const errors: string[] = [];
    await page.setViewportSize({ width, height: 900 });
    await openGallery(page, errors);
    // 1440 is the reference width and is committed; the others are layout
    // checks kept out of git (reports/screenshots/layout-checks/).
    const dir = width === 1440 ? OUT : `${OUT}/layout-checks`;
    await page.screenshot({ path: `${dir}/gallery-${width}.png`, fullPage: true });
    // the error example is a deliberate 404; anything else is a defect
    expect(errors.filter((e) => !e.includes("404"))).toEqual([]);
  });
}

test("provenance hover and drawer", async ({ page }) => {
  const errors: string[] = [];
  await openGallery(page, errors);
  const section = page.locator("section[aria-labelledby='g-kpi']");
  const kpi = section.getByRole("button").first();
  await kpi.scrollIntoViewIfNeeded();
  await kpi.hover();
  await expect(page.getByRole("tooltip")).toBeVisible();
  const box = await section.boundingBox();
  if (box) {
    await page.screenshot({ path: `${OUT}/gallery-hover-1440.png`, fullPage: true, clip: { x: 0, y: box.y - 24, width: 1440, height: 420 } });
  }
  await kpi.click();
  const drawer = page.getByRole("dialog", { name: /Validation net Sharpe/ });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByText("Before terms check").first()).toBeVisible();
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${OUT}/gallery-drawer-1440.png` });
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
});
