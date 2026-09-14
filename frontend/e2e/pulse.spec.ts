import { expect, test } from "@playwright/test";

test("pulse page loads with nav and paper cards, no page errors", async ({
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
  await expect(page.locator("article")).toHaveCount(8);
  // mock-pulse.ts contract: exactly two "adopt" verdicts
  await expect(page.getByText("ADOPT", { exact: true })).toHaveCount(2);
  await expect(page.getByText("✓ read")).toBeVisible();

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
