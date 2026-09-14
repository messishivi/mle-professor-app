import { expect, test } from "@playwright/test";

test("pulse page loads the live snapshot with nav, no page errors", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto("/");
  await expect(page).toHaveTitle(/MLE Professor/);
  await expect(
    page.getByRole("navigation", { name: "Sections" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Pulse" })).toBeVisible();

  // Live snapshot from the API (GET /pulse), not the P1 mock data.
  await expect(
    page.getByText(/updated \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC · \d+ items/),
  ).toBeVisible();
  // A live-feed topic (stable while the stored snapshot is unchanged —
  // e2e never clicks Refresh, so the DB snapshot is never mutated). The
  // topic string also appears in the card's "Paper ·" line, so scope the
  // assertion to the card heading.
  await expect(
    page.getByRole("heading", {
      name: "AutoResearch: Insight In, Hallucination Out",
    }),
  ).toBeVisible();
  await expect(page.locator("article")).not.toHaveCount(0);
  // Empty settings → empty stack → every item ranks "Set stack" and the
  // stack chip row says so.
  await expect(page.getByText("SET STACK", { exact: true }).first()).toBeVisible();
  await expect(
    page.getByText("not set — items rank as “Set stack”"),
  ).toBeVisible();
  // Live memos carry a verdict badge (heuristic origin, uppercased).
  await expect(page.getByText("Decision").first()).toBeVisible();
  await expect(page.getByText("WATCH", { exact: true }).first()).toBeVisible();
  // hf_daily items tag themselves "trending" (Streamlit parity).
  await expect(page.getByText("trending", { exact: true }).first()).toBeVisible();
  // No GROQ_API_KEY in this environment → Refine is disabled (app.py parity).
  const refineButtons = page.getByRole("button", { name: "Refine memo" });
  expect(await refineButtons.count()).toBeGreaterThan(0);
  await expect(refineButtons.first()).toBeDisabled();

  // regression: the nav must stay a non-scrolling container. The active
  // tab underline protrudes 1px below its link; any overflow-* value on
  // the nav (e.g. overflow-x-auto) promotes overflow-y to auto and draws
  // a vertical scrollbar on the navbar.
  const navOverflowY = await page.evaluate(() =>
    getComputedStyle(
      document.querySelector('nav[aria-label="Sections"]')!,
    ).overflowY,
  );
  expect(navOverflowY).toBe("visible");

  expect(errors).toEqual([]);
});

test("theme toggle switches to light and back", async ({ page }) => {
  await page.goto("/");
  const html = page.locator("html");
  await expect(html).not.toHaveAttribute("data-theme", "light");

  await page
    .getByRole("button", { name: /switch to light theme/i })
    .click();
  await expect(html).toHaveAttribute("data-theme", "light");

  await page
    .getByRole("button", { name: /switch to dark theme/i })
    .click();
  await expect(html).not.toHaveAttribute("data-theme", "light");
});

test("saved and consultant pages load", async ({ page }) => {
  // /saved is now a live view (P3a): empty state when nothing is marked read.
  await page.goto("/saved");
  await expect(page.getByRole("heading", { name: "Saved" })).toBeVisible();

  await page.goto("/consultant");
  await expect(page.getByText("consultant terminal")).toBeVisible();
});
