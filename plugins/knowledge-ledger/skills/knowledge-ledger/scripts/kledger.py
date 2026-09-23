#!/usr/bin/env python3
"""knowledge-ledger: keep a ledger of the lines an AI agent wrote, and which of
them you have explained in your own words.

  kledger record            read a PostToolUse hook payload on stdin (Write/Edit/MultiEdit)
  kledger record --git      record lines added since HEAD (for agents without hooks)
  kledger status [--json]   AI-written lines still in the code, explained vs not
  kledger explain FILE --lines A-B   read your explanation on stdin, mark those lines

Standard library only. The ledger lives in <project>/.knowledge-ledger/ledger.jsonl
and is meant to be committed, so the history of the debt is the git history.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

LEDGER_DIR = ".knowledge-ledger"
MIN_EXPLANATION = 40  # characters


# --- lines ------------------------------------------------------------------
def norm(line):
    return " ".join(line.split())


def trivial(line):
    s = norm(line)
    return len(s) < 4 or not any(c.isalnum() for c in s)


def h(line):
    return hashlib.sha1(norm(line).encode("utf-8")).hexdigest()[:16]


def hashes(text):
    return [h(l) for l in text.splitlines() if not trivial(l)]


# --- project and ledger -----------------------------------------------------
def project_root(cwd=None):
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    start = Path(cwd or os.getcwd()).resolve()
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start,
                             capture_output=True, text=True, check=True).stdout.strip()
        return Path(out).resolve()
    except (OSError, subprocess.CalledProcessError):
        return start


def ledger_path(root):
    return root / LEDGER_DIR / "ledger.jsonl"


def rel(root, file_path):
    p = Path(file_path)
    if not p.is_absolute():
        p = root / p
    try:
        return p.resolve().relative_to(root).as_posix()
    except ValueError:
        return None  # outside the project: not ours to track


def append(root, event):
    path = ledger_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    event.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def events(root):
    path = ledger_path(root)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


# --- record -----------------------------------------------------------------
def added(old, new):
    """Hashes in new that are not accounted for by old (multiset difference)."""
    return list((Counter(hashes(new)) - Counter(hashes(old))).elements())


def from_hook(payload):
    tool = payload.get("tool_name")
    ti = payload.get("tool_input") or {}
    if tool == "Write":
        return ti.get("file_path"), hashes(ti.get("content", ""))
    if tool == "Edit":
        return ti.get("file_path"), added(ti.get("old_string", ""), ti.get("new_string", ""))
    if tool == "MultiEdit":
        hs = []
        for e in ti.get("edits") or []:
            hs += added(e.get("old_string", ""), e.get("new_string", ""))
        return ti.get("file_path"), hs
    return None, []


def cmd_record(args):
    if args.git:
        return record_git()
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        root = project_root(payload.get("cwd"))
        file_path, hs = from_hook(payload)
        r = rel(root, file_path) if file_path else None
        if r and hs and not r.startswith(LEDGER_DIR + "/"):
            append(root, {"t": "ai", "file": r, "h": hs,
                          "tool": payload.get("tool_name"),
                          "session": payload.get("session_id")})
    except Exception as e:  # a ledger must never get in the agent's way
        print(f"knowledge-ledger: not recorded ({e})", file=sys.stderr)
    return 0


def record_git():
    root = project_root()
    diff = subprocess.run(["git", "diff", "HEAD", "--unified=0", "--no-color", "--no-ext-diff"],
                          cwd=root, capture_output=True, text=True, encoding="utf-8")
    if diff.returncode != 0:
        print(diff.stderr.strip(), file=sys.stderr)
        return 1
    per_file, cur = {}, None
    for line in diff.stdout.splitlines():
        if line.startswith("+++ "):
            cur = None if line[4:] == "/dev/null" else line[4:].removeprefix("b/")
        elif line.startswith("+") and cur and not trivial(line[1:]):
            per_file.setdefault(cur, []).append(h(line[1:]))
    for f, hs in per_file.items():
        append(root, {"t": "ai", "file": f, "h": hs, "tool": "git-diff"})
    print(f"recorded {sum(map(len, per_file.values()))} lines in {len(per_file)} files")
    return 0


# --- status -----------------------------------------------------------------
def compute(root):
    ai, explained = {}, {}
    for e in events(root):
        f = e.get("file")
        if e.get("t") == "ai":
            ai.setdefault(f, Counter()).update(e.get("h", []))
        elif e.get("t") == "explained":
            explained.setdefault(f, set()).update(e.get("h", []))
    files = []
    for f, ai_count in sorted(ai.items()):
        p = root / f
        if not p.is_file():
            continue
        try:
            cur = Counter(hashes(p.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
        present = {k: min(v, cur[k]) for k, v in ai_count.items() if cur[k]}
        n_ai = sum(present.values())
        n_exp = sum(v for k, v in present.items() if k in explained.get(f, ()))
        files.append({"file": f, "total_lines": sum(cur.values()), "ai_lines": n_ai,
                      "explained": n_exp, "debt": n_ai - n_exp})
    tot = lambda k: sum(x[k] for x in files)
    return {"total_lines": tot("total_lines"), "ai_lines": tot("ai_lines"),
            "explained": tot("explained"), "debt": tot("debt"), "files": files}


def cmd_status(args):
    s = compute(project_root())
    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return 0
    if not s["files"]:
        print("knowledge-ledger: nothing recorded yet")
        return 0
    share = 100 * s["ai_lines"] / s["total_lines"] if s["total_lines"] else 0
    print(f"AI-written lines still in the code: {s['ai_lines']} of {s['total_lines']} ({share:.0f}%)")
    print(f"explained in your own words: {s['explained']}   unexplained (debt): {s['debt']}")
    print()
    print(f"{'debt':>5} {'AI':>5} {'lines':>6}  file")
    for x in sorted(s["files"], key=lambda x: -x["debt"]):
        if x["ai_lines"]:
            print(f"{x['debt']:>5} {x['ai_lines']:>5} {x['total_lines']:>6}  {x['file']}")
    return 0


# --- explain ----------------------------------------------------------------
def cmd_explain(args):
    root = project_root()
    r = rel(root, args.file)
    if not r or not (root / r).is_file():
        print(f"no such file in this project: {args.file}", file=sys.stderr)
        return 2
    try:
        a, _, b = args.lines.partition("-")
        a, b = int(a), int(b or a)
    except ValueError:
        print("--lines takes A-B, e.g. 10-24", file=sys.stderr)
        return 2
    text = sys.stdin.read().strip()
    if len(text) < MIN_EXPLANATION:
        print(f"explanation too short ({len(text)} chars, need {MIN_EXPLANATION}). "
              "Say what the lines do and why, in your own words.", file=sys.stderr)
        return 1
    lines = (root / r).read_text(encoding="utf-8", errors="replace").splitlines()[a - 1:b]
    hs = [h(l) for l in lines if not trivial(l)]
    append(root, {"t": "explained", "file": r, "lines": [a, b], "h": hs,
                  "text": text, "by": args.by})
    s = compute(root)
    print(f"recorded. debt now {s['debt']} of {s['ai_lines']} AI-written lines")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kledger", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("record"); p.add_argument("--git", action="store_true"); p.set_defaults(fn=cmd_record)
    p = sub.add_parser("status"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_status)
    p = sub.add_parser("explain"); p.add_argument("file"); p.add_argument("--lines", required=True)
    p.add_argument("--by", default="human"); p.set_defaults(fn=cmd_explain)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
