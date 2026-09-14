import { expect, test } from "@playwright/test";

/**
 * P3c e2e — Consultant Terminal + Settings + Pulse→Consultant Apply wiring.
 *
 * This environment has NO GROQ_API_KEY, so GET /consult/status answers
 * ready=false, demo_mode=false (app.py `_api_ready` parity): every test
 * asserts the offline local path. No test may POST /consult/chat, save
 * settings, click Refresh/Refine, or load a README from a real URL — the
 * shared live DB must come out byte-identical (checked separately).
 */

const OFFLINE_MESSAGE =
  "Consultant is offline. Set `GROQ_API_KEY` in `.env`.";

const APPLY_PLACEHOLDER =
  "How do I apply this paper to my system given the papers I already use?";

function trackChatRequests(page: import("@playwright/test").Page) {
  const chatPosts: string[] = [];
  page.on("request", (req) => {
    if (req.method() === "POST" && req.url().includes("/consult/chat")) {
      chatPosts.push(req.url());
    }
  });
  return chatPosts;
}

test("consultant terminal loads offline with the three layer tabs", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const chatPosts = trackChatRequests(page);

  await page.goto("/consultant");
  await expect(page.getByRole("heading", { name: "Consultant Terminal" })).toBeVisible();

  // All three layers are always visible (Streamlit parity: layer buttons,
  // not a hidden select).
  await expect(page.getByRole("tab", { name: "1 · Apply to my system" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "2 · Plain English" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "3 · Systems critic" })).toBeVisible();

  // No key configured → the warn line (providers.OFFLINE_MESSAGE wording).
  await expect(page.getByText("for the Consultant Terminal.")).toBeVisible();
  // demo_mode=false → the BYOK password field is not rendered at all.
  await expect(page.getByPlaceholder("gsk_…")).toHaveCount(0);

  // Default layer is apply: its placeholder + empty state + disabled Clear.
  await expect(
    page.getByRole("textbox", { name: "Consultant message" }),
  ).toBeVisible();
  await expect(page.getByText("No turns yet in this layer.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Clear session" })).toBeDisabled();

  // Loading the status line is a GET only — the chat endpoint is never hit.
  expect(chatPosts).toEqual([]);
  expect(errors).toEqual([]);
});

test("offline send appends the offline error turn and never calls the API", async ({
  page,
}) => {
  const chatPosts = trackChatRequests(page);

  await page.goto("/consultant");
  await expect(page.getByRole("textbox", { name: "Consultant message" })).toBeVisible();

  await page
    .getByRole("textbox", { name: "Consultant message" })
    .fill("Why does the Transformer still win?");
  await page.getByRole("button", { name: "Send" }).click();

  // The offline turn is appended as an assistant message (app.py parity:
  // st.error + the message recorded as the assistant turn) AND surfaced
  // as an alert.
  await expect(page.getByText(OFFLINE_MESSAGE).first()).toBeVisible();
  // Scope by text: Next's __next-route-announcer__ div also carries
  // role="alert" (empty name).
  await expect(
    page.getByRole("alert").filter({ hasText: OFFLINE_MESSAGE }),
  ).toBeVisible();
  // The user prompt is the first turn, the offline note the second.
  await expect(
    page.getByText("Why does the Transformer still win?"),
  ).toBeVisible();
  // A history now exists for THIS layer → Clear unlocks.
  await expect(page.getByRole("button", { name: "Clear session" })).toBeEnabled();

  expect(chatPosts).toEqual([]);
});

test("layer history is isolated per layer", async ({ page }) => {
  await page.goto("/consultant");
  await page
    .getByRole("textbox", { name: "Consultant message" })
    .fill("apply-layer probe");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("apply-layer probe")).toBeVisible();

  // Switching layers shows a fresh, empty terminal (per-layer sessions,
  // exactly like the Streamlit session_state keying).
  await page.getByRole("tab", { name: "2 · Plain English" }).click();
  await expect(page.getByText("No turns yet in this layer.")).toBeVisible();
  await expect(page.getByText("apply-layer probe")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Clear session" })).toBeDisabled();
  await expect(
    page.getByPlaceholder(
      "Ask for a short plain-English explanation of a paper or idea.",
    ),
  ).toBeVisible();
});

test("clear session wipes the current layer only", async ({ page }) => {
  await page.goto("/consultant");
  await page
    .getByRole("textbox", { name: "Consultant message" })
    .fill("to be cleared");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("to be cleared")).toBeVisible();

  await page.getByRole("button", { name: "Clear session" }).click();
  await expect(page.getByText("No turns yet in this layer.")).toBeVisible();
  await expect(page.getByText("to be cleared")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Clear session" })).toBeDisabled();
});

test("settings page loads with the Streamlit sidebar defaults", async ({
  page,
}) => {
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your stack" })).toBeVisible();

  // Live DB has an empty settings row → the idle README caption (exact
  // app.py:216-310 string) and no Load button (no URL to load).
  await expect(
    page.getByText("Paste a public repo, then load the README for Apply delta."),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Load README" })).toHaveCount(0);
});

test("pulse Apply queues the paper prompt into the consultant apply layer", async ({
  page,
}) => {
  const chatPosts = trackChatRequests(page);

  await page.goto("/");
  // The first live snapshot item (paper_id 2608.17906) — stable while the
  // stored snapshot is unchanged; e2e never clicks Refresh, so it stays.
  await expect(
    page.getByRole("heading", { name: "AutoResearch: Insight In, Hallucination Out" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Apply" })
    .first()
    .click();

  // Lands on /consultant (the ?q=… query is consumed and cleared).
  await expect(page).toHaveURL(/\/consultant$/);
  await expect(page.getByRole("tab", { name: "1 · Apply to my system" })).toBeVisible();

  // The queued prompt becomes the user turn: exact P2c preamble + the
  // paper's title block. Settings are empty in the live DB, so no
  // "My system:" / "I already use:" / "My repo:" lines are present.
  await expect(
    page.getByText("Map this paper onto my current application."),
  ).toBeVisible();
  await expect(
    page.getByText("Title: AutoResearch: Insight In, Hallucination Out"),
  ).toBeVisible();
  // Offline → the queued turn resolves to the offline assistant note.
  await expect(page.getByText(OFFLINE_MESSAGE).first()).toBeVisible();

  expect(chatPosts).toEqual([]);
});
