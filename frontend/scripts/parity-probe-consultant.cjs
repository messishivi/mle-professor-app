// One-off parity probe: dump the Streamlit Consultant pane visible text.
// NOT part of the test suite (no assertions, read-only).
// Run with PLAYWRIGHT_BROWSERS_PATH=0 node scripts/parity-probe-consultant.cjs
// (requires the Streamlit parity reference on 127.0.0.1:8501).
//
// Read-only by construction: it clicks the Consultant radio and reads
// innerText; it never types into the chat box, never sends, and never
// touches the sidebar settings.
const { chromium } = require("@playwright/test");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto("http://127.0.0.1:8501", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(6000); // Streamlit boots over websocket
  // Click the Consultant radio explicitly so a previous manual session on a
  // different tab cannot contaminate the dump.
  const consultant = page
    .locator("label")
    .filter({ hasText: /Consultant/ })
    .first();
  if (await consultant.count()) {
    await consultant.click();
    await page.waitForTimeout(2500);
  }
  const text = await page.evaluate(() => document.body.innerText);
  console.log("=== STREAMLIT CONSULTANT PANE (visible text) ===");
  console.log(text.replace(/\n{3,}/g, "\n\n").slice(0, 6000));
  await browser.close();
})().catch((e) => {
  console.error("PROBE FAILED:", e.message);
  process.exit(1);
});
