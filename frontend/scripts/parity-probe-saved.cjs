// One-off parity probe: dump the Streamlit Saved pane visible text.
// NOT part of the test suite (no assertions, read-only).
const { chromium } = require("@playwright/test");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto("http://127.0.0.1:8501", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(6000); // Streamlit boots over websocket
  // switch the view radio to "Saved"
  const saved = page
    .locator("label")
    .filter({ hasText: /^Saved$/ })
    .first();
  await saved.click();
  await page.waitForTimeout(2000);
  const text = await page.evaluate(() => document.body.innerText);
  console.log("=== STREAMLIT SAVED PANE (visible text) ===");
  console.log(text.replace(/\n{3,}/g, "\n\n").slice(0, 4000));
  await browser.close();
})().catch((e) => {
  console.error("PROBE FAILED:", e.message);
  process.exit(1);
});
