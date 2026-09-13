export type Verdict = "adopt" | "prototype" | "watch" | "skip";
export type StackFit = "high" | "watch" | "low";
export type PaperSource = "HF" | "arXiv";

export interface Paper {
  id: string;
  title: string;
  url: string;
  arxivId: string | null;
  source: PaperSource;
  /** ISO date, e.g. "2026-09-12" */
  date: string;
  abstract: string;
  concepts: string[];
  verdict: Verdict;
  fit: StackFit;
  memo: string;
  read: boolean;
}
