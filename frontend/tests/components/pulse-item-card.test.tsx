import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { PulseItem } from "@/lib/pulse";
import { PulseItemCard } from "@/components/pulse-item-card";

function makeItem(partial: Partial<PulseItem> = {}): PulseItem {
  return {
    topic: "AutoResearch: Insight In, Hallucination Out",
    why: "Why this matters for your system.",
    paper_id: "2608.17906",
    paper_title: "AutoResearch: Insight In, Hallucination Out",
    paper_url: "https://arxiv.org/abs/2608.17906",
    concept: "Evaluation / benchmarks",
    concept_blurb: "Measuring what models can actually do.",
    in_library: false,
    source: "hf_daily",
    abstract: "",
    published_date: "2026-08-23",
    fit: {
      label: "High fit",
      score: 85,
      so_what: "Overlaps pytorch, hugging-face.",
    },
    memo: {
      verdict: "Adopt",
      constraint_note: "Needs a held-out eval set.",
      so_what: "Adopt once the eval harness exists.",
      paper_url: "https://arxiv.org/abs/2608.17906",
      origin: "groq",
    },
    ...partial,
  };
}

const base = { apiReady: true, refining: false, onRefine: vi.fn() };

describe("PulseItemCard (render_ml_pulse parity)", () => {
  it("renders topic, date, arXiv link, tags, fit so-what and why", () => {
    const { container } = render(<PulseItemCard item={makeItem()} {...base} />);
    expect(screen.getByRole("heading", { name: /AutoResearch/ })).toBeInTheDocument();
    const article = container.querySelector("article")!;
    expect(article).toHaveTextContent("2026-08-23");
    expect(article).toHaveTextContent("arXiv:2608.17906");
    const chips = [...article.querySelectorAll("span")].map((s) => s.textContent);
    expect(chips).toEqual(expect.arrayContaining([
      "High fit", "2026-08-23", "trending", "paper", "concept",
    ]));
    expect(article).toHaveTextContent("Overlaps pytorch, hugging-face.");
    expect(article).toHaveTextContent("Why this matters for your system.");
  });

  it("renders the memo block: Decision, verdict badge, groq origin, so-what, constraint, link", () => {
    const { container } = render(<PulseItemCard item={makeItem()} {...base} />);
    const article = container.querySelector("article")!;
    expect(article).toHaveTextContent("Decision");
    expect(article).toHaveTextContent("ADOPT");
    // origin is italicized and shown only for groq
    expect(screen.getByText("groq")).toBeInTheDocument();
    expect(article).toHaveTextContent("Adopt once the eval harness exists.");
    expect(article).toHaveTextContent("Constraint: Needs a held-out eval set.");
    const links = [...article.querySelectorAll("a")];
    expect(
      links.some((a) => a.getAttribute("href") === "https://arxiv.org/abs/2608.17906"),
    ).toBe(true);
  });

  it("does not show the origin for heuristic memos", () => {
    render(
      <PulseItemCard
        item={makeItem({ memo: { ...makeItem().memo, origin: "heuristic", verdict: "watch" } })}
        {...base}
      />
    );
    expect(screen.queryByText("groq")).not.toBeInTheDocument();
    // Streamlit uppercases whatever verdict the backend sends
    expect(screen.getByText("WATCH")).toBeInTheDocument();
  });

  it("shows 'No single paper pinned to this topic.' when there is no paper", () => {
    render(
      <PulseItemCard
        item={makeItem({
          paper_id: null,
          paper_title: "",
          paper_url: "",
          memo: { ...makeItem().memo, paper_url: "" },
        })}
        {...base}
      />
    );
    expect(
      screen.getByText("No single paper pinned to this topic."),
    ).toBeInTheDocument();
  });

  it("renders the concept line with blurb and the 'in library' tag", () => {
    const { container } = render(
      <PulseItemCard item={makeItem({ in_library: true })} {...base} />,
    );
    const article = container.querySelector("article")!;
    expect(article).toHaveTextContent("Concept ·");
    expect(article).toHaveTextContent("Evaluation / benchmarks");
    expect(article).toHaveTextContent("Measuring what models can actually do.");
    expect(article).toHaveTextContent("in library");
  });

  it("labels the arxiv source as 'arxiv new'", () => {
    const { container } = render(
      <PulseItemCard
        item={makeItem({ source: "arxiv", in_library: false })}
        {...base}
      />,
    );
    const article = container.querySelector("article")!;
    expect(article).toHaveTextContent("arxiv new");
  });

  it("disables Refine memo when the consultant is offline, with the parity hint", async () => {
    const onRefine = vi.fn();
    render(<PulseItemCard item={makeItem()} apiReady={false} refining={false} onRefine={onRefine} />);
    const btn = screen.getByRole("button", { name: "Refine memo" });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute(
      "title",
      "Consultant is offline — set GROQ_API_KEY in the API .env",
    );
    await userEvent.click(btn);
    expect(onRefine).not.toHaveBeenCalled();
  });

  it("calls onRefine with the item when online, and shows busy text while refining", async () => {
    const onRefine = vi.fn();
    const user = userEvent.setup();
    const { rerender } = render(
      <PulseItemCard item={makeItem()} apiReady={true} refining={false} onRefine={onRefine} />,
    );
    await user.click(screen.getByRole("button", { name: "Refine memo" }));
    expect(onRefine).toHaveBeenCalledWith(expect.objectContaining({ topic: "AutoResearch: Insight In, Hallucination Out" }));
    rerender(<PulseItemCard item={makeItem()} apiReady={true} refining={true} onRefine={onRefine} />);
    expect(screen.getByRole("button", { name: "Refining…" })).toBeDisabled();
  });

  it("normalizes unknown verdicts to raw uppercase", () => {
    render(
      <PulseItemCard
        item={makeItem({ memo: { ...makeItem().memo, verdict: "Pilot it" } })}
        {...base}
      />
    );
    expect(screen.getByText("PILOT IT")).toBeInTheDocument();
  });
});
