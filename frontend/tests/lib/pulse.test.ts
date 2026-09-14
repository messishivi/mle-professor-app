import { afterEach, describe, expect, it, vi } from "vitest";
import type { PulseItem } from "@/lib/pulse";
import {
  formatFetchedAt,
  getPulse,
  memoItemKey,
  rankItems,
  refreshPulse,
  refineMemo,
} from "@/lib/pulse";
import { API_BASE, ApiError } from "@/lib/api";

function item(
  partial: Partial<PulseItem> & Pick<PulseItem, "topic">,
): PulseItem {
  return {
    why: "",
    paper_id: null,
    paper_title: "",
    paper_url: "",
    concept: "",
    concept_blurb: "",
    in_library: false,
    source: "arxiv",
    abstract: "",
    published_date: "",
    fit: { label: "Set stack", score: 40, so_what: "" },
    memo: {
      verdict: "Watch",
      constraint_note: "",
      so_what: "",
      paper_url: "",
      origin: "heuristic",
    },
    ...partial,
  };
}

const fit = (label: string, score: number) => ({
  label,
  score,
  so_what: "",
});

describe("rankItems (app.py:518-525 parity)", () => {
  const items = [
    item({ topic: "A", fit: fit("High fit", 90) }),
    item({ topic: "B", fit: fit("Skip", 10) }),
    item({ topic: "C", fit: fit("Watch", 45) }),
    item({ topic: "D", fit: fit("High fit", 90) }),
  ];

  it("returns the list unchanged for the 'all' view", () => {
    expect(rankItems(items, ["pytorch"], "all")).toEqual(items);
  });

  it("passes through in snapshot order when the stack is empty", () => {
    expect(rankItems(items, [], "stack")).toEqual(items);
  });

  it("sorts by (-score, original index) and drops Skip when stacked", () => {
    expect(
      rankItems(items, ["pytorch"], "stack").map((i) => i.topic),
    ).toEqual(["A", "D", "C"]);
  });

  it("is stable for equal scores (original index order)", () => {
    const same = [
      item({ topic: "X", fit: fit("Watch", 45) }),
      item({ topic: "Y", fit: fit("Watch", 45) }),
    ];
    expect(
      rankItems(same, ["pytorch"], "stack").map((i) => i.topic),
    ).toEqual(["X", "Y"]);
  });
});

describe("formatFetchedAt", () => {
  it("formats an ISO snapshot timestamp", () => {
    expect(formatFetchedAt("2026-09-13T23:53:30+00:00")).toBe(
      "2026-09-13 23:53 UTC",
    );
  });

  it("returns 'never' for a missing snapshot", () => {
    expect(formatFetchedAt(null)).toBe("never");
  });

  it("passes through unparseable values", () => {
    expect(formatFetchedAt("yesterday")).toBe("yesterday");
  });
});

describe("memoItemKey (trends.py:181 parity)", () => {
  it("prefers the paper id over the topic", () => {
    expect(
      memoItemKey(item({ topic: "Some topic", paper_id: "2608.17906" })),
    ).toBe("2608.17906");
  });

  it("falls back to the topic", () => {
    expect(memoItemKey(item({ topic: "Some topic" }))).toBe("Some topic");
  });

  it("truncates to 120 characters", () => {
    const long = "t".repeat(200);
    expect(memoItemKey(item({ topic: long }))).toHaveLength(120);
  });
});

describe("pulse client endpoints", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("GET /pulse", async () => {
    const payload = {
      fetched_at: null,
      items: [],
      errors: [],
      stack: [],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        expect(url).toBe(`${API_BASE}/pulse`);
        return {
          ok: true,
          status: 200,
          statusText: "OK",
          json: async () => payload,
        };
      }),
    );
    await expect(getPulse()).resolves.toEqual(payload);
  });

  it("POST /pulse/refresh", async () => {
    let method = "";
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) => {
        method = init?.method ?? "GET";
        return {
          ok: true,
          status: 200,
          statusText: "OK",
          json: async () => ({
            fetched_at: "2026-09-13T23:53:30+00:00",
            items: [],
            errors: [],
            stack: [],
          }),
        };
      }),
    );
    await refreshPulse();
    expect(method).toBe("POST");
  });

  it("POST /pulse/memos/refine sends the full item + stack", async () => {
    const src = item({ topic: "T", paper_id: "2501.00001" });
    let body: unknown;
    let method = "";
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) => {
        method = init?.method ?? "GET";
        body = JSON.parse(String(init?.body));
        return {
          ok: true,
          status: 200,
          statusText: "OK",
          json: async () => ({
            item_key: "2501.00001",
            stack_key: "a,b",
            memo: { ...src.memo, verdict: "Adopt", origin: "groq" },
          }),
        };
      }),
    );
    const res = await refineMemo(src, ["pytorch", "hf"]);
    expect(method).toBe("POST");
    expect(body).toEqual({ item: src, stack: ["pytorch", "hf"] });
    expect(res.memo.verdict).toBe("Adopt");
    expect(res.item_key).toBe("2501.00001");
  });

  it("throws ApiError with the server detail on 4xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 422,
        statusText: "Unprocessable Entity",
        json: async () => ({ detail: "Unknown layer" }),
      })),
    );
    await expect(getPulse()).rejects.toBeInstanceOf(ApiError);
    await expect(getPulse()).rejects.toMatchObject({
      status: 422,
      detail: "Unknown layer",
    });
  });
});
