import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { PulseItem, PulsePayload } from "@/lib/pulse";

const { pulseMock, consultMock } = vi.hoisted(() => ({
  pulseMock: {
    getPulse: vi.fn(),
    refreshPulse: vi.fn(),
    refineMemo: vi.fn(),
  },
  consultMock: { getConsultStatus: vi.fn() },
}));

vi.mock("@/lib/pulse", () => ({
  getPulse: (...a: unknown[]) => pulseMock.getPulse(...a),
  refreshPulse: (...a: unknown[]) => pulseMock.refreshPulse(...a),
  refineMemo: (...a: unknown[]) => pulseMock.refineMemo(...a),
  memoItemKey: (i: PulseItem) => (i.paper_id || i.topic).slice(0, 120),
  formatFetchedAt: (iso: string | null) =>
    iso ? `${iso.slice(0, 16).replace("T", " ")} UTC` : "never",
  rankItems: (items: PulseItem[], stack: string[], view: "stack" | "all") => {
    if (view !== "stack" || stack.length === 0) return items;
    return items
      .map((item, index) => ({ item, index }))
      .filter(({ item }) => item.fit.label !== "Skip")
      .sort((a, b) => b.item.fit.score - a.item.fit.score || a.index - b.index)
      .map(({ item }) => item);
  },
  pulseErrorMessage: (e: unknown) =>
    e instanceof Error ? e.message : String(e),
}));
vi.mock("@/lib/api", () => ({
  getConsultStatus: (...a: unknown[]) => consultMock.getConsultStatus(...a),
  ApiError: class ApiError extends Error {
    status: number;
    detail: string;
    constructor(status: number, detail: string) {
      super(detail);
      this.status = status;
      this.detail = detail;
    }
  },
}));

import { PulseClient } from "@/components/pulse-client";

const item = (
  topic: string,
  label: string,
  score: number,
  verdict = "Watch",
): PulseItem => ({
  topic,
  why: `${topic} why`,
  paper_id: topic === "Alpha" ? "2608.00001" : null,
  paper_title: topic === "Alpha" ? "Alpha paper" : "",
  paper_url: topic === "Alpha" ? "https://arxiv.org/abs/2608.00001" : "",
  concept: "",
  concept_blurb: "",
  in_library: false,
  source: "arxiv",
  abstract: "",
  published_date: "2026-09-01",
  fit: { label, score, so_what: `${topic} so-what` },
  memo: {
    verdict,
    constraint_note: `${topic} constraint`,
    so_what: `${topic} memo`,
    paper_url: "",
    origin: "heuristic",
  },
});

const payload = (items: PulseItem[], stack: string[] = ["pytorch"]): PulsePayload => ({
  fetched_at: "2026-09-13T23:53:30+00:00",
  items,
  errors: [],
  stack,
});

const ITEMS = [
  item("Alpha", "High fit", 90, "Adopt"),
  item("Beta", "Skip", 10, "Skip"),
  item("Gamma", "Watch", 45),
];

beforeEach(() => {
  vi.clearAllMocks();
  pulseMock.getPulse.mockResolvedValue(payload(ITEMS));
  pulseMock.refreshPulse.mockResolvedValue(
    payload([item("Delta", "Watch", 50, "Prototype")]),
  );
  pulseMock.refineMemo.mockResolvedValue({
    item_key: "2608.00001",
    stack_key: "pytorch",
    memo: {
      verdict: "Adopt",
      constraint_note: "refined constraint",
      so_what: "refined so-what",
      paper_url: "https://arxiv.org/abs/2608.00001",
      origin: "groq",
    },
  });
  consultMock.getConsultStatus.mockResolvedValue({
    ready: true,
    provider: "groq",
    model: "openai/gpt-oss-120b",
    demo_mode: false,
  });
});

describe("PulseClient", () => {
  it("loads the snapshot: caption, stack chips, items", async () => {
    render(<PulseClient />);
    expect(screen.getByRole("heading", { name: "Pulse" })).toBeInTheDocument();
    await screen.findByText("updated 2026-09-13 23:53 UTC · 3 items");
    expect(screen.getByText("pytorch")).toBeInTheDocument();
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Gamma")).toBeInTheDocument();
    // Beta is "Skip" with a non-empty stack → dropped from the default
    // "For my stack" view (app.py parity).
    expect(screen.queryByText("Beta")).not.toBeInTheDocument();
    expect(pulseMock.getPulse).toHaveBeenCalledTimes(1);
    expect(consultMock.getConsultStatus).toHaveBeenCalledTimes(1);
  });

  it("stack view (default) re-ranks by score and drops Skip", async () => {
    const { container } = render(<PulseClient />);
    await screen.findByText("Gamma");
    const article = container.querySelector("article")!;
    const order = [...article.parentElement!.querySelectorAll("article")].map(
      (a) => (a.querySelector("h3")!.textContent as string),
    );
    expect(order).toEqual(["Alpha", "Gamma"]);
    expect(screen.queryByText("Beta")).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "For my stack" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("'Everything' shows the snapshot in original order", async () => {
    const user = userEvent.setup();
    const { container } = render(<PulseClient />);
    await screen.findByText("Gamma");
    await user.click(screen.getByRole("tab", { name: "Everything" }));
    const order = [...container.querySelectorAll("article")].map(
      (a) => a.querySelector("h3")!.textContent as string,
    );
    expect(order).toEqual(["Alpha", "Beta", "Gamma"]);
  });

  it("Refresh posts, swaps the payload, and surfaces source errors", async () => {
    const user = userEvent.setup();
    pulseMock.refreshPulse.mockResolvedValueOnce({
      fetched_at: "2026-09-14T00:00:00+00:00",
      items: [item("Delta", "Watch", 50)],
      errors: ["arXiv: 429 Too Many Requests"],
      stack: ["pytorch"],
    });
    render(<PulseClient />);
    await screen.findByText("Alpha");
    await user.click(screen.getByRole("button", { name: "Refresh" }));
    expect(pulseMock.refreshPulse).toHaveBeenCalledTimes(1);
    await screen.findByText("Delta");
    expect(screen.getByText("updated 2026-09-14 00:00 UTC · 1 items")).toBeInTheDocument();
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("arXiv: 429 Too Many Requests");
  });

  it("surfaces refresh failures without dropping the old payload", async () => {
    const user = userEvent.setup();
    pulseMock.refreshPulse.mockRejectedValueOnce(
      new Error("Cannot reach the API at http://127.0.0.1:8000"),
    );
    render(<PulseClient />);
    await screen.findByText("Alpha");
    await user.click(screen.getByRole("button", { name: "Refresh" }));
    expect(
      await screen.findByText(
        "Cannot reach the API at http://127.0.0.1:8000",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Alpha")).toBeInTheDocument();
  });

  it("Refine memo posts the item + stack and swaps the memo in place", async () => {
    const user = userEvent.setup();
    render(<PulseClient />);
    const alpha = (await screen.findByText("Alpha")).closest("article")!;
    expect(alpha).toHaveTextContent("Constraint: Alpha constraint");
    await user.click(within(alpha as HTMLElement).getByRole("button", { name: "Refine memo" }));
    expect(pulseMock.refineMemo).toHaveBeenCalledWith(
      expect.objectContaining({ topic: "Alpha" }),
      ["pytorch"],
    );
    await waitFor(() =>
      expect(alpha).toHaveTextContent("Constraint: refined constraint"),
    );
    expect(alpha).toHaveTextContent("refined so-what");
    expect(alpha).toHaveTextContent("groq");
    // other visible items keep their memos (Beta is dropped from the
    // stack view by rankItems, so assert on Gamma)
    const gamma = screen.getByText("Gamma").closest("article")!;
    expect(gamma).toHaveTextContent("Constraint: Gamma constraint");
  });

  it("shows a refine error and keeps the old memo on failure", async () => {
    const user = userEvent.setup();
    pulseMock.refineMemo.mockRejectedValueOnce(
      Object.assign(new Error("Consultant is offline."), {
        name: "ApiError",
        status: 422,
      }),
    );
    render(<PulseClient />);
    const alpha = (await screen.findByText("Alpha")).closest("article")!;
    await user.click(within(alpha as HTMLElement).getByRole("button", { name: "Refine memo" }));
    await screen.findByText("Consultant is offline.");
    expect(alpha).toHaveTextContent("Constraint: Alpha constraint");
  });

  it("disables Refine memo when the consultant is offline", async () => {
    consultMock.getConsultStatus.mockResolvedValue({
      ready: false,
      provider: "groq",
      model: "openai/gpt-oss-120b",
      demo_mode: false,
    });
    render(<PulseClient />);
    const alpha = (await screen.findByText("Alpha")).closest("article")!;
    const btn = within(alpha as HTMLElement).getByRole("button", { name: "Refine memo" });
    expect(btn).toBeDisabled();
  });

  it("still renders the page when /consult/status fails", async () => {
    consultMock.getConsultStatus.mockRejectedValueOnce(new Error("down"));
    render(<PulseClient />);
    await screen.findByText("Alpha");
    const alpha = screen.getByText("Alpha").closest("article")!;
    expect(
      within(alpha as HTMLElement).getByRole("button", { name: "Refine memo" }),
    ).toBeDisabled();
  });

  it("shows an empty state when the snapshot has no items", async () => {
    pulseMock.getPulse.mockResolvedValue(payload([], []));
    render(<PulseClient />);
    expect(
      await screen.findByText(/No pulse yet/),
    ).toBeInTheDocument();
    expect(screen.getByText("not set — items rank as “Set stack”")).toBeInTheDocument();
  });

  it("shows the stack-view-empty message when everything is skipped", async () => {
    pulseMock.getPulse.mockResolvedValue(
      payload([item("Beta", "Skip", 10, "Skip")], ["pytorch"]),
    );
    render(<PulseClient />);
    expect(
      await screen.findByText(/Nothing on your stack in this pulse/),
    ).toBeInTheDocument();
  });

  it("shows a load error with Retry when the API is unreachable", async () => {
    pulseMock.getPulse.mockRejectedValueOnce(
      new Error("Cannot reach the API at http://127.0.0.1:8000"),
    );
    const user = userEvent.setup();
    render(<PulseClient />);
    expect(
      await screen.findByText(
        "Cannot reach the API at http://127.0.0.1:8000",
      ),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(pulseMock.getPulse).toHaveBeenCalledTimes(2);
  });
});
