"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getConsultStatus } from "@/lib/api";
import type { ConsultStatus } from "@/lib/api";
import {
  getProviderSelection,
  getSettings,
  loadRepoReadme,
  setProviderSelection,
  updateSettings,
} from "@/lib/consult";
import type { ProviderSelection, SettingsPayload } from "@/lib/consult";

function errMsg(exc: unknown, fallback: string): string {
  if (exc instanceof ApiError) return exc.detail;
  return exc instanceof Error ? exc.message : fallback;
}

/** BYOK placeholder per provider (P5). */
const KEY_PLACEHOLDERS: Record<string, string> = {
  groq: "gsk_…",
  openai: "sk-…",
  anthropic: "sk-ant-…",
  local: "optional — keyless",
};

/**
 * Settings pane (Streamlit sidebar parity, app.py:233-303):
 * - "Your stack" chips (multiselect parity) with the exact ranking caption
 * - "I'm building" / "Papers I already use" with exact placeholders
 * - "Repo (README)" with the exact help caption; Load/Reload README button
 *
 * Original-design adaptations (documented in the P3c commit):
 * - chips save immediately on toggle (Streamlit autosaves on change)
 * - the FE cannot run parse_repo(), so the Load README button is shown for
 *   any non-empty URL; an unparseable URL surfaces the server's 400 message
 *   ("Need a GitHub or GitLab repo URL." equivalent)
 * - the README preview body is omitted: the API exposes repo_readme_chars,
 *   not the content, and the backend is frozen for this increment
 *
 * P5 additions (no Streamlit equivalent):
 * - "Consultant LLM provider" section: provider dropdown (from
 *   /consult/status `providers`), per-provider model override + BYOK key.
 *   Saved to the in-memory session store only (setProviderSelection) — the
 *   backend has no provider persistence (auth DEFERRED), so there is no
 *   separate server round-trip; changes apply to the next Consultant request.
 */
export function SettingsPanel() {
  const [payload, setPayload] = useState<SettingsPayload | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [stack, setStack] = useState<string[]>([]);
  const [application, setApplication] = useState("");
  const [knownPapers, setKnownPapers] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [readmeLoading, setReadmeLoading] = useState(false);
  const [readmeError, setReadmeError] = useState<string | null>(null);
  const [readmeChars, setReadmeChars] = useState(0);
  const [llmStatus, setLlmStatus] = useState<ConsultStatus | null>(null);
  const [llmStatusError, setLlmStatusError] = useState<string | null>(null);
  const [sel, setSel] = useState<ProviderSelection>(() =>
    getProviderSelection(),
  );
  const mounted = useRef(false);

  const load = useCallback(() => {
    setLoadError(null);
    getSettings()
      .then((s) => {
        setPayload(s);
        setStack(s.stack);
        setApplication(s.application);
        setKnownPapers(s.known_papers);
        setRepoUrl(s.repo_url);
        setReadmeChars(s.repo_readme_chars);
      })
      .catch((exc) => setLoadError(errMsg(exc, "Cannot reach the API.")));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // P5: provider readiness for the Consultant LLM section (failure degrades
  // the section, not the page).
  const loadLlmStatus = useCallback(() => {
    setLlmStatusError(null);
    getConsultStatus()
      .then(setLlmStatus)
      .catch((exc) => {
        setLlmStatus(null);
        setLlmStatusError(errMsg(exc, "Cannot reach the API."));
      });
  }, []);

  useEffect(() => {
    loadLlmStatus();
  }, [loadLlmStatus]);

  // P5: every provider change commits to the in-memory session store — the
  // Consultant terminal reads it per request (no server round-trip).
  const applySelection = useCallback((next: ProviderSelection) => {
    setSel(next);
    setProviderSelection(next);
  }, []);

  const onProviderChange = useCallback(
    (name: string) => {
      const models = { ...sel.models };
      if (name && models[name] === undefined) {
        // First contact with a provider: prefill the server's resolved model.
        models[name] = llmStatus?.providers?.[name]?.model ?? "";
      }
      applySelection({ provider: name, models, keys: { ...sel.keys } });
    },
    [sel, llmStatus, applySelection],
  );

  const onModelChange = useCallback(
    (value: string) => {
      if (!sel.provider) return;
      applySelection({
        ...sel,
        models: { ...sel.models, [sel.provider]: value },
      });
    },
    [sel, applySelection],
  );

  const onKeyChange = useCallback(
    (value: string) => {
      if (!sel.provider) return;
      applySelection({
        ...sel,
        keys: { ...sel.keys, [sel.provider]: value },
      });
    },
    [sel, applySelection],
  );

  const markSaved = useCallback(() => {
    setSavedAt(
      new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    );
    setSaveError(null);
  }, []);

  const toggleStack = useCallback(
    (choice: string) => {
      if (!payload) return;
      const next = stack.includes(choice)
        ? stack.filter((c) => c !== choice)
        : [...stack, choice];
      setStack(next);
      setSaving(true);
      setSaveError(null);
      updateSettings({ stack: next })
        .then((s) => {
          setPayload(s);
          setStack(s.stack);
          markSaved();
        })
        .catch((exc) => {
          setStack(stack);
          setSaveError(errMsg(exc, "Could not save your stack."));
        })
        .finally(() => setSaving(false));
    },
    [payload, stack, markSaved],
  );

  const saveField = useCallback(
    (patch: { application?: string; known_papers?: string; repo_url?: string }) => {
      setSaving(true);
      setSaveError(null);
      updateSettings(patch)
        .then((s) => {
          setPayload(s);
          setReadmeChars(s.repo_readme_chars);
          markSaved();
        })
        .catch((exc) => setSaveError(errMsg(exc, "Could not save settings.")))
        .finally(() => setSaving(false));
    },
    [markSaved],
  );

  const loadReadme = useCallback(
    (url: string) => {
      setReadmeLoading(true);
      setReadmeError(null);
      loadRepoReadme(url)
        .then((res) => {
          setReadmeChars(res.chars);
          setRepoUrl(res.repo_url);
          setPayload((p) =>
            p
              ? {
                  ...p,
                  repo_url: res.repo_url,
                  repo_readme_url: res.readme_url,
                  repo_readme_chars: res.chars,
                }
              : p,
          );
          markSaved();
        })
        .catch((exc) =>
          setReadmeError(errMsg(exc, "README fetch failed.")),
        )
        .finally(() => setReadmeLoading(false));
    },
    [markSaved],
  );

  const onRepoBlur = useCallback(() => {
    if (!payload) return;
    const v = repoUrl.trim();
    if (v === payload.repo_url) return;
    // Save first: a repo URL change clears the cached README server-side.
    updateSettings({ repo_url: v })
      .then((s) => {
        setPayload(s);
        setReadmeChars(s.repo_readme_chars);
        markSaved();
        if (v) loadReadme(v);
      })
      .catch((exc) =>
        setSaveError(errMsg(exc, "Could not save the repo URL.")),
      );
  }, [payload, repoUrl, loadReadme, markSaved]);

  if (loadError) {
    return (
      <div className="mx-auto flex w-full max-w-[860px] flex-col gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-ink-0">
          Settings
        </h1>
        <p role="alert" className="rounded-lg border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">
          {loadError}{" "}
          <button
            type="button"
            onClick={load}
            className="font-mono text-xs underline hover:text-ink-0"
          >
            Retry
          </button>
        </p>
      </div>
    );
  }

  if (!payload) {
    return (
      <div className="mx-auto flex w-full max-w-[860px] flex-col gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-ink-0">
          Settings
        </h1>
        <p className="font-mono text-xs text-ink-2">loading…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-[860px] flex-col gap-6">
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-ink-0">
          Settings
        </h1>
        <p aria-live="polite" className="font-mono text-xs text-ink-2">
          {saving ? "saving…" : savedAt ? `saved · ${savedAt}` : ""}
        </p>
      </div>

      {saveError && (
        <p role="alert" className="rounded-lg border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">
          {saveError}
        </p>
      )}

      <section>
        <h2 className="text-sm font-semibold text-ink-0">
          Consultant LLM provider
        </h2>
        <p className="mt-0.5 text-xs text-ink-2">
          Sent with every Consultant request; kept in memory for this browser
          session only.
        </p>
        {llmStatusError ? (
          <p role="alert" className="mt-2 text-xs text-warn">
            {llmStatusError}{" "}
            <button
              type="button"
              onClick={loadLlmStatus}
              className="font-mono text-xs underline hover:text-ink-0"
            >
              Retry
            </button>
          </p>
        ) : llmStatus === null ? (
          <p className="mt-2 font-mono text-xs text-ink-2">
            checking consultant…
          </p>
        ) : (
          <>
            <label htmlFor="settings-provider" className="mt-3 block">
              <span className="font-mono text-xs text-ink-2">Provider</span>
              <select
                id="settings-provider"
                value={sel.provider}
                onChange={(e) => onProviderChange(e.target.value)}
                className="mt-1 w-full rounded-lg border border-line-0 bg-bg-0 px-3 py-2 font-mono text-sm text-ink-0 outline-none transition-colors duration-120 focus:border-accent"
              >
                <option value="">server default (LLM_PROVIDER)</option>
                {Object.entries(llmStatus.providers).map(([name, entry]) => (
                  <option key={name} value={name}>
                    {name} · {entry.ready ? "ready" : "needs key"}
                  </option>
                ))}
              </select>
            </label>
            <label htmlFor="settings-provider-model" className="mt-3 block">
              <span className="font-mono text-xs text-ink-2">Model</span>
              <input
                id="settings-provider-model"
                value={sel.provider ? (sel.models[sel.provider] ?? "") : ""}
                onChange={(e) => onModelChange(e.target.value)}
                disabled={!sel.provider}
                placeholder={
                  sel.provider
                    ? llmStatus.providers[sel.provider]?.model ||
                      "provider default"
                    : "pick a provider first"
                }
                className="mt-1 w-full rounded-lg border border-line-0 bg-bg-0 px-3 py-2 font-mono text-sm text-ink-0 outline-none transition-colors duration-120 focus:border-accent disabled:opacity-50"
              />
            </label>
            <label htmlFor="settings-provider-key" className="mt-3 block">
              <span className="font-mono text-xs text-ink-2">
                API key (this session only)
              </span>
              <input
                id="settings-provider-key"
                type="password"
                value={sel.provider ? (sel.keys[sel.provider] ?? "") : ""}
                onChange={(e) => onKeyChange(e.target.value)}
                disabled={!sel.provider}
                placeholder={
                  sel.provider
                    ? (KEY_PLACEHOLDERS[sel.provider] ?? "…")
                    : "pick a provider first"
                }
                className="mt-1 w-full rounded-lg border border-line-0 bg-bg-0 px-3 py-2 font-mono text-sm text-ink-0 outline-none transition-colors duration-120 focus:border-accent disabled:opacity-50"
              />
            </label>
            <p className="mt-1 text-xs text-ink-2">
              Never written to disk — lost on reload.
            </p>
          </>
        )}
      </section>

      <section>
        <h2 className="text-sm font-semibold text-ink-0">Your stack</h2>
        <p className="mt-0.5 text-xs text-ink-2">
          Pulse ranks papers as High fit / Watch / Skip against this.
        </p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {payload.stack_choices.map((choice) => {
            const active = stack.includes(choice);
            return (
              <button
                key={choice}
                type="button"
                aria-pressed={active}
                onClick={() => toggleStack(choice)}
                className={`rounded-lg border px-3 py-1.5 font-mono text-xs transition-colors duration-120 ${
                  active
                    ? "border-accent bg-accent/10 text-ink-0"
                    : "border-line-0 bg-bg-1 text-ink-1 hover:border-line-1"
                }`}
              >
                {choice}
              </button>
            );
          })}
        </div>
        {stack.length > 0 && (
          <p className="mt-2 text-xs text-ink-2">{stack.join(" · ")}</p>
        )}
      </section>

      <section>
        <label className="text-sm font-semibold text-ink-0" htmlFor="settings-application">
          I&rsquo;m building
        </label>
        <textarea
          id="settings-application"
          value={application}
          onChange={(e) => setApplication(e.target.value)}
          onBlur={() => {
            if (application !== payload.application)
              saveField({ application });
          }}
          placeholder="What you ship — e.g. RL post-training, RAG over a corpus, two-tower rec… train/serve split"
          rows={5}
          className="mt-2 w-full resize-y rounded-lg border border-line-0 bg-bg-0 px-3 py-2 text-sm text-ink-0 outline-none transition-colors duration-120 focus:border-accent"
        />
      </section>

      <section>
        <label className="text-sm font-semibold text-ink-0" htmlFor="settings-known-papers">
          Papers I already use
        </label>
        <input
          id="settings-known-papers"
          value={knownPapers}
          onChange={(e) => setKnownPapers(e.target.value)}
          onBlur={() => {
            if (knownPapers !== payload.known_papers)
              saveField({ known_papers: knownPapers });
          }}
          placeholder="Methods already in the stack, e.g. PPO, DPO"
          className="mt-2 w-full rounded-lg border border-line-0 bg-bg-0 px-3 py-2 text-sm text-ink-0 outline-none transition-colors duration-120 focus:border-accent"
        />
      </section>

      <section>
        <label className="text-sm font-semibold text-ink-0" htmlFor="settings-repo-url">
          Repo (README)
        </label>
        <input
          id="settings-repo-url"
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          onBlur={onRepoBlur}
          placeholder="https://github.com/you/your-service"
          className="mt-2 w-full rounded-lg border border-line-0 bg-bg-0 px-3 py-2 font-mono text-sm text-ink-0 outline-none transition-colors duration-120 focus:border-accent"
        />
        <p className="mt-1 text-xs text-ink-2">
          Public GitHub/GitLab README is used in Apply delta. Sent to Groq. No
          private/company repos.
        </p>

        {repoUrl.trim() !== "" && (
          <button
            type="button"
            onClick={() => loadReadme(repoUrl.trim())}
            disabled={readmeLoading}
            className="mt-3 w-full rounded-lg bg-accent px-4 py-2 font-mono text-xs font-medium text-bg-0 transition-opacity duration-120 hover:opacity-90 disabled:opacity-50"
          >
            {readmeLoading
              ? "Fetching README…"
              : readmeChars > 0
                ? "Reload README"
                : "Load README"}
          </button>
        )}

        {readmeError ? (
          <p role="alert" className="mt-2 text-xs text-warn">
            {readmeError}
          </p>
        ) : readmeChars > 0 ? (
          <p className="mt-2 text-xs text-ink-2">
            README loaded · {readmeChars} chars · used in Apply delta
          </p>
        ) : (
          <p className="mt-2 text-xs text-ink-2">
            Paste a public repo, then load the README for Apply delta.
          </p>
        )}
      </section>
    </div>
  );
}
