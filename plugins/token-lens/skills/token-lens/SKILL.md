---
name: token-lens
description: Set up or explain the token-lens status line, a cat that runs as fast as the session spends and warns when the five-hour limit will fill before it resets. Use when the user asks to install or turn on token-lens, asks why the cat is running or what "full in" means, or asks how fast they are using their limit.
---

# token-lens

Two parts:

- **Status line.** `scripts/tokenlens.py statusline` prints a cat on a track. It
  sleeps when nothing is being spent, then walks, runs and sprints. The pace comes
  from the five-hour rate limit when Claude Code reports it (Pro and Max plans),
  measured over the last 30 minutes; otherwise from the session's estimated cost,
  measured over the last 5 minutes. If the five-hour window would fill before it
  resets at the current pace, the line adds `full in 1h40m`.
- **Prompt cache.** From Claude Code's own `prompt_cache` statistics: a countdown
  in the last two minutes before the cache goes cold, how many tokens the next
  reply will re-cache once it is cold, and a new cache miss with its cause for one
  minute. If the user asks whether to reply now or later, this is the number to
  point at: after the cache goes cold, the next reply pays to write it again.
- **Hook** (installed with the plugin). Before Read opens a text file of about
  25,000 tokens or more without `offset`/`limit`, it asks first and says the
  estimate. Change the threshold with the `TOKEN_LENS_READ_TOKENS` environment
  variable. Images and PDFs are left alone.

## Turning on the status line

A plugin cannot set the status line itself, so this is done once in the user's
settings. Ask before editing them.

1. Copy `scripts/tokenlens.py` from this skill's directory to
   `~/.claude/token-lens/tokenlens.py`, so plugin updates do not move the path.
2. In `~/.claude/settings.json`, set:

   ```json
   "statusLine": {
     "type": "command",
     "command": "python3 ~/.claude/token-lens/tokenlens.py statusline",
     "refreshInterval": 1
   }
   ```

   On Windows use `python` and the full path. `refreshInterval: 1` is what makes
   the cat move between events. If the user already has a status line, show them
   what it is and ask before replacing it.
3. Tell the user the cat appears on the next update.

## Reading it

| Cat | Five-hour pace | Session cost pace |
|---|---|---|
| sleeping `zZ` | under 0.5 %/h | under $0.01/min |
| walking | under 10 %/h | under $0.20/min |
| running | under 25 %/h | under $1/min |
| sprinting | 25 %/h or more | $1/min or more |

At 25 %/h a fresh five-hour window is empty in four hours. The cost figure is
Claude Code's own estimate at list price, not a bill.
