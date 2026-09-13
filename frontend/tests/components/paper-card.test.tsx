import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PaperCard } from "@/components/paper-card";
import type { Paper } from "@/lib/pulse-types";

const base: Paper = {
  id: "t-1",
  title: "Test Paper Title",
  url: "https://example.com/p",
  arxivId: "2609.00001",
  source: "arXiv",
  date: "2026-09-12",
  abstract: "A test abstract.",
  concepts: ["MoE", "serving"],
  verdict: "adopt",
  fit: "high",
  memo: "memo text",
  read: false,
};

describe("PaperCard", () => {
  it("renders title, meta rail, concepts, verdict and fit", () => {
    render(<PaperCard paper={base} />);
    expect(screen.getByText("Test Paper Title")).toBeInTheDocument();
    expect(screen.getByText("arXiv")).toBeInTheDocument();
    expect(screen.getByText("2026-09-12")).toBeInTheDocument();
    expect(screen.getByText("2609.00001")).toBeInTheDocument();
    expect(screen.getByText("MoE")).toBeInTheDocument();
    expect(screen.getByText("ADOPT")).toBeInTheDocument();
    expect(screen.getByText("HIGH")).toBeInTheDocument();
  });

  it("shows a read marker only when the paper is read", () => {
    const { rerender } = render(<PaperCard paper={base} />);
    expect(screen.queryByText("✓ read")).not.toBeInTheDocument();
    rerender(<PaperCard paper={{ ...base, read: true }} />);
    expect(screen.getByText("✓ read")).toBeInTheDocument();
  });

  it("renders skip verdict with low fit", () => {
    render(<PaperCard paper={{ ...base, verdict: "skip", fit: "low" }} />);
    expect(screen.getByText("SKIP")).toBeInTheDocument();
    expect(screen.getByText("LOW")).toBeInTheDocument();
  });
});
