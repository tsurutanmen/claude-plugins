#!/usr/bin/env python3
"""token-lens: a cat in the Claude Code status line that runs as fast as you spend.

  tokenlens.py statusline   status line command: reads the status JSON on stdin
  tokenlens.py pretool      PreToolUse hook: asks before reading a very large file whole

The cat sleeps when nothing is being spent, then walks, runs and sprints. The pace
comes from the five-hour rate limit when Claude Code reports it (Pro and Max),
otherwise from the session's estimated cost. When the five-hour window would
fill up before it resets at the current pace, the line says when.

Standard library only. State is a small JSON file per session in the temp dir.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

CAT = "ᓚᘏᗢ"
WIDTH = 10
COST_WINDOW_S = 300     # cost pace: last five minutes
FIVE_WINDOW_S = 1800    # five-hour pace: last 30 minutes (the percentage moves slowly)
MIN_SPAN_S = 20         # need this much history before judging the pace
TIERS = ["sleep", "walk", "run", "sprint"]
SPEED = {"sleep": 0, "walk": 0.5, "run": 1, "sprint": 2}  # cells per second
COST_PER_MIN = [0.01, 0.2, 1.0]    # $/min at which walk, run, sprint begin
FIVE_PER_HOUR = [0.5, 10, 25]      # five-hour %/h at which walk, run, sprint begin
COLOR = {"sleep": "2", "walk": "32", "run": "33", "sprint": "31"}
COOLING_S = 120        # warn when the prompt cache goes cold within this many seconds
MISS_SHOW_S = 60       # how long a new cache miss stays on the line
DEFAULT_READ_TOKENS = 25_000
BYTES_PER_TOKEN = 4
NOT_TEXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".pdf"}  # Read sizes these its own way


def now():
    return float(os.environ.get("TOKEN_LENS_NOW") or time.time())


def state_file(session):
    base = Path(os.environ.get("TOKEN_LENS_STATE_DIR") or Path(tempfile.gettempdir()) / "token-lens")
    base.mkdir(parents=True, exist_ok=True)
    safe = "".join(c for c in str(session) if c.isalnum() or c in "-_") or "default"
    return base / f"{safe}.json"


def tier_for(value, cuts):
    return TIERS[sum(value >= c for c in cuts)]


def fmt_duration(s):
    s = int(s)
    h, m = divmod(s // 60, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m"


def analyse(data, t):
    """Update the session's samples and work out tier, pace and time to full."""
    cost = (data.get("cost") or {}).get("total_cost_usd")
    five = ((data.get("rate_limits") or {}).get("five_hour") or {})
    pct, resets = five.get("used_percentage"), five.get("resets_at")

    path = state_file(data.get("session_id") or "default")
    try:
        samples = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        samples = []
    samples = [s for s in samples if t - s["t"] <= FIVE_WINDOW_S and s["t"] <= t]
    samples.append({"t": t, "cost": cost, "five": pct})
    try:
        path.write_text(json.dumps(samples[-200:]), encoding="utf-8")
    except OSError:
        pass

    tier, full_in = "sleep", None
    five_first = next((s for s in samples if s["five"] is not None), None)
    cost_first = next((s for s in samples if s["cost"] is not None
                       and t - s["t"] <= COST_WINDOW_S), None)
    if pct is not None and five_first and t - five_first["t"] >= MIN_SPAN_S:
        per_s = (pct - five_first["five"]) / (t - five_first["t"])
        tier = tier_for(per_s * 3600, FIVE_PER_HOUR)
        if per_s > 0 and resets:
            eta = (100 - pct) / per_s
            if t + eta < resets:
                full_in = round(eta)
    elif cost is not None and cost_first and t - cost_first["t"] >= MIN_SPAN_S:
        tier = tier_for((cost - cost_first["cost"]) / (t - cost_first["t"]) * 60, COST_PER_MIN)

    pos = int(t * SPEED[tier]) % WIDTH
    return {"tier": tier, "pos": pos, "width": WIDTH, "full_in_s": full_in,
            "five": pct, "cost": cost, **cache_state(data, t, path)}


def cache_state(data, t, path):
    """What to say about the prompt cache, from the prompt_cache object Claude Code sends."""
    pc = data.get("prompt_cache") or {}
    side = path.with_suffix(".cache.json")
    try:
        prev = json.loads(side.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prev = {}
    misses = pc.get("misses") or 0
    miss_at, cause = prev.get("miss_at"), prev.get("cause")
    if "misses" in prev and misses > prev["misses"]:
        miss_at, cause = t, pc.get("last_miss_cause")
    try:
        side.write_text(json.dumps({"misses": misses, "miss_at": miss_at, "cause": cause}),
                        encoding="utf-8")
    except OSError:
        pass
    out = {"cache": None, "cache_left_s": None, "recache": pc.get("recache_tokens_if_cold")}
    if miss_at is not None and t - miss_at <= MISS_SHOW_S:
        out.update(cache="miss", cause=cause)
    elif not pc.get("warm"):
        out["cache"] = "cold" if out["recache"] else None
    elif pc.get("expires_at") and 0 < pc["expires_at"] - t <= COOLING_S:
        out.update(cache="cooling", cache_left_s=pc["expires_at"] - t)
    return out


def fmt_tokens(n):
    return f"{n / 1000:.0f}k" if n >= 1000 else str(n)


def render(a, data):
    track = ["·"] * WIDTH
    body = "".join(track[:a["pos"]]) + CAT + "".join(track[a["pos"]:])
    if a["tier"] == "sleep":
        body += " zZ"
    if not os.environ.get("NO_COLOR"):
        body = f"\033[{COLOR[a['tier']]}m{body}\033[0m"
    parts = [body]
    model = (data.get("model") or {}).get("display_name")
    if model:
        parts.append(model)
    if a["five"] is not None:
        five = f"5h {a['five']:.0f}%"
        if a["full_in_s"] is not None:
            five += f" · full in {fmt_duration(a['full_in_s'])}"
        parts.append(five)
    elif a["cost"] is not None:
        parts.append(f"${a['cost']:.2f}")
    if a.get("cache") == "miss":
        parts.append(f"cache miss ({a.get('cause') or 'cause unknown'})")
    elif a.get("cache") == "cooling":
        parts.append(f"cache cools in {fmt_seconds(a['cache_left_s'])}")
    elif a.get("cache") == "cold":
        parts.append(f"cache cold: next reply re-caches {fmt_tokens(a['recache'])}")
    return "  ".join(parts)


def fmt_seconds(s):
    s = int(s)
    return f"{s // 60}m{s % 60:02d}s" if s >= 60 else f"{s}s"


def cmd_statusline():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw or "{}")
        a = analyse(data, now())
        print(render(a, data))
    except Exception as e:  # the status line must always print something
        a = {"tier": "sleep", "pos": 0, "width": WIDTH, "full_in_s": None, "error": str(e)}
        print(CAT + " zZ")
    if os.environ.get("TOKEN_LENS_DEBUG"):
        print(json.dumps(a), file=sys.stderr)
    return 0


def cmd_pretool():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if payload.get("tool_name") != "Read":
            return 0
        ti = payload.get("tool_input") or {}
        if ti.get("limit") or ti.get("offset"):
            return 0
        path = Path(ti.get("file_path") or "")
        if not path.is_file() or path.suffix.lower() in NOT_TEXT:
            return 0
        est = path.stat().st_size // BYTES_PER_TOKEN
        limit = int(os.environ.get("TOKEN_LENS_READ_TOKENS") or DEFAULT_READ_TOKENS)
        if est < limit:
            return 0
        reason = (f"token-lens: {path.name} is about {est:,} tokens "
                  f"(over {limit:,}). Read part of it with offset/limit, or search it with Grep, "
                  "unless the whole file is needed.")
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                 "permissionDecision": "ask",
                                                 "permissionDecisionReason": reason}}))
    except Exception as e:  # never get in the way of the tool call
        print(f"token-lens: {e}", file=sys.stderr)
    return 0


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "statusline":
        return cmd_statusline()
    if cmd == "pretool":
        return cmd_pretool()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
