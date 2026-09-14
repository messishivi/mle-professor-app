import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PapersClient } from "@/components/papers-client";
import type { ApiPaper } from "@/lib/api";

const { listPapersMock, patchPaperMock, ingestMock, getSettingsMock, routerMock } =
  vi.hoisted(() => ({
    listPapersMock: vi.fn(),
    patchPaperMock: vi.fn(),
    ingestMock: vi.fn(),
    getSettingsMock: vi.fn(),
    routerMock: { push: vi.fn(), replace: vi.fn() },
  }));

vi.mock("@/lib/api", () => ({
  listPapers: listPapersMock,
  patchPaper: patchPaperMock,
  ingest: ingestMock,
}));

// Keep the REAL buildApplyPrompt (byte parity is what we assert); stub the
// settings fetch.
vi.mock("@/lib/consult", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/consult")>();
  return {
    ...actual,
    getSettings: (...a: unknown[]) => getSettingsMock(...a),
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
}));

const paperA: ApiPaper = {
  id: "1706.03762",
  title: "Attention Is All You Need",
  authors: "Vaswani et al.",
  published_date: "2017-06-12",
  summary_raw: "We propose the Transformer.",
  summary_structured: null,
  read_status: 0,
  added_at: "2026-09-13T23:02:38+00:00",
};
const paperB: ApiPaper = {
  ...paperA,
  id: "1802.02143",
  title: "BERT: Pre-training of Deep Bidirectional Transformers",
  authors: "Devlin et al.",
  read_status: 1,
};

function listResponse(papers: ApiPaper[]) {
  listPapersMock.mockResolvedValue({ count: papers.length, papers });
}

beforeEach(() => {
  vi.clearAllMocks();
  listResponse([paperA, paperB]);
  getSettingsMock.mockResolvedValue({
    stack: [],
    stack_choices: ["RL", "RAG", "Rec"],
    application: "RL post-training loop",
    known_papers: "PPO, DPO",
    repo_url: "https://github.com/you/your-service",
    repo_readme_url: "",
    repo_readme_chars: 0,
  });
  patchPaperMock.mockImplementation(async (id: string, rs: 0 | 1) => ({
    ...paperA,
    id,
    read_status: rs,
  }));
  ingestMock.mockResolvedValue({
    query: "cat:cs.CL",
    fetched: 2,
    upserted: 1,
    skipped: 1,
    papers: [],
    errors: [],
  });
});

describe("PapersClient (all mode)", () => {
  it("loads and renders the library with a count caption", async () => {
    render(<PapersClient />);
    expect(screen.getByText("loading…")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByText("Attention Is All You Need"),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByText("BERT: Pre-training of Deep Bidirectional Transformers"),
    ).toBeInTheDocument();
    expect(screen.getByText("Your library · 2 papers")).toBeInTheDocument();
    expect(listPapersMock).toHaveBeenCalled();
  });

  it("passes the search query to the API", async () => {
    const user = userEvent.setup();
    render(<PapersClient />);
    await screen.findByText("Attention Is All You Need");
    await user.type(screen.getByLabelText(/search papers/i), "bert");
    await waitFor(() =>
      expect(listPapersMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ q: "bert" }),
      ),
    );
  });

  it("sends read=0 for the Unread filter and read=1 for Read", async () => {
    const user = userEvent.setup();
    render(<PapersClient />);
    await screen.findByText("Attention Is All You Need");

    await user.click(screen.getByRole("tab", { name: "Unread" }));
    await waitFor(() =>
      expect(listPapersMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ read: 0 }),
      ),
    );
    await user.click(screen.getByRole("tab", { name: "Read" }));
    await waitFor(() =>
      expect(listPapersMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ read: 1 }),
      ),
    );
    await user.click(screen.getByRole("tab", { name: "All" }));
    await waitFor(() =>
      expect(listPapersMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ read: undefined }),
      ),
    );
  });

  it("marks a paper read via PATCH and updates the row", async () => {
    const user = userEvent.setup();
    render(<PapersClient />);
    await screen.findByText("Attention Is All You Need");
    const btn = screen.getByRole("button", { name: /mark attention is all you need as read/i });
    await user.click(btn);
    expect(patchPaperMock).toHaveBeenCalledWith(paperA.id, 1);
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /mark attention is all you need as unread/i }),
      ).toBeInTheDocument(),
    );
  });

  it("rolls back an optimistic toggle when the PATCH fails", async () => {
    const user = userEvent.setup();
    patchPaperMock.mockRejectedValueOnce(
      new Error("No paper with id '1706.03762'"),
    );
    render(<PapersClient />);
    await screen.findByText("Attention Is All You Need");
    await user.click(
      screen.getByRole("button", { name: /mark attention is all you need as read/i }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /mark attention is all you need as read/i }),
      ).toBeInTheDocument(),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No paper with id '1706.03762'",
    );
  });

  it("shows the ingest result and refetches the list", async () => {
    const user = userEvent.setup();
    render(<PapersClient />);
    await screen.findByText("Attention Is All You Need");
    const callsBefore = listPapersMock.mock.calls.length;
    await user.click(screen.getByRole("button", { name: /refresh papers/i }));
    expect(ingestMock).toHaveBeenCalledWith({
      categories: ["cs.CL", "cs.LG"],
      max_results: 20,
    });
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Fetched 2 · upserted 1 · skipped 1",
    );
    expect(listPapersMock.mock.calls.length).toBeGreaterThan(callsBefore);
  });

  it("validates the ingest form: at least one category", async () => {
    const user = userEvent.setup();
    render(<PapersClient />);
    await screen.findByText("Attention Is All You Need");
    // uncheck both default categories
    await user.click(screen.getByRole("button", { name: "cs.CL" }));
    await user.click(screen.getByRole("button", { name: "cs.LG" }));
    await user.click(screen.getByRole("button", { name: /refresh papers/i }));
    expect(ingestMock).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Pick at least one category.",
    );
  });

  it("shows an error banner when the API is unreachable", async () => {
    listPapersMock.mockRejectedValue(
      new Error("Cannot reach the API at http://127.0.0.1:8000"),
    );
    render(<PapersClient />);
    expect(
      await screen.findByRole("alert"),
    ).toHaveTextContent(/cannot reach the api/i);
  });

  it("Apply queues the paper into the Consultant's Apply layer (byte-parity prompt)", async () => {
    const user = userEvent.setup();
    render(<PapersClient />);
    await screen.findByText("Attention Is All You Need");
    await user.click(
      screen.getByRole("button", {
        name: "Apply Attention Is All You Need to my system",
      }),
    );
    await waitFor(() =>
      expect(routerMock.push).toHaveBeenCalledTimes(1),
    );
    const url = routerMock.push.mock.calls[0][0] as string;
    expect(url.startsWith("/consultant?layer=apply&q=")).toBe(true);
    const prompt = decodeURIComponent(
      url.slice("/consultant?layer=apply&q=".length),
    );
    // Exact P2c/Streamlit parity template for a library paper.
    expect(prompt).toBe(
      "Map this paper onto my current application. What is relevant, what to ignore, " +
        "and how I implement it. Use user / item (or target) / data / training / serving / eval; " +
        "rename those to my modules. Do not assume a rec stack.\n" +
        "\nMy system: RL post-training loop\n" +
        "I already use: PPO, DPO\n" +
        "My repo: https://github.com/you/your-service\n" +
        "Delta against the repo README in retrieved sources — what is already shipped.\n" +
        "\n" +
        "Title: Attention Is All You Need\n" +
        "Authors: Vaswani et al.\n" +
        "arXiv: 1706.03762\n" +
        "Date: 2017-06-12\n\n" +
        "Abstract:\nWe propose the Transformer.",
    );
  });
});

describe("PapersClient (saved mode)", () => {
  it("always fetches read=1 and hides search, filters and ingest", async () => {
    render(<PapersClient mode="saved" />);
    expect(screen.getByRole("heading", { name: "Saved" })).toBeInTheDocument();
    await waitFor(() =>
      expect(listPapersMock).toHaveBeenCalledWith(
        expect.objectContaining({ read: 1 }),
      ),
    );
    expect(screen.queryByLabelText(/search papers/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /refresh papers/i })).not.toBeInTheDocument();
  });

  it("removes a row from the saved view when it is unmarked", async () => {
    const user = userEvent.setup();
    listResponse([paperB]);
    render(<PapersClient mode="saved" />);
    await screen.findByText("BERT: Pre-training of Deep Bidirectional Transformers");
    await user.click(
      screen.getByRole("button", { name: /mark bert: pre-training of deep bidirectional transformers as unread/i }),
    );
    expect(patchPaperMock).toHaveBeenCalledWith(paperB.id, 0);
    await waitFor(() =>
      expect(
        screen.queryByText("BERT: Pre-training of Deep Bidirectional Transformers"),
      ).not.toBeInTheDocument(),
    );
    expect(
      screen.getByText(
        "No saved papers yet — mark a paper read and it lands here.",
      ),
    ).toBeInTheDocument();
  });
});
