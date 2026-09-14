import { describe, expect, it, vi, afterEach } from "vitest";
import {
  CONSULT_LAYERS,
  LAYER_LABELS,
  LAYER_HINTS,
  LAYER_PLACEHOLDERS,
  OFFLINE_MESSAGE,
  decodeSse,
  streamConsult,
  getSettings,
  updateSettings,
  loadRepoReadme,
  buildApplyPrompt,
  getHistory,
  setHistory,
  getDemoKey,
  setDemoKey,
  type ConsultTurn,
  type SseEvent,
} from "@/lib/consult";
import { ApiError } from "@/lib/api";

// ------------------------------------------------------------- constants

describe("parity constants", () => {
  it("layers, labels, hints and placeholders are the Streamlit strings", () => {
    expect(CONSULT_LAYERS).toEqual(["apply", "explain", "systems"]);
    expect(LAYER_LABELS).toEqual({
      apply: "1 · Apply to my system",
      explain: "2 · Plain English",
      systems: "3 · Systems critic",
    });
    expect(LAYER_HINTS.apply).toContain("Default · map the paper onto YOUR application");
    expect(LAYER_HINTS.explain).toContain("Short plain-English briefing");
    expect(LAYER_HINTS.systems).toContain("No introductory lectures.");
    expect(LAYER_PLACEHOLDERS.apply).toBe(
      "How do I apply this paper to my system given the papers I already use?",
    );
    expect(LAYER_PLACEHOLDERS.explain).toBe(
      "Ask for a short plain-English explanation of a paper or idea.",
    );
    expect(LAYER_PLACEHOLDERS.systems).toBe(
      "Sketch a training/serving design. The critic will attack it.",
    );
  });

  it("OFFLINE_MESSAGE is byte-identical to providers.py", () => {
    expect(OFFLINE_MESSAGE).toBe(
      "Consultant is offline. Set `GROQ_API_KEY` in `.env`.",
    );
  });
});

// --------------------------------------------------------------- decodeSse

describe("decodeSse", () => {
  it("decodes a single complete frame", () => {
    const { events, rest } = decodeSse(
      'event: delta\ndata: {"text": "hi"}\n\n',
    );
    expect(rest).toBe("");
    expect(events).toEqual([{ type: "delta", text: "hi" }]);
  });

  it("decodes multiple frames in one chunk", () => {
    const { events, rest } = decodeSse(
      'event: sources\ndata: {"sources": [{"kind": "arxiv", "title": "T1", "url": "u1"}]}\n\n' +
        'event: delta\ndata: {"text": "a"}\n\n' +
        'event: delta\ndata: {"text": "b"}\n\n',
    );
    expect(rest).toBe("");
    expect(events).toHaveLength(3);
    expect(events[0]).toEqual({
      type: "sources",
      sources: [{ kind: "arxiv", title: "T1", url: "u1" }],
    });
    expect(events[1]).toEqual({ type: "delta", text: "a" });
    expect(events[2]).toEqual({ type: "delta", text: "b" });
  });

  it("buffers a trailing partial frame until the next chunk", () => {
    const first = decodeSse('event: delta\ndata: {"tex');
    expect(first.events).toEqual([]);
    expect(first.rest).toBe('event: delta\ndata: {"tex');
    const second = decodeSse(first.rest + 't": "hi"}\n\n');
    expect(second.rest).toBe("");
    expect(second.events).toEqual([{ type: "delta", text: "hi" }]);
  });

  it("keeps a frame partial when the delimiter itself is split", () => {
    const first = decodeSse('event: done\ndata: {"content": "x"}\n');
    expect(first.events).toEqual([]);
    expect(first.rest).toBe('event: done\ndata: {"content": "x"}\n');
    const second = decodeSse(first.rest + "\n");
    expect(second.events).toEqual([
      { type: "done", content: "x", model: "", provider: "", layer: "" },
    ]);
  });

  it("drops unknown event names and invalid JSON", () => {
    const { events } = decodeSse(
      'event: ping\ndata: {"x": 1}\n\n' +
        'event: delta\ndata: not-json\n\n' +
        'event: error\ndata: {"message": "boom"}\n\n',
    );
    expect(events).toEqual([{ type: "error", message: "boom" }]);
  });

  it("decodes done with the full payload", () => {
    const { events } = decodeSse(
      'event: done\ndata: {"content": "ok", "model": "m", "provider": "p", "layer": "apply"}\n\n',
    );
    expect(events).toEqual([
      { type: "done", content: "ok", model: "m", provider: "p", layer: "apply" },
    ]);
  });
});

// ----------------------------------------------------------- buildApplyPrompt

describe("buildApplyPrompt (consultant.py paper_apply_prompt parity)", () => {
  const paper = {
    id: "2608.17906",
    title: "Scaling Laws for RL",
    authors: "A One, B Two",
    published_date: "2026-08-19",
    summary_raw: "An abstract.",
  };

  it("no context: exact template", () => {
    expect(
      buildApplyPrompt(paper, {
        application: "",
        known_papers: "",
        repo_url: "",
      }),
    ).toBe(
      "Map this paper onto my current application. What is relevant, what to ignore, " +
        "and how I implement it. Use user / item (or target) / data / training / serving / eval; " +
        "rename those to my modules. Do not assume a rec stack.\n" +
        "\n" +
        "Title: Scaling Laws for RL\n" +
        "Authors: A One, B Two\n" +
        "arXiv: 2608.17906\n" +
        "Date: 2026-08-19\n\n" +
        "Abstract:\nAn abstract.",
    );
  });

  it("full context: My system / I already use / My repo + README delta line", () => {
    expect(
      buildApplyPrompt(paper, {
        application: "RL post-training loop",
        known_papers: "PPO, DPO",
        repo_url: "https://github.com/you/your-service",
      }),
    ).toBe(
      "Map this paper onto my current application. What is relevant, what to ignore, " +
        "and how I implement it. Use user / item (or target) / data / training / serving / eval; " +
        "rename those to my modules. Do not assume a rec stack.\n" +
        "\nMy system: RL post-training loop\n" +
        "I already use: PPO, DPO\n" +
        "My repo: https://github.com/you/your-service\n" +
        "Delta against the repo README in retrieved sources — what is already shipped.\n" +
        "\n" +
        "Title: Scaling Laws for RL\n" +
        "Authors: A One, B Two\n" +
        "arXiv: 2608.17906\n" +
        "Date: 2026-08-19\n\n" +
        "Abstract:\nAn abstract.",
    );
  });

  it("partial context: only the set fields appear (trimmed)", () => {
    const out = buildApplyPrompt(paper, {
      application: "  RAG over a corpus  ",
      known_papers: "   ",
      repo_url: "",
    });
    expect(out).toContain("\nMy system: RAG over a corpus\n");
    expect(out).not.toContain("I already use");
    expect(out).not.toContain("My repo");
    expect(out).not.toContain("Delta against");
  });

  it("blank paper fields fall back like the Python version", () => {
    const out = buildApplyPrompt(
      { id: "", title: "", authors: "", published_date: "", summary_raw: "" },
      { application: "", known_papers: "", repo_url: "" },
    );
    // Trailing space before the newline is part of the Python template.
    expect(out).toContain("Title: Untitled\n");
    expect(out).toContain("Authors: \n");
    expect(out).toContain("arXiv: \n");
    expect(out).toContain("Date: \n\n");
    expect(out).toContain("Abstract:\n");
  });
});

// --------------------------------------------------------------- streamConsult

function sseFrames(frames: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  let index = 0;
  return new ReadableStream({
    pull(controller) {
      if (index < frames.length) {
        controller.enqueue(enc.encode(frames[index++]));
      } else {
        controller.close();
      }
    },
  });
}

describe("streamConsult", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("posts the body and delivers sources/delta/done across split chunks", async () => {
    const history: ConsultTurn[] = [
      { role: "user", content: "earlier" },
      { role: "assistant", content: "earlier reply" },
    ];
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      body: sseFrames([
        'event: sources\ndata: {"sources": [{"kind": "arxiv", "title": "T1", "url": "u1"}]}\n',
        '\nevent: delta\ndata: {"text": "hel',
        'lo"}\n\nevent: delta\ndata: {"text": "world"}\n\n',
        'event: done\ndata: {"content": "helloworld", "model": "m", "provider": "p", "layer": "explain"}\n\n',
      ]),
    });
    vi.stubGlobal("fetch", fetchMock);

    const events: SseEvent[] = [];
    await streamConsult(
      { message: "next", history, layer: "explain", apiKey: "sk-test" },
      (ev) => events.push(ev),
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/consult/chat");
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({
      message: "next",
      history,
      layer: "explain",
      api_key: "sk-test",
    });
    expect(events).toEqual([
      { type: "sources", sources: [{ kind: "arxiv", title: "T1", url: "u1" }] },
      { type: "delta", text: "hello" },
      { type: "delta", text: "world" },
      { type: "done", content: "helloworld", model: "m", provider: "p", layer: "explain" },
    ]);
  });

  it("sends api_key null when no demo key", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      body: sseFrames(['event: done\ndata: {"content": "", "model": "m", "provider": "p", "layer": "apply"}\n\n']),
    });
    vi.stubGlobal("fetch", fetchMock);
    await streamConsult({ message: "m", history: [], layer: "apply" }, () => {});
    const body = JSON.parse(
      (fetchMock.mock.calls[0][1] as RequestInit).body as string,
    );
    expect(body.api_key).toBeNull();
  });

  it("throws ApiError with the server detail on HTTP errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        statusText: "Bad Gateway",
        json: async () => ({ detail: "README fetch failed: no" }),
      }),
    );
    await expect(
      streamConsult({ message: "m", history: [], layer: "apply" }, () => {}),
    ).rejects.toMatchObject({
      name: "ApiError",
      status: 502,
      detail: "README fetch failed: no",
    });
  });

  it("throws ApiError(0) when the fetch itself fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNREFUSED")));
    const err = await streamConsult(
      { message: "m", history: [], layer: "apply" },
      () => {},
    ).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(0);
  });

  it("rethrows AbortError untouched", async () => {
    const abort = new DOMException("Aborted", "AbortError");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abort));
    const err = await streamConsult(
      { message: "m", history: [], layer: "apply" },
      () => {},
    ).catch((e) => e);
    expect(err).toBe(abort);
  });

  it("delivers an in-stream error event", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      body: sseFrames(['event: error\ndata: {"message": "rate limited"}\n\n']),
    }));
    const events: SseEvent[] = [];
    await streamConsult({ message: "m", history: [], layer: "systems" }, (ev) =>
      events.push(ev),
    );
    expect(events).toEqual([{ type: "error", message: "rate limited" }]);
  });
});

// ---------------------------------------------------------------- settings

describe("settings endpoints (via stubbed fetch)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const payload = {
    stack: ["pytorch"],
    stack_choices: ["pytorch", "jax"],
    application: "app",
    known_papers: "PPO",
    repo_url: "",
    repo_readme_url: "",
    repo_readme_chars: 0,
  };

  it("getSettings GETs /settings", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => payload,
    });
    vi.stubGlobal("fetch", fetchMock);
    await expect(getSettings()).resolves.toEqual(payload);
    expect(fetchMock.mock.calls[0][0]).toContain("/settings");
  });

  it("updateSettings PUTs the partial patch", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => ({ ...payload, stack: ["jax"] }),
    });
    vi.stubGlobal("fetch", fetchMock);
    await updateSettings({ stack: ["jax"] });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/settings");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body as string)).toEqual({ stack: ["jax"] });
  });

  it("loadRepoReadme POSTs the url when given", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => ({
        repo_url: "https://github.com/you/your-service",
        readme_url: "https://raw.githubusercontent.com/you/your-service/main/README.md",
        chars: 1234,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const out = await loadRepoReadme("https://github.com/you/your-service");
    expect(out.chars).toBe(1234);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/settings/repo-readme");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      url: "https://github.com/you/your-service",
    });
  });

  it("loadRepoReadme without url POSTs an empty body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => ({ repo_url: "", readme_url: "", chars: 0 }),
    });
    vi.stubGlobal("fetch", fetchMock);
    await loadRepoReadme();
    expect(
      JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string),
    ).toEqual({});
  });

  it("surfaces the server 400 detail for a missing repo url", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        statusText: "Bad Request",
        json: async () => ({
          detail: "No repo URL set. Set it in settings first.",
        }),
      }),
    );
    await expect(loadRepoReadme()).rejects.toMatchObject({
      status: 400,
      detail: "No repo URL set. Set it in settings first.",
    });
  });
});

// ------------------------------------------------------- in-memory session store

describe("in-memory session storage (st.session_state parity)", () => {
  it("isolates history per layer and clears on empty", () => {
    setHistory("apply", [{ role: "user", content: "a" }]);
    setHistory("explain", [{ role: "user", content: "e" }]);
    expect(getHistory("apply")).toEqual([{ role: "user", content: "a" }]);
    expect(getHistory("explain")).toEqual([{ role: "user", content: "e" }]);
    expect(getHistory("systems")).toEqual([]);
    setHistory("apply", []);
    expect(getHistory("apply")).toEqual([]);
  });

  it("stores the demo key for the session only", () => {
    setDemoKey("gsk_123");
    expect(getDemoKey()).toBe("gsk_123");
    setDemoKey("");
    expect(getDemoKey()).toBe("");
  });
});
