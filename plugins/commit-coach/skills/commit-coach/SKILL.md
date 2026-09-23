---
name: commit-coach
description: Explain what a git command would throw away before running it, and suggest the safer command. Use when the commit-coach hook asks about a git command, when the user asks whether a git command is safe or what it will do to their work, or before running reset --hard, clean -f, checkout -- / restore, push --force, commit --amend on a pushed commit, branch -D, or stash drop/clear.
---

# commit-coach

The plugin's hook runs before every Bash command. For the git commands below it
dry-runs the command against the repository and, when something would be lost,
asks the user with a plain-words list of exactly what. When nothing would be
lost it says nothing.

| Command | What it checks |
|---|---|
| `git reset --hard [ref]` | uncommitted changes (`git status`), and commits the branch would move back past |
| `git clean -f[d][x]` | the files `git clean -n` with the same flags would remove |
| `git checkout -- <paths>`, `git checkout .`, `git restore <paths>` | files with unstaged changes under those paths |
| `git push --force`, `-f`, `+refspec` | commits on the remote-tracking branch that are not in HEAD (as of the last fetch) |
| `git commit --amend` | whether HEAD is already on the upstream branch |
| `git branch -D <name>` | commits on that branch that no other branch or remote branch has |
| `git stash clear`, `git stash drop` | the stash entries that would be deleted |

## When the hook asks

1. Read the list in the hook's message to the user in plain words: what would be
   lost and whether git can bring it back.
2. If the user did not ask for that loss, use the safer command the message
   names (`git stash`, `git clean -n`, `--force-with-lease`, `git branch -d`, a new
   commit instead of `--amend`) instead of retrying the same command.
3. Never try to get around the hook, for example by splitting the command or
   calling git through another program. The point is that the user sees the list.

## Settings

- `COMMIT_COACH_MODE=deny` refuses instead of asking.
- `COMMIT_COACH_LANG=ja` writes the message in Japanese (it also follows `LANG`).

## Limits

- Only commands that start with `git` in the Bash tool are checked, including
  after `&&`, `;`, `|` and `FOO=bar`. `git -C <path>` is followed. A git command
  inside another program's arguments is not.
- Force-push checks compare with the remote-tracking branch from the last fetch.
  If someone pushed since then, the list can be short. That is also why
  `--force-with-lease` is the safer default.
