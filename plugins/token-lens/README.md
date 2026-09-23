# token-lens

A cat in the Claude Code status line that runs as fast as you spend.

```
ᓚᘏᗢ·········· zZ  Opus 5.5  5h 40%  cache cools in 1m40s
····ᓚᘏᗢ······  Opus 5.5  5h 50% · full in 1h40m
ᓚᘏᗢ·········· zZ  Opus 5.5  5h 51%  cache cold: next reply re-caches 120k
```

```
/plugin marketplace add tsurutanmen/claude-plugins
/plugin install token-lens@tsurutalab
```

Then ask Claude to turn on the token-lens status line (a plugin cannot set the status line
itself; the skill edits your settings after asking).

## What it does

- **The cat.** It sleeps when nothing is being spent, then walks, runs and sprints. On Pro and Max
  the pace is the five-hour rate limit's percentage per hour over the last 30 minutes. Otherwise it
  is the session's estimated cost per minute over the last 5 minutes.
- **`full in 1h40m`.** Shown only when the five-hour window would fill before it resets at the
  current pace, so you see it while there is still time to slow down.
- **The prompt cache.** From the `prompt_cache` object Claude Code sends to the status line
  (v2.1.251 or later): `cache cools in 1m40s` in the last two minutes before the cached prefix
  expires, `cache cold: next reply re-caches 120k` once it has, and `cache miss (<cause>)` for a
  minute after Claude Code records a new miss. The numbers are Claude Code's; token-lens only
  decides when to show them.
- **Large reads.** A `PreToolUse` hook asks before Read opens a text file of about 25,000 tokens
  or more whole (bytes ÷ 4), and suggests `offset`/`limit` or Grep. Set `TOKEN_LENS_READ_TOKENS`
  to change the threshold.

## What it does not do

- It does not count tokens itself. It reads what Claude Code puts in the status line JSON.
- The pace is a straight line through recent samples. A burst that stops will keep the cat running
  until it leaves the window.
- The token estimate for a read is bytes ÷ 4. Code with long identifiers or non-English text will
  differ.

## Tests

```
python -m unittest discover -s plugins/token-lens/tests
```

Standard library only. MIT.
