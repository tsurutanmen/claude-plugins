#!/usr/bin/env python3
"""commit-coach: before a git command that throws work away, say what it would
throw away, in plain words, and ask.

PreToolUse hook for Bash. It dry-runs the git command against the repository
(git status, git clean -n, rev-list against the remote-tracking branch) and stays
silent when nothing would be lost. Standard library only.

  COMMIT_COACH_MODE=ask|deny   ask (default) or refuse outright
  COMMIT_COACH_LANG=en|ja      message language (default: from LANG, else en)
"""
import json
import os
import re
import shlex
import subprocess
import sys

MAX_LIST = 8


def read_stdin():
    """Claude Code sends UTF-8. On Windows, sys.stdin would decode it with the
    ANSI code page (CP932 on Japanese systems), so read the bytes ourselves."""
    data = sys.stdin.buffer.read()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode(sys.stdin.encoding or "utf-8", errors="replace")

TEXT = {
    "en": {
        "reset_files": "`git reset --hard` throws away uncommitted changes. These would be gone, and git cannot bring them back:\n{files}",
        "reset_commits": "It also moves the branch back {n} commit{s} ({items}). Those stay reachable for a while through `git reflog`, but they leave the branch.",
        "reset_safer": "Safer: `git stash` first (you can `git stash pop` later), or `git reset --keep`.",
        "clean": "`git clean` deletes files git is not tracking. These {n} file{s} would be deleted, not moved to the trash:\n{items}",
        "clean_safer": "Safer: look first with `git clean -n`, or move what you want to keep.",
        "discard": "This overwrites your uncommitted changes in these files with the last committed version. git cannot bring them back:\n{items}",
        "discard_safer": "Safer: `git stash` first, or `git diff` to see what you would lose.",
        "push": "Force-pushing replaces the branch on `{ref}`. {n} commit{s} there {are} not in your branch and would be dropped from it (as of your last fetch):\n{items}",
        "push_safer": "Safer: `git pull --rebase` to include them, or `git push --force-with-lease`, which refuses if the remote changed since you last looked.",
        "amend": "The commit you would amend is already pushed to `{ref}`. Amending makes a new commit, so the next push needs force and rewrites what others may have pulled.",
        "amend_safer": "Safer: make a new commit with the fix instead.",
        "branch": "`git branch -D {name}` deletes a branch whose {n} commit{s} {are} on no other branch:\n{items}",
        "branch_safer": "Safer: `git branch -d {name}` refuses when work would be lost; or merge it first.",
        "stash": "`git stash {what}` deletes {n} saved stash entr{y}:\n{items}",
        "stash_safer": "Safer: `git stash list` and `git stash show -p` to check what is in them first.",
        "more": "... and {n} more",
        "head": "commit-coach",
    },
    "ja": {
        "reset_files": "`git reset --hard` はコミットしていない変更を捨てます。次の変更が消え、git では戻せません：\n{files}",
        "reset_commits": "さらにブランチを {n} コミット戻します（{items}）。しばらくは `git reflog` からたどれますが、ブランチからは外れます。",
        "reset_safer": "安全な方法：先に `git stash`（あとで `git stash pop` で戻せる）、または `git reset --keep`。",
        "clean": "`git clean` は git が管理していないファイルを削除します。次の {n} 個はごみ箱にも入らず消えます：\n{items}",
        "clean_safer": "安全な方法：まず `git clean -n` で確かめる。残したいものは移しておく。",
        "discard": "このファイルのコミットしていない変更を、最後にコミットした内容で上書きします。git では戻せません：\n{items}",
        "discard_safer": "安全な方法：先に `git stash`、または `git diff` で消えるものを確かめる。",
        "push": "強制 push は `{ref}` のブランチを置き換えます。そこにあって手元に無い {n} コミットがブランチから消えます（最後に fetch した時点）：\n{items}",
        "push_safer": "安全な方法：`git pull --rebase` で取り込む。または `git push --force-with-lease`（見たあとでリモートが変わっていたら止まる）。",
        "amend": "直そうとしているコミットは、もう `{ref}` に push 済みです。amend すると別のコミットになるので、次の push に強制が要り、ほかの人が取り込んだ内容を書き換えます。",
        "amend_safer": "安全な方法：直した内容を新しいコミットにする。",
        "branch": "`git branch -D {name}` は、ほかのどのブランチにも無い {n} コミットごとブランチを消します：\n{items}",
        "branch_safer": "安全な方法：`git branch -d {name}`（作業が消えるときは止まる）、または先にマージする。",
        "stash": "`git stash {what}` は保存した stash を {n} 件消します：\n{items}",
        "stash_safer": "安全な方法：先に `git stash list` と `git stash show -p` で中身を確かめる。",
        "more": "…ほか {n} 件",
        "head": "commit-coach",
    },
}


def lang():
    v = os.environ.get("COMMIT_COACH_LANG") or os.environ.get("LANG", "")
    return "ja" if v.lower().startswith("ja") else "en"


def t(key, **kw):
    n = kw.get("n")
    kw.setdefault("s", "" if n == 1 else "s")
    kw.setdefault("are", "is" if n == 1 else "are")
    kw.setdefault("y", "y" if n == 1 else "ies")
    return TEXT[lang()][key].format(**kw)


def bullet(items):
    shown = [f"  - {x}" for x in items[:MAX_LIST]]
    if len(items) > MAX_LIST:
        shown.append("  " + t("more", n=len(items) - MAX_LIST))
    return "\n".join(shown)


# --- git -----------------------------------------------------------------------
def run_git(cwd, *args):
    r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=10)
    return r.stdout if r.returncode == 0 else None


def lines(out):
    return [l for l in (out or "").splitlines() if l.strip()]


def changed_files(cwd, paths=None):
    out = run_git(cwd, "status", "--porcelain", "--untracked-files=no", "--", *(paths or []))
    return [l[3:] for l in lines(out)]


def commit_subjects(cwd, rev_range):
    return lines(run_git(cwd, "log", "--format=%h %s", rev_range))


# --- the command line ----------------------------------------------------------
SEPARATORS = re.compile(r"&&|\|\||[;|\n]")


def git_invocations(command):
    """Yield argument lists (after 'git') for each git command in the line."""
    for segment in SEPARATORS.split(command):
        try:
            words = shlex.split(segment, posix=True)
        except ValueError:
            continue
        while words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):
            words = words[1:]  # FOO=bar git ...
        if not words or os.path.basename(words[0]).lower() not in ("git", "git.exe"):
            continue
        yield words[1:]


def split_globals(args, cwd):
    """Handle git's own options before the subcommand: -C path, -c k=v."""
    i = 0
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C" and i + 1 < len(args):
            cwd = os.path.join(cwd, args[i + 1])
            i += 2
        elif args[i] in ("-c", "--git-dir", "--work-tree", "--namespace") and i + 1 < len(args):
            i += 2
        else:
            i += 1
    return (args[i], args[i + 1:], cwd) if i < len(args) else (None, [], cwd)


# --- checks: each returns a message or None ------------------------------------
def check_reset(cwd, args):
    if "--hard" not in args:
        return None
    parts = []
    files = changed_files(cwd)
    if files:
        parts.append(t("reset_files", files=bullet(files)))
    target = next((a for a in args if not a.startswith("-")), None)
    if target:
        dropped = commit_subjects(cwd, f"{target}..HEAD")
        if dropped:
            parts.append(t("reset_commits", n=len(dropped), items="; ".join(dropped[:3])))
    if not parts:
        return None
    return "\n\n".join(parts + [t("reset_safer")])


def check_clean(cwd, args):
    flags = "".join(a[1:] for a in args if a.startswith("-") and not a.startswith("--"))
    if "n" in flags or "--dry-run" in args or not ("f" in flags or "--force" in args):
        return None
    dry = ["clean", "-n"] + [f"-{c}" for c in "dxX" if c in flags]
    doomed = [l.replace("Would remove ", "", 1) for l in lines(run_git(cwd, *dry))]
    if not doomed:
        return None
    return t("clean", n=len(doomed), items=bullet(doomed)) + "\n\n" + t("clean_safer")


def check_discard(cwd, sub, args):
    if sub == "checkout":
        if "--" not in args and args != ["."]:
            return None
        paths = args[args.index("--") + 1:] if "--" in args else ["."]
    else:  # restore
        if ("--staged" in args or "-S" in args) and not ("--worktree" in args or "-W" in args):
            return None
        paths = [a for a in args if not a.startswith("-")]
    hit = lines(run_git(cwd, "diff", "--name-only", "--", *(paths or ["."])))
    if not hit:
        return None
    return t("discard", items=bullet(hit)) + "\n\n" + t("discard_safer")


def check_push(cwd, args):
    forced = any(a in ("--force", "-f") or (a.startswith("-") and not a.startswith("--") and "f" in a[1:])
                 for a in args) or any(a.startswith("+") for a in args)
    if not forced:
        return None
    positional = [a for a in args if not a.startswith("-")]
    if len(positional) >= 2:
        remote, branch = positional[0], positional[1].lstrip("+").split(":")[-1]
        ref = f"{remote}/{branch}"
    else:
        ref = (run_git(cwd, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}") or "").strip()
    if not ref or run_git(cwd, "rev-parse", "--verify", "--quiet", ref) is None:
        return None
    lost = commit_subjects(cwd, f"HEAD..{ref}")
    if not lost:
        return None
    return t("push", ref=ref, n=len(lost), items=bullet(lost)) + "\n\n" + t("push_safer")


def check_commit(cwd, args):
    if "--amend" not in args:
        return None
    ref = (run_git(cwd, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}") or "").strip()
    if not ref:
        return None
    r = subprocess.run(["git", "merge-base", "--is-ancestor", "HEAD", ref], cwd=cwd,
                       capture_output=True, timeout=10)
    if r.returncode != 0:
        return None
    return t("amend", ref=ref) + "\n\n" + t("amend_safer")


def check_branch(cwd, args):
    forced = "-D" in args or (
        any(a in ("-d", "--delete") for a in args) and any(a in ("-f", "--force") for a in args))
    if not forced:
        return None
    parts = []
    for name in (a for a in args if not a.startswith("-")):
        others = [r for r in lines(run_git(cwd, "for-each-ref", "--format=%(refname)",
                                           "refs/heads", "refs/remotes"))
                  if r != f"refs/heads/{name}"]
        only_here = lines(run_git(cwd, "log", "--format=%h %s", name, "--not", *others))
        if only_here:
            parts.append(t("branch", name=name, n=len(only_here), items=bullet(only_here))
                         + "\n\n" + t("branch_safer", name=name))
    return "\n\n".join(parts) or None


def check_stash(cwd, args):
    if not args or args[0] not in ("clear", "drop"):
        return None
    entries = lines(run_git(cwd, "stash", "list"))
    if not entries:
        return None
    if args[0] == "drop":
        target = next((a for a in args[1:] if not a.startswith("-")), "stash@{0}")
        entries = [e for e in entries if e.startswith(target + ":")] or entries[:1]
    return t("stash", what=args[0], n=len(entries), items=bullet(entries)) + "\n\n" + t("stash_safer")


def assess(command, cwd):
    messages = []
    for args in git_invocations(command):
        sub, rest, where = split_globals(args, cwd)
        if not sub or run_git(where, "rev-parse", "--git-dir") is None:
            continue
        check = {
            "reset": lambda: check_reset(where, rest),
            "clean": lambda: check_clean(where, rest),
            "checkout": lambda: check_discard(where, "checkout", rest),
            "restore": lambda: check_discard(where, "restore", rest),
            "push": lambda: check_push(where, rest),
            "commit": lambda: check_commit(where, rest),
            "branch": lambda: check_branch(where, rest),
            "stash": lambda: check_stash(where, rest),
        }.get(sub)
        msg = check() if check else None
        if msg:
            messages.append(msg)
    return messages


def main():
    try:
        payload = json.loads(read_stdin() or "{}")
        if payload.get("tool_name") != "Bash":
            return 0
        command = (payload.get("tool_input") or {}).get("command") or ""
        cwd = payload.get("cwd") or os.getcwd()
        messages = assess(command, cwd)
        if not messages:
            return 0
        mode = "deny" if os.environ.get("COMMIT_COACH_MODE") == "deny" else "ask"
        reason = f"{t('head')}:\n\n" + "\n\n".join(messages)
        out = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                      "permissionDecision": mode,
                                      "permissionDecisionReason": reason}}
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
    except Exception as e:  # never get in the way because of our own failure
        print(f"commit-coach: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
