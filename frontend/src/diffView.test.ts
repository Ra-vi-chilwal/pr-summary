import { describe, expect, it } from "vitest";
import { parseDiffFiles } from "./diffView";

const DIFF = [
  "diff --git a/src/config.py b/src/config.py",
  "index 1..2 100644",
  "--- a/src/config.py",
  "+++ b/src/config.py",
  "@@ -15,4 +15,5 @@ class Settings:",
  "     SECRET_KEY: str",
  "     DATABASE_URL: str",
  "-    TIMEOUT = 5",
  "+    TIMEOUT = 30",
  "+    RABBITMQ_URL: str",
  "     ALGORITHM = 'HS256'",
  "diff --git a/logo.png b/logo.png",
  "Binary files a/logo.png and b/logo.png differ",
  "diff --git a/new.txt b/new.txt",
  "new file mode 100644",
  "--- /dev/null",
  "+++ b/new.txt",
  "@@ -0,0 +1 @@",
  "+hello",
  "\\ No newline at end of file",
  "",
].join("\n");

describe("parseDiffFiles", () => {
  const [config, logo, created] = parseDiffFiles(DIFF);

  it("finds each file with counts", () => {
    expect([config.path, logo.path, created.path]).toEqual(["src/config.py", "logo.png", "new.txt"]);
    expect([config.deletions, config.additions]).toEqual([1, 2]);
    expect(logo.binary).toBe(true);
    expect(created.rows).toHaveLength(2); // hunk + one added line, no "\ No newline" row
  });

  it("pairs deletions with additions side by side, using real line numbers", () => {
    const rows = config.rows;
    expect(rows[0]).toEqual({ kind: "hunk", text: "@@ -15,4 +15,5 @@ class Settings:" });
    expect(rows[1]).toEqual({
      kind: "ctx",
      left: { n: 15, text: "    SECRET_KEY: str" },
      right: { n: 15, text: "    SECRET_KEY: str" },
    });
    expect(rows[3]).toEqual({
      kind: "chg",
      left: { n: 17, text: "    TIMEOUT = 5" },
      right: { n: 17, text: "    TIMEOUT = 30" },
    });
    expect(rows[4]).toEqual({ kind: "chg", left: null, right: { n: 18, text: "    RABBITMQ_URL: str" } });
    expect(rows[5]).toMatchObject({ kind: "ctx", left: { n: 18 }, right: { n: 19 } });
    expect(rows).toHaveLength(6);
  });

  it("returns nothing for text that is not a diff", () => {
    expect(parseDiffFiles("hello")).toEqual([]);
  });
});
