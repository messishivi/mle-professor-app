/**
 * Constants mirrored from the Streamlit app for parity.
 * Keep in sync with app.py (CATEGORY_OPTIONS, pipeline.DEFAULT_CATEGORIES).
 */

export const CATEGORY_OPTIONS = [
  "cs.CL",
  "cs.LG",
  "cs.AI",
  "cs.CV",
  "cs.NE",
  "stat.ML",
  "cs.DC",
  "cs.SE",
] as const;

export const DEFAULT_CATEGORIES: readonly string[] = ["cs.CL", "cs.LG"];
