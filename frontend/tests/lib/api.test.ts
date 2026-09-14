import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  API_BASE,
  ApiError,
  ingest,
  listPapers,
  patchPaper,
} from "@/lib/api";

const mockFetch = vi.fn();

beforeEach(() => {
  mockFetch.mockReset();
  vi.stubGlobal("fetch", mockFetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResponse(data: unknown, ok = true, status = 200) {
  return {
    ok,
    status,
    statusText: ok ? "OK" : "Error",
    json: async () => data,
  };
}

describe("api client", () => {
  it("lists papers with no params", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ count: 0, papers: [] }),
    );
    const res = await listPapers();
    expect(res).toEqual({ count: 0, papers: [] });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe(`${API_BASE}/papers`);
    expect(init?.method).toBeUndefined();
  });

  it("lists papers with search, read and limit params", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ count: 1, papers: [{ id: "1" }] }),
    );
    await listPapers({ q: "attention", read: 0, limit: 10 });
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe(`${API_BASE}/papers?q=attention&read=0&limit=10`);
  });

  it("PATCHes a paper's read status", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ id: "1706.03762", read_status: 1 }),
    );
    const res = await patchPaper("1706.03762", 1);
    expect(res.read_status).toBe(1);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe(`${API_BASE}/papers/1706.03762`);
    expect(init?.method).toBe("PATCH");
    expect(JSON.parse(init?.body as string)).toEqual({ read_status: 1 });
  });

  it("posts ingest with categories and max_results", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ query: "cat:cs.CL", fetched: 5, upserted: 2, skipped: 3, papers: [], errors: [] }),
    );
    await ingest({ categories: ["cs.CL", "cs.LG"], max_results: 25 });
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe(`${API_BASE}/papers/ingest`);
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({
      categories: ["cs.CL", "cs.LG"],
      max_results: 25,
    });
  });

  it("throws ApiError with FastAPI detail on non-2xx", async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ detail: "No paper with id 'nope'" }, false, 404),
    );
    await expect(patchPaper("nope", 1)).rejects.toThrow(
      ApiError,
    );
    try {
      await patchPaper("nope", 1);
    } catch (exc) {
      expect((exc as ApiError).status).toBe(404);
      expect((exc as ApiError).detail).toBe("No paper with id 'nope'");
    }
  });

  it("throws ApiError when the API is unreachable", async () => {
    mockFetch.mockRejectedValue(new TypeError("fetch failed"));
    await expect(listPapers()).rejects.toThrow(/Cannot reach the API/);
  });

  it("falls back to status text for non-JSON error bodies", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
      json: async () => {
        throw new Error("not json");
      },
    });
    try {
      await listPapers();
    } catch (exc) {
      expect((exc as ApiError).status).toBe(502);
      expect((exc as ApiError).detail).toBe("502 Bad Gateway");
    }
  });
});
