import { describe, expect, it } from "vitest";
import { MOCK_PAPERS, MOCK_STACK } from "@/lib/mock-pulse";

const VERDICTS = new Set(["adopt", "prototype", "watch", "skip"]);
const FITS = new Set(["high", "watch", "low"]);

describe("mock pulse data", () => {
  it("provides 8 papers with unique ids, valid enums and https urls", () => {
    expect(MOCK_PAPERS).toHaveLength(8);
    const ids = MOCK_PAPERS.map((p) => p.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const p of MOCK_PAPERS) {
      expect(VERDICTS.has(p.verdict)).toBe(true);
      expect(FITS.has(p.fit)).toBe(true);
      expect(p.url).toMatch(/^https:/);
      expect(p.concepts.length).toBeLessThanOrEqual(3);
      expect(p.abstract.length).toBeGreaterThan(20);
    }
  });

  it("exposes a non-empty mock stack", () => {
    expect(MOCK_STACK.length).toBeGreaterThan(0);
  });
});
