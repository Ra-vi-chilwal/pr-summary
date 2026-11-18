/** Turn a unified git diff into side-by-side rows (GitHub "split" view). Browser only. */

export interface Side {
  n: number;
  text: string;
}

export type Row =
  | { kind: "hunk"; text: string }
  | { kind: "ctx"; left: Side; right: Side }
  | { kind: "chg"; left: Side | null; right: Side | null };

export interface DiffFile {
  path: string;
  additions: number;
  deletions: number;
  binary: boolean;
  rows: Row[];
}

const HEADER = /^diff --git a\/(.+) b\/(.+)$/;
const HUNK = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(.*)$/;

export function parseDiffFiles(text: string): DiffFile[] {
  const files: DiffFile[] = [];
  let file: DiffFile | null = null;
  let inHunk = false;
  let oldN = 0;
  let newN = 0;
  let dels: Side[] = [];
  let adds: Side[] = [];

  const flush = () => {
    if (!file) return;
    for (let i = 0; i < Math.max(dels.length, adds.length); i++) {
      file.rows.push({ kind: "chg", left: dels[i] ?? null, right: adds[i] ?? null });
    }
    dels = [];
    adds = [];
  };

  for (const line of text.split(/\r?\n/)) {
    const header = HEADER.exec(line);
    if (header) {
      flush();
      file = { path: header[2], additions: 0, deletions: 0, binary: false, rows: [] };
      files.push(file);
      inHunk = false;
      continue;
    }
    if (!file) continue;

    const hunk = HUNK.exec(line);
    if (hunk) {
      flush();
      inHunk = true;
      oldN = Number(hunk[1]);
      newN = Number(hunk[2]);
      file.rows.push({ kind: "hunk", text: line });
      continue;
    }

    if (!inHunk) {
      if (line.startsWith("+++ ") && line.slice(4).trim() !== "/dev/null") {
        file.path = line.slice(4).trim().replace(/^b\//, "");
      } else if (line.startsWith("rename to ")) {
        file.path = line.slice("rename to ".length);
      } else if (line.startsWith("Binary files ") || line === "GIT binary patch") {
        file.binary = true;
      }
      continue;
    }

    if (line.startsWith("-")) {
      dels.push({ n: oldN++, text: line.slice(1) });
      file.deletions++;
    } else if (line.startsWith("+")) {
      adds.push({ n: newN++, text: line.slice(1) });
      file.additions++;
    } else if (line.startsWith(" ") || line === "") {
      flush();
      const content = line.slice(1);
      file.rows.push({ kind: "ctx", left: { n: oldN++, text: content }, right: { n: newN++, text: content } });
    }
    // "\ No newline at end of file" and anything else is ignored.
  }
  flush();
  // A trailing empty line from the final newline is not real context.
  for (const f of files) {
    const last = f.rows[f.rows.length - 1];
    if (last && last.kind === "ctx" && last.left.text === "" && last.right.text === "") f.rows.pop();
  }
  return files;
}
