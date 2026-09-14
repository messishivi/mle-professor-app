import { expect, test } from "@playwright/test";

// Runs against the real API (:8000) and the real dev DB. The single library
// paper ("Attention Is All You Need") is toggled read and restored, so the
// suite leaves the DB as it found it.

test("papers page loads the library from the live API", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto("/papers");
  await expect(page.getByRole("heading", { name: "Papers" })).toBeVisible();
  const heading = page.getByRole("heading", {
    name: "Attention Is All You Need",
  });
  await expect(heading).toBeVisible();
  await expect(
    page.getByRole("button", { name: /mark attention is all you need as read/i }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "cs.CL" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  // render_structured parity: category chips from summary_structured
  const row = page.getByRole("article").filter({ has: heading });
  await expect(row.getByText("cs.CL", { exact: true })).toBeVisible();
  await expect(row.getByText("cs.LG", { exact: true })).toBeVisible();

  expect(errors).toEqual([]);
});

test("papers search filters the live list", async ({ page }) => {
  await page.goto("/papers");
  await expect(
    page.getByRole("heading", { name: "Attention Is All You Need" }),
  ).toBeVisible();

  const search = page.getByLabel(/search papers/i);
  await search.fill("zzz-no-match-9412");
  await expect(
    page.getByText("No papers match “zzz-no-match-9412”."),
  ).toBeVisible();

  await search.fill("attention");
  await expect(
    page.getByRole("heading", { name: "Attention Is All You Need" }),
  ).toBeVisible();
  await search.fill("");
});

test("mark-read round trip persists and restores", async ({ page }) => {
  await page.goto("/papers");
  const heading = page.getByRole("heading", { name: "Attention Is All You Need" });
  await expect(heading).toBeVisible();

  const markRead = page.getByRole("button", {
    name: /mark attention is all you need as read/i,
  });
  await markRead.click();

  // persisted: the row shows its read state
  const markUnread = page.getByRole("button", {
    name: /mark attention is all you need as unread/i,
  });
  await expect(markUnread).toBeVisible();

  // the saved view now contains it
  await page.goto("/saved");
  await expect(heading).toBeVisible();

  // restore: unmark, and the saved view empties again
  await page.goto("/papers");
  await markUnread.click();
  await expect(markRead).toBeVisible();

  await page.goto("/saved");
  await expect(heading).not.toBeVisible();
  await expect(
    page.getByText("No saved papers yet — mark a paper read and it lands here."),
  ).toBeVisible();
});

test("saved page shows the live empty state when nothing is read", async ({
  page,
}) => {
  await page.goto("/saved");
  await expect(page.getByRole("heading", { name: "Saved" })).toBeVisible();
  await expect(
    page.getByText("No saved papers yet — mark a paper read and it lands here."),
  ).toBeVisible();
});
