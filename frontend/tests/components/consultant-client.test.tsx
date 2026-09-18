import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { SseEvent, ConsultTurn } from "@/lib/consult";

const {
  streamMock,
  statusMock,
  routerMock,
  paramsMock,
} = vi.hoisted(() => ({
  streamMock: vi.fn(),
  statusMock: vi.fn(),
  routerMock: { push: vi.fn(), replace: vi.fn() },
  paramsMock: { current: new URLSearchParams() },
}));

// Keep the REAL constants + in-memory store (byte parity is what we assert);
// stub only the network.
vi.mock("@/lib/consult", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/consult")>();
  return { ...actual, streamConsult: (...a: unknown[]) => streamMock(...a) };
});
vi.mock("@/lib/api", () => ({
  getConsultStatus: (...a: unknown[]) => statusMock(...a),
  ApiError: class ApiError extends Error {
    status: number;
    detail: string;
    constructor(status: number, detail: string) {
      super(detail);
      this.name = "ApiError";
      this.status = status;
      this.detail = detail;
    }
  },
}));
vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  useSearchParams: () => paramsMock.current,
}));

import { ConsultantClient } from "@/components/consultant-client";
import { OFFLINE_MESSAGE, setHistory, setDemoKey } from "@/lib/consult";

const offline = { ready: false, provider: "groq", model: "openai/gpt-oss-120b", demo_mode: false };
const ready = { ready: true, provider: "groq", model: "openai/gpt-oss-120b", demo_mode: false };

function emitThenDone(events: SseEvent[]) {
  streamMock.mockImplementation(
    (_opts: unknown, onEvent: (ev: SseEvent) => void) => {
      for (const ev of events) onEvent(ev);
      return Promise.resolve();
    },
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  setHistory("apply", []);
  setHistory("explain", []);
  setHistory("systems", []);
  setDemoKey("");
  paramsMock.current = new URLSearchParams();
  statusMock.mockResolvedValue(offline);
});

describe("ConsultantClient", () => {
  it("renders the offline state with the exact Streamlit strings", async () => {
    render(<ConsultantClient />);
    expect(
      await screen.findByRole("heading", { name: "Consultant Terminal" }),
    ).toBeInTheDocument();
    // Status line (GROQ_API_KEY is wrapped in <code>, so match by regex).
    expect(screen.getByText(/GROQ_API_KEY/)).toBeInTheDocument();
    expect(
      screen.getByText(/for the Consultant Terminal\./),
    ).toBeInTheDocument();
    // Three layer tabs with exact labels; apply selected by default.
    const applyTab = screen.getByRole("tab", { name: "1 · Apply to my system" });
    const explainTab = screen.getByRole("tab", { name: "2 · Plain English" });
    const systemsTab = screen.getByRole("tab", { name: "3 · Systems critic" });
    expect(applyTab).toHaveAttribute("aria-selected", "true");
    expect(explainTab).toHaveAttribute("aria-selected", "false");
    expect(systemsTab).toHaveAttribute("aria-selected", "false");
    expect(
      screen.getByText(
        "Default · map the paper onto YOUR application (user / item / data / train / serve / eval): Use / Adapt / Ignore, delta vs papers + repo README, then an implementation path.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(
        "How do I apply this paper to my system given the papers I already use?",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Clear session" })).toBeDisabled();
    expect(screen.getByText("No turns yet in this layer.")).toBeInTheDocument();
  });

  it("offline send: no request goes out; the exact offline message is recorded", async () => {
    const user = userEvent.setup();
    render(<ConsultantClient />);
    await screen.findByText(/GROQ_API_KEY/);
    await user.type(
      screen.getByRole("textbox", { name: "Consultant message" }),
      "explain this paper",
    );
    await user.click(screen.getByRole("button", { name: "Send" }));
    // No network at all (app.py:394-398 parity).
    expect(streamMock).not.toHaveBeenCalled();
    // The message is kept in the layer history as user + assistant turns.
    await screen.findByText("explain this paper");
    const offlineMatches = await screen.findAllByText(OFFLINE_MESSAGE);
    expect(offlineMatches.length).toBeGreaterThanOrEqual(1);
    // The alert variant is the turnError box.
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Clear session" })).toBeEnabled();
  });

  it("keeps histories isolated per layer (st.session_state parity)", async () => {
    const user = userEvent.setup();
    render(<ConsultantClient />);
    await screen.findByText(/GROQ_API_KEY/);
    await user.type(
      screen.getByRole("textbox", { name: "Consultant message" }),
      "apply-layer question",
    );
    await user.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByText("apply-layer question");

    await user.click(screen.getByRole("tab", { name: "2 · Plain English" }));
    expect(screen.getByText("No turns yet in this layer.")).toBeInTheDocument();
    expect(screen.queryByText("apply-layer question")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "1 · Apply to my system" }));
    expect(screen.getByText("apply-layer question")).toBeInTheDocument();
  });

  it("streams sources/deltas and finishes with the done content", async () => {
    emitThenDone([
      {
        type: "sources",
        sources: [{ kind: "arxiv", title: "T1", url: "https://arxiv.org/abs/1" }],
      },
      { type: "delta", text: "Hel" },
      { type: "delta", text: "lo" },
      { type: "done", content: "Hello grounded.", model: "m", provider: "groq", layer: "apply" },
    ]);
    statusMock.mockResolvedValue(ready);
    const user = userEvent.setup();
    render(<ConsultantClient />);
    await screen.findByText("Consultant ready · groq · openai/gpt-oss-120b");
    await user.type(
      screen.getByRole("textbox", { name: "Consultant message" }),
      "how do I use this?",
    );
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Hello grounded.")).toBeInTheDocument();
    expect(streamMock).toHaveBeenCalledTimes(1);
    const [opts] = streamMock.mock.calls[0] as [{
      message: string;
      history: ConsultTurn[];
      layer: string;
      apiKey?: string;
    }];
    expect(opts.message).toBe("how do I use this?");
    expect(opts.history).toEqual([]);
    expect(opts.layer).toBe("apply");
    expect(opts.apiKey).toBeUndefined();
    // Sources expander on the last assistant turn (Streamlit parity string).
    const summary = screen.getByText(
      "Checked sources (click these — do not trust an unsourced paper name)",
    );
    summary.click();
    expect(await screen.findByText("T1")).toBeInTheDocument();
    expect(
      within(summary.parentElement as HTMLElement).getByText("arxiv"),
    ).toBeInTheDocument();
    // provider · model meta under the turns.
    expect(screen.getByText("groq · m")).toBeInTheDocument();
  });

  it("sends only PAST turns as history (current prompt excluded)", async () => {
    setHistory("explain", [
      { role: "user", content: "earlier" },
      { role: "assistant", content: "earlier reply" },
    ]);
    emitThenDone([
      { type: "done", content: "ok", model: "m", provider: "p", layer: "explain" },
    ]);
    statusMock.mockResolvedValue(ready);
    const user = userEvent.setup();
    render(<ConsultantClient />);
    // Switch to the explain tab (seeded history lives there).
    await user.click(screen.getByRole("tab", { name: "2 · Plain English" }));
    // Restored history is visible in that layer.
    expect(await screen.findByText("earlier")).toBeInTheDocument();
    await user.type(
      screen.getByRole("textbox", { name: "Consultant message" }),
      "current question",
    );
    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(streamMock).toHaveBeenCalledTimes(1));
    const [opts] = streamMock.mock.calls[0] as [{ history: ConsultTurn[] }];
    expect(opts.history).toEqual([
      { role: "user", content: "earlier" },
      { role: "assistant", content: "earlier reply" },
    ]);
  });

  it("records an in-stream error as the assistant turn", async () => {
    emitThenDone([{ type: "error", message: "rate limited" }]);
    statusMock.mockResolvedValue(ready);
    const user = userEvent.setup();
    render(<ConsultantClient />);
    await screen.findByText(/Consultant ready/);
    await user.type(
      screen.getByRole("textbox", { name: "Consultant message" }),
      "hi",
    );
    await user.click(screen.getByRole("button", { name: "Send" }));
    // Turn + alert both carry the error text (Streamlit parity: st.error +
    // the message kept in history).
    expect((await screen.findAllByText("rate limited")).length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });

  it("treats an empty done as an error turn", async () => {
    emitThenDone([
      { type: "done", content: "", model: "m", provider: "p", layer: "apply" },
    ]);
    statusMock.mockResolvedValue(ready);
    const user = userEvent.setup();
    render(<ConsultantClient />);
    await screen.findByText(/Consultant ready/);
    await user.type(screen.getByRole("textbox", { name: "Consultant message" }), "hi");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(
      (await screen.findAllByText("The model returned an empty response."))
        .length,
    ).toBeGreaterThanOrEqual(2);
  });

  it("demo mode: session-only key unlocks the consultant", async () => {
    statusMock.mockResolvedValue({ ...offline, demo_mode: true });
    const user = userEvent.setup();
    render(<ConsultantClient />);
    expect(
      await screen.findByText(
        "Paste a Groq key above to unlock the Consultant (this session only).",
      ),
    ).toBeInTheDocument();
    // The banner paragraph carries a second sentence, so match a substring.
    expect(screen.getByText(/Demo mode — explore freely/)).toBeInTheDocument();
    expect(
      screen.getByText("Kept in memory for this browser session. Never written to disk."),
    ).toBeInTheDocument();
    // input[type=password] is hidden from role=textbox queries; use the
    // Streamlit-parity placeholder instead.
    const keyInput = screen.getByPlaceholderText("gsk_…");
    await user.type(keyInput, "sk-test");
    await user.type(
      screen.getByRole("textbox", { name: "Consultant message" }),
      "hello consultant",
    );
    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(streamMock).toHaveBeenCalledTimes(1));
    const [opts] = streamMock.mock.calls[0] as [{ apiKey?: string }];
    expect(opts.apiKey).toBe("sk-test");
  });

  it("auto-runs a queued Apply turn (?q=) exactly once, offline-safe", async () => {
    paramsMock.current = new URLSearchParams(
      "q=queued+prompt+text&layer=apply",
    );
    render(<ConsultantClient />);
    // The queued prompt appears as a user turn without any typing.
    expect(await screen.findByText("queued prompt text")).toBeInTheDocument();
    // The exact offline message answers it (turn + alert), nothing fetched.
    expect((await screen.findAllByText(OFFLINE_MESSAGE)).length).toBeGreaterThanOrEqual(2);
    expect(streamMock).not.toHaveBeenCalled();
    // The URL is cleaned up.
    expect(routerMock.replace).toHaveBeenCalledWith("/consultant");
  });

  it("queued ?q= still runs when the status load fails (offline path, not stuck)", async () => {
    statusMock.mockRejectedValue(new Error("boom-status"));
    paramsMock.current = new URLSearchParams(
      "q=queued+prompt+text&layer=apply",
    );
    render(<ConsultantClient />);
    // The status failure surfaces in the banner...
    expect(await screen.findByText("boom-status")).toBeInTheDocument();
    // ...and the queued prompt is NOT silently stuck: it ran the not-ready
    // path, landing in the layer history with the exact offline reply.
    expect(await screen.findByText("queued prompt text")).toBeInTheDocument();
    expect(
      (await screen.findAllByText(OFFLINE_MESSAGE)).length,
    ).toBeGreaterThanOrEqual(2);
    expect(streamMock).not.toHaveBeenCalled();
    expect(routerMock.replace).toHaveBeenCalledWith("/consultant");
  });

  it("queued ?q= with an unknown layer falls back to apply", async () => {
    paramsMock.current = new URLSearchParams("q=queued+prompt+text&layer=bogus");
    render(<ConsultantClient />);
    expect(await screen.findByText("queued prompt text")).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "1 · Apply to my system" }),
    ).toHaveAttribute("aria-selected", "true");
  });

  it("Clear session empties only the current layer", async () => {
    const user = userEvent.setup();
    render(<ConsultantClient />);
    await screen.findByText(/GROQ_API_KEY/);
    await user.type(
      screen.getByRole("textbox", { name: "Consultant message" }),
      "to be cleared",
    );
    await user.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByText("to be cleared");
    await user.click(screen.getByRole("button", { name: "Clear session" }));
    expect(screen.getByText("No turns yet in this layer.")).toBeInTheDocument();
    expect(screen.queryByText("to be cleared")).not.toBeInTheDocument();
  });

  it("surfaces a status-load failure with Retry", async () => {
    statusMock.mockRejectedValue(new Error("boom-status"));
    const user = userEvent.setup();
    render(<ConsultantClient />);
    expect(await screen.findByText("boom-status")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(statusMock).toHaveBeenCalledTimes(2);
  });
});
