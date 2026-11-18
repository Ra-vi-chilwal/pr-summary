import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// Vitest blanks CSS imports, so read the file itself (tests run from the frontend folder).
const css = readFileSync(resolve(process.cwd(), "src/design/tokens.css"), "utf8");

/** WCAG 2.x contrast ratio between two #rrggbb colours. */
function contrast(a: string, b: string): number {
  const lum = (hex: string) => {
    const [r, g, bl] = [1, 3, 5].map((i) => {
      const c = parseInt(hex.slice(i, i + 2), 16) / 255;
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
  };
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const token = (name: string) => {
  const m = new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`).exec(css);
  if (!m) throw new Error(`token --${name} not found`);
  return m[1];
};

describe("design tokens meet WCAG AA (4.5:1 for text)", () => {
  const pairs: [string, string][] = [
    ["color-text", "color-bg"],
    ["color-text", "color-surface-sunken"],
    ["color-text-muted", "color-bg"],
    ["color-text-muted", "color-surface"],
    ["color-text-muted", "color-surface-sunken"],
    ["color-on-accent", "color-accent"],
    ["color-on-accent", "color-accent-hover"],
    ["color-accent", "color-bg"],
    ["color-accent", "color-accent-soft"],
    ["color-risk-high", "color-surface"],
    ["color-risk-high", "color-risk-high-soft"],
    ["color-risk-medium", "color-surface"],
    ["color-risk-medium", "color-risk-medium-soft"],
    ["color-success", "color-surface"],
    ["color-text", "color-diff-add-bg"],
    ["color-text", "color-diff-del-bg"],
    ["color-text-muted", "color-diff-hunk-bg"],
  ];
  it.each(pairs)("%s on %s", (fg, bg) => {
    expect(contrast(token(fg), token(bg))).toBeGreaterThanOrEqual(4.5);
  });
});
