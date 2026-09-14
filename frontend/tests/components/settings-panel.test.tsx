import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "@/lib/api";
import type { SettingsPayload } from "@/lib/consult";

const { getSettingsMock, updateSettingsMock, loadReadmeMock, statusMock } =
  vi.hoisted(() => ({
    getSettingsMock: vi.fn(),
    updateSettingsMock: vi.fn(),
    loadReadmeMock: vi.fn(),
    statusMock: vi.fn(),
  }));

// Keep the real pure helpers; stub only the network fns.
vi.mock("@/lib/consult", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/consult")>();
  return {
    ...actual,
    getSettings: (...a: unknown[]) => getSettingsMock(...a),
    updateSettings: (...a: unknown[]) => updateSettingsMock(...a),
    loadRepoReadme: (...a: unknown[]) => loadReadmeMock(...a),
  };
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

import { SettingsPanel } from "@/components/settings-panel";
import { getProviderSelection, setProviderSelection } from "@/lib/consult";

const basePayload: SettingsPayload = {
  stack: [],
  stack_choices: ["RL", "RAG", "Rec"],
  application: "",
  known_papers: "",
  repo_url: "",
  repo_readme_url: "",
  repo_readme_chars: 0,
};

// /consult/status fixture — mirrors the backend providers registry (P5).
const LLM_STATUS = {
  ready: false,
  provider: "groq",
  model: "openai/gpt-oss-120b",
  demo_mode: false,
  offline_message: "Consultant is offline. Set `GROQ_API_KEY` in `.env`.",
  providers: {
    groq: {
      ready: false,
      model: "openai/gpt-oss-120b",
      offline_message: "Consultant is offline. Set `GROQ_API_KEY` in `.env`.",
    },
    openai: {
      ready: false,
      model: "gpt-4o-mini",
      offline_message: "Consultant is offline. Set `OPENAI_API_KEY` in `.env`.",
    },
    anthropic: {
      ready: false,
      model: "claude-sonnet-4-5",
      offline_message: "Consultant is offline. Set `ANTHROPIC_API_KEY` in `.env`.",
    },
    local: {
      ready: true,
      model: "local",
      offline_message:
        "Consultant is offline. Start a local OpenAI-compatible server (e.g. " +
        "llama.cpp) and set `LOCAL_BASE_URL` in `.env`.",
    },
  },
};

beforeEach(() => {
  vi.clearAllMocks();
  setProviderSelection({ provider: "", models: {}, keys: {} });
  getSettingsMock.mockResolvedValue(basePayload);
  updateSettingsMock.mockImplementation(async (patch: Record<string, unknown>) => ({
    ...basePayload,
    ...patch,
  }));
  loadReadmeMock.mockResolvedValue({
    chars: 1234,
    repo_url: "https://github.com/x/y",
    readme_url: "https://raw.githubusercontent.com/x/y/main/README.md",
  });
  statusMock.mockResolvedValue(LLM_STATUS);
});

describe("SettingsPanel", () => {
  it("renders the server-side values with exact Streamlit sidebar strings", async () => {
    getSettingsMock.mockResolvedValue({
      ...basePayload,
      stack: ["RL"],
      application: "RL post-training loop",
      known_papers: "PPO",
    });
    render(<SettingsPanel />);
    // Wait on a heading that only exists after the payload loads (the
    // loading state also renders an h1 "Settings", which would resolve a
    // role query on a node that is then detached).
    await screen.findByRole("heading", { name: "Your stack" });
    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(
      screen.getByText("Pulse ranks papers as High fit / Watch / Skip against this."),
    ).toBeInTheDocument();
    // Chip multiselect parity: RL active, others not.
    expect(screen.getByRole("button", { name: "RL" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "RAG" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    // The active-stack summary line (the chip button also says "RL").
    const stackSection = within(
      screen.getByRole("heading", { name: "Your stack" }).closest("section") as HTMLElement,
    );
    expect(stackSection.getByText("RL", { selector: "p" })).toBeInTheDocument();
    expect(
      screen.getByRole("textbox", { name: "I’m building" }),
    ).toHaveValue("RL post-training loop");
    expect(
      screen.getByRole("textbox", { name: "Papers I already use" }),
    ).toHaveValue("PPO");
    expect(
      screen.getByRole("textbox", {
        name: "Repo (README)",
      }),
    ).toHaveValue("");
    // Exact placeholders (Streamlit sidebar parity).
    expect(
      screen.getByPlaceholderText(
        "What you ship — e.g. RL post-training, RAG over a corpus, two-tower rec… train/serve split",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Methods already in the stack, e.g. PPO, DPO"),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("https://github.com/you/your-service"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Public GitHub/GitLab README is used in Apply delta. Sent to Groq. No private/company repos.",
      ),
    ).toBeInTheDocument();
    // No README loaded yet → the exact idle caption, no Load button (no URL).
    expect(
      screen.getByText("Paste a public repo, then load the README for Apply delta."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Load README" })).toBeNull();
  });

  it("chip toggle PUTs the new stack immediately and updates the summary", async () => {
    const user = userEvent.setup();
    render(<SettingsPanel />);
    await screen.findByRole("heading", { name: "Your stack" });
    await user.click(screen.getByRole("button", { name: "RAG" }));
    await waitFor(() =>
      expect(updateSettingsMock).toHaveBeenCalledWith({ stack: ["RAG"] }),
    );
    expect(screen.getByRole("button", { name: "RAG" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    const stackSection = within(
      screen.getByRole("heading", { name: "Your stack" }).closest("section") as HTMLElement,
    );
    expect(stackSection.getByText("RAG", { selector: "p" })).toBeInTheDocument();
    // Toggle off removes it.
    await user.click(screen.getByRole("button", { name: "RAG" }));
    await waitFor(() =>
      expect(updateSettingsMock).toHaveBeenLastCalledWith({ stack: [] }),
    );
  });

  it("saves on blur only when the value changed", async () => {
    const user = userEvent.setup();
    render(<SettingsPanel />);
    await screen.findByRole("heading", { name: "Your stack" });
    const appBox = screen.getByRole("textbox", { name: "I’m building" });
    await user.clear(appBox);
    await user.type(appBox, "RAG over a corpus");
    await user.click(screen.getByRole("heading", { name: "Your stack" }));
    await waitFor(() =>
      expect(updateSettingsMock).toHaveBeenCalledWith({
        application: "RAG over a corpus",
      }),
    );
    // A blur with no changes must not PUT: refocus, then blur again.
    updateSettingsMock.mockClear();
    await user.click(appBox);
    await user.click(screen.getByRole("heading", { name: "Your stack" }));
    // Give a (wrong) async PUT a chance to fire before asserting absence.
    await new Promise((r) => setTimeout(r, 50));
    expect(updateSettingsMock).not.toHaveBeenCalled();
  });

  it("repo blur saves the URL first, then loads the README (server clears the cache)", async () => {
    const user = userEvent.setup();
    render(<SettingsPanel />);
    await screen.findByRole("heading", { name: "Your stack" });
    const repoInput = screen.getByRole("textbox", { name: "Repo (README)" });
    await user.type(repoInput, "https://github.com/x/y");
    await user.click(screen.getByRole("heading", { name: "Your stack" }));
    await waitFor(() =>
      expect(updateSettingsMock).toHaveBeenCalledWith({
        repo_url: "https://github.com/x/y",
      }),
    );
    // The README load follows the successful save.
    await waitFor(() =>
      expect(loadReadmeMock).toHaveBeenCalledWith("https://github.com/x/y"),
    );
    expect(
      await screen.findByText("README loaded · 1234 chars · used in Apply delta"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Reload README" }),
    ).toBeInTheDocument();
  });

  it("surfaces the server README error detail", async () => {
    loadReadmeMock.mockRejectedValue(
      new ApiError(502, "README fetch failed: boom"),
    );
    getSettingsMock.mockResolvedValue({ ...basePayload, repo_url: "https://github.com/x/y" });
    const user = userEvent.setup();
    render(<SettingsPanel />);
    await screen.findByRole("heading", { name: "Your stack" });
    await user.click(screen.getByRole("button", { name: "Load README" }));
    expect(
      await screen.findByText("README fetch failed: boom"),
    ).toBeInTheDocument();
  });

  it("Load README button posts with the current URL and shows the fetched chars", async () => {
    getSettingsMock.mockResolvedValue({
      ...basePayload,
      repo_url: "https://github.com/x/y",
      repo_readme_chars: 0,
    });
    const user = userEvent.setup();
    render(<SettingsPanel />);
    await screen.findByRole("heading", { name: "Your stack" });
    const loadBtn = screen.getByRole("button", { name: "Load README" });
    await user.click(loadBtn);
    await waitFor(() =>
      expect(loadReadmeMock).toHaveBeenCalledWith("https://github.com/x/y"),
    );
    expect(
      await screen.findByText("README loaded · 1234 chars · used in Apply delta"),
    ).toBeInTheDocument();
  });

  it("surfaces a settings-load failure with Retry", async () => {
    getSettingsMock.mockRejectedValue(
      new ApiError(0, "Cannot reach the API at http://127.0.0.1:8000"),
    );
    const user = userEvent.setup();
    render(<SettingsPanel />);
    expect(
      await screen.findByText("Cannot reach the API at http://127.0.0.1:8000"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(getSettingsMock).toHaveBeenCalledTimes(2);
  });

  // ---------------------------------------------------------------- P5:
  // the "Consultant LLM provider" section (session-only store).

  it("renders the provider section from the /consult/status map", async () => {
    render(<SettingsPanel />);
    expect(
      await screen.findByRole("heading", { name: "Consultant LLM provider" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "server default (LLM_PROVIDER)" }),
    ).toBeInTheDocument();
    // Registry order + readiness suffix, exactly as the backend reports.
    expect(
      screen.getByRole("option", { name: "groq · needs key" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "openai · needs key" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "anthropic · needs key" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "local · ready" })).toBeInTheDocument();
    // No provider picked yet → model/key inputs are disabled (password
    // inputs are not in the role "textbox" set, so match by placeholder).
    const disabled = screen.getAllByPlaceholderText("pick a provider first");
    expect(disabled).toHaveLength(2);
    for (const el of disabled) expect(el).toBeDisabled();
  });

  it("selecting a provider prefills the model and applies the session store", async () => {
    const user = userEvent.setup();
    render(<SettingsPanel />);
    await screen.findByRole("heading", { name: "Consultant LLM provider" });
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Provider" }),
      "openai",
    );
    // First contact with the provider: prefilled from the status map.
    expect(screen.getByRole("textbox", { name: "Model" })).toHaveValue(
      "gpt-4o-mini",
    );
    // Password input: not in the role "textbox" set — match the BYOK placeholder.
    await user.type(screen.getByPlaceholderText("sk-…"), "sk-user");
    // The real in-memory store holds the selection (the terminal reads it).
    expect(getProviderSelection()).toEqual({
      provider: "openai",
      models: { openai: "gpt-4o-mini" },
      keys: { openai: "sk-user" },
    });
  });

  it("a provider status-load failure degrades only the provider section", async () => {
    statusMock.mockRejectedValue(new ApiError(0, "no backend for llm"));
    render(<SettingsPanel />);
    expect(await screen.findByText(/no backend for llm/)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Your stack" }),
    ).toBeInTheDocument();
  });
});
