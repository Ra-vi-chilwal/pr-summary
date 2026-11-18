/**
 * Tiny frontend logger. Quiet in production: only warnings and errors are printed there.
 * Never pass diffs, tokens or passwords to it.
 */
type Level = "debug" | "info" | "warn" | "error";

const ORDER: Record<Level, number> = { debug: 10, info: 20, warn: 30, error: 40 };
const MIN: Level = import.meta.env.PROD ? "warn" : "debug";

function emit(level: Level, message: string, context?: Record<string, unknown>) {
  if (ORDER[level] < ORDER[MIN]) return;
  const line = context ? [`[pr-summary] ${message}`, context] : [`[pr-summary] ${message}`];
  // eslint-disable-next-line no-console
  console[level === "debug" ? "log" : level](...line);
}

export const logger = {
  debug: (m: string, c?: Record<string, unknown>) => emit("debug", m, c),
  info: (m: string, c?: Record<string, unknown>) => emit("info", m, c),
  warn: (m: string, c?: Record<string, unknown>) => emit("warn", m, c),
  error: (m: string, c?: Record<string, unknown>) => emit("error", m, c),
};
