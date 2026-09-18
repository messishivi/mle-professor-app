import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * design.md §5 claims WCAG AA contrast for all text in both themes
 * (body ≥ 7:1, secondary ≥ 4.5:1, accent-as-text ≥ 4.5:1). This suite pins
 * that claim against the committed tokens in app/globals.css so a token
 * drift back below AA fails the build.
 */

const here = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(join(here, "..", "app", "globals.css"), "utf8");

function blockTokens(selector: string): Record<string, string> {
  const m = css.match(new RegExp(`${selector}\\s*\\{([^}]*)\\}`));
  expect(m, `CSS block ${selector} not found`).toBeTruthy();
  const out: Record<string, string> = {};
  for (const t of m![1].matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})/g)) {
    out[t[1]] = t[2].toLowerCase();
  }
  return out;
}

function luminance(hex: string): number {
  const c = hex.slice(1);
  const [r, g, b] = [0, 2, 4]
    .map((i) => parseInt(c.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const TEXT_TOKENS = ["ink-0", "ink-1", "ink-2", "accent", "ok", "warn", "bad"];
const SURFACES = ["bg-0", "bg-1", "bg-2", "bg-3"];

for (const theme of ["dark", "light"]) {
  describe(`contrast: ${theme} theme (design.md §5)`, () => {
    const tokens = blockTokens(
      theme === "dark" ? ":root" : "[data-theme=\"light\"]",
    );

    for (const surface of SURFACES) {
      for (const text of TEXT_TOKENS) {
        it(`${text} on ${surface} clears 4.5:1 (AA)`, () => {
          expect(
            contrast(tokens[text], tokens[surface]),
            `${text} ${tokens[text]} on ${surface} ${tokens[surface]}`,
          ).toBeGreaterThanOrEqual(4.5);
        });
      }
    }

    for (const surface of SURFACES) {
      it(`ink-0 (body) on ${surface} clears 7:1`, () => {
        expect(
          contrast(tokens["ink-0"], tokens[surface]),
          `ink-0 ${tokens["ink-0"]} on ${surface} ${tokens[surface]}`,
        ).toBeGreaterThanOrEqual(7);
      });
    }
  });
}
