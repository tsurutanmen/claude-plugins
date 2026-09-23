# commit-coach

Before a git command throws work away, commit-coach dry-runs it, says exactly what would be lost,
and asks. When nothing would be lost, it stays out of the way.

```
/plugin marketplace add tsurutanmen/claude-plugins
/plugin install commit-coach@tsurutalab
```

```
commit-coach:

`git reset --hard` throws away uncommitted changes. These would be gone, and git cannot bring them back:
  - app.py
  - config.yml

Safer: `git stash` first (you can `git stash pop` later), or `git reset --keep`.
```

## Why not a blocklist

Many git-safety hooks block `git reset --hard` or `git push --force` by pattern. They stop the command every time,
including when it is harmless, and say only that it is not allowed. commit-coach asks git what
the command would do in this repository at this moment:

- `git reset --hard` on a clean tree: nothing to lose, no prompt.
- `git clean -fd` with nothing untracked: no prompt. With files: the list `git clean -n` gives.
- `git push --force` when the remote has nothing you lack: no prompt. When it does: those commits,
  by subject, and `--force-with-lease` as the safer command.
- `git branch -D` on a branch whose commits are elsewhere: no prompt.

Also checked: `git checkout -- <paths>` / `git restore`, `git commit --amend` on a pushed commit,
`git stash clear` / `drop`. See the [skill](skills/commit-coach/SKILL.md) for the full table.

## Settings

- `COMMIT_COACH_MODE=deny` refuses instead of asking.
- `COMMIT_COACH_LANG=ja` for Japanese messages (also follows `LANG`).

## Limits

- It reads the Bash command line. Git run from inside another program is not seen.
- Force-push checks use the remote-tracking branch as of the last fetch.

## Tests

```
python -m unittest discover -s plugins/commit-coach/tests
```

Each test builds real repositories (including a bare remote and a second clone for force-push
cases). Standard library only. MIT.
