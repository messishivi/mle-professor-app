// One-off parity probe: dump the Streamlit ML Pulse pane visible text.
// NOT part of the test suite (no assertions, read-only).
// Run with PLAYWRIGHT_BROWSERS_PATH=0 node scripts/parity-probe-pulse.cjs
// (requires the Streamlit parity reference on 127.0.0.1:8501).
const { chromium } = require("@playwright/test");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto("http://127.0.0.1:8501", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(6000); // Streamlit boots over websocket
  // The ML Pulse pane is the default radio view; click it explicitly to be
  // sure we are not on a different tab from a previous manual session.
  const pulse = page.locator("label").filter({ hasText: /Pulse/ }).first();
  if (await pulse.count()) {
    await pulse.click();
    await page.waitForTimeout(2500);
  }
  const text = await page.evaluate(() => document.body.innerText);
  console.log("=== STREAMLIT ML PULSE PANE (visible text) ===");
  console.log(text.replace(/\n{3,}/g, "\n\n").slice(0, 6000));
  await browser.close();
})().catch((e) => {
  console.error("PROBE FAILED:", e.message);
  process.exit(1);
});
