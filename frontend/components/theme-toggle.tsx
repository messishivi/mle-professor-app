"use client";

import { useSyncExternalStore } from "react";

const STORAGE_KEY = "mle-theme";
const CHANGE_EVENT = "mle-theme-change";

type Theme = "dark" | "light";

// The external "store" is the data-theme attribute on <html>, which the
// head script in app/layout.tsx sets before first paint.
function readTheme(): Theme {
  return document.documentElement.getAttribute("data-theme") === "light"
    ? "light"
    : "dark";
}

function subscribe(callback: () => void) {
  window.addEventListener(CHANGE_EVENT, callback);
  window.addEventListener("storage", callback); // cross-tab changes
  return () => {
    window.removeEventListener(CHANGE_EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}

// Used only during SSR/hydration so the initial tree matches the server
// (dark default); React re-reads the real snapshot right after hydration.
function getServerSnapshot(): Theme {
  return "dark";
}

export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribe, readTheme, getServerSnapshot);
  const next: Theme = theme === "dark" ? "light" : "dark";

  return (
    <button
      type="button"
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      onClick={() => {
        const el = document.documentElement;
        if (next === "light") el.setAttribute("data-theme", "light");
        else el.removeAttribute("data-theme");
        try {
          localStorage.setItem(STORAGE_KEY, next);
        } catch {
          // private mode / storage disabled — theme still applies this visit
        }
        window.dispatchEvent(new Event(CHANGE_EVENT));
      }}
      className="flex size-8 items-center justify-center rounded-md border border-line-0 bg-bg-2 font-mono text-xs text-ink-1 transition-colors duration-120 hover:border-line-1 hover:text-ink-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
    >
      {theme === "dark" ? "◐" : "◑"}
    </button>
  );
}
