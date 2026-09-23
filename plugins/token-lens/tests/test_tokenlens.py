"""Tests for tokenlens. Run: python -m unittest discover -s plugins/token-lens/tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "token-lens" / "scripts" / "tokenlens.py"
T0 = 1_800_000_000.0


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cmd(self, args, stdin, now=T0, extra_env=None):
        env = {**os.environ, "TOKEN_LENS_STATE_DIR": str(self.state),
               "TOKEN_LENS_NOW": str(now), "TOKEN_LENS_DEBUG": "1", "NO_COLOR": "1"}
        env.update(extra_env or {})
        return subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin,
                              capture_output=True, text=True, encoding="utf-8", env=env)

    def line(self, now, cost=None, five=None, resets=None, session="s1"):
        data = {"session_id": session, "model": {"display_name": "Opus"}}
        if cost is not None:
            data["cost"] = {"total_cost_usd": cost}
        if five is not None:
            data["rate_limits"] = {"five_hour": {"used_percentage": five,
                                                 "resets_at": resets or now + 4 * 3600}}
        r = self.run_cmd(["statusline"], json.dumps(data), now=now)
        self.assertEqual(r.returncode, 0, r.stderr)
        debug = json.loads(r.stderr.strip().splitlines()[-1])
        return r.stdout, debug


class Statusline(Base):
    def test_first_call_sleeps(self):
        out, d = self.line(T0, cost=0.5)
        self.assertEqual(d["tier"], "sleep")
        self.assertIn("ᓚᘏᗢ", out)

    def test_no_spending_is_sleep(self):
        self.line(T0, cost=1.0)
        _, d = self.line(T0 + 120, cost=1.0)
        self.assertEqual(d["tier"], "sleep")

    def test_cost_rate_sets_tier(self):
        # $/min thresholds: walk < 0.2 <= run < 1.0 <= sprint
        for per_min, tier in [(0.05, "walk"), (0.5, "run"), (2.0, "sprint")]:
            with self.subTest(tier=tier):
                s = f"cost-{tier}"
                self.line(T0, cost=1.0, session=s)
                _, d = self.line(T0 + 120, cost=1.0 + 2 * per_min, session=s)
                self.assertEqual(d["tier"], tier)

    def test_sessions_do_not_share_state(self):
        self.line(T0, cost=1.0, session="a")
        _, d = self.line(T0 + 120, cost=9.0, session="b")
        self.assertEqual(d["tier"], "sleep")

    def test_old_samples_are_forgotten(self):
        # spending an hour ago says nothing about now
        self.line(T0, cost=1.0)
        self.line(T0 + 60, cost=5.0)
        _, d = self.line(T0 + 3600, cost=5.0)
        self.assertEqual(d["tier"], "sleep")

    def test_cost_pace_uses_last_five_minutes(self):
        # a burst ten minutes ago is outside the cost window
        self.line(T0, cost=1.0)
        self.line(T0 + 60, cost=5.0)
        _, d = self.line(T0 + 600, cost=5.0)
        self.assertEqual(d["tier"], "sleep")

    def test_cat_moves_faster_when_sprinting(self):
        self.line(T0, cost=1.0, session="w")
        self.line(T0, cost=1.0, session="s")
        _, w1 = self.line(T0 + 120, cost=1.1, session="w")
        _, w2 = self.line(T0 + 121, cost=1.1, session="w")
        _, s1 = self.line(T0 + 120, cost=9.0, session="s")
        _, s2 = self.line(T0 + 121, cost=9.0, session="s")
        width = w1["width"]
        step = lambda a, b: (b["pos"] - a["pos"]) % width
        self.assertGreater(step(s1, s2), step(w1, w2))

    # --- five-hour window --------------------------------------------------
    def test_warns_when_limit_comes_before_reset(self):
        # 40% -> 50% in 20 min = 30%/h; 50 left -> 1h40m; reset in 4h
        resets = T0 + 4 * 3600
        self.line(T0, five=40, resets=resets)
        out, d = self.line(T0 + 1200, five=50, resets=resets)
        self.assertEqual(d["full_in_s"], 6000)
        self.assertIn("1h40m", out)

    def test_no_warning_when_reset_comes_first(self):
        resets = T0 + 3600
        self.line(T0, five=40, resets=resets)
        out, d = self.line(T0 + 1200, five=42, resets=resets)
        self.assertIsNone(d["full_in_s"])
        self.assertIn("42%", out)
        self.assertNotIn("full in", out)

    def test_five_hour_rate_drives_tier_when_present(self):
        resets = T0 + 4 * 3600
        self.line(T0, cost=1.0, five=10, resets=resets)
        _, d = self.line(T0 + 600, cost=1.0, five=20, resets=resets)  # 60%/h
        self.assertEqual(d["tier"], "sprint")

    # --- robustness ----------------------------------------------------------
    def test_missing_fields(self):
        out, d = self.line(T0)
        self.assertEqual(d["tier"], "sleep")
        self.assertTrue(out.strip())

    def test_bad_input_prints_something(self):
        r = self.run_cmd(["statusline"], "{nope")
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.stdout.strip())


class PreToolUse(Base):
    def hook(self, tool, tool_input, threshold=None):
        env = {"TOKEN_LENS_READ_TOKENS": str(threshold)} if threshold else None
        payload = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}
        r = self.run_cmd(["pretool"], json.dumps(payload), extra_env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout) if r.stdout.strip() else None

    def make(self, n_bytes):
        p = self.state / f"f{n_bytes}.txt"
        p.write_text("x" * n_bytes, encoding="utf-8")
        return str(p)

    def test_big_read_asks_with_estimate(self):
        out = self.hook("Read", {"file_path": self.make(400_000)}, threshold=50_000)
        hso = out["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "ask")
        self.assertIn("100,000", hso["permissionDecisionReason"])  # 400k bytes / 4

    def test_small_read_is_silent(self):
        self.assertIsNone(self.hook("Read", {"file_path": self.make(1000)}, threshold=50_000))

    def test_read_with_limit_is_silent(self):
        self.assertIsNone(self.hook("Read", {"file_path": self.make(400_000), "limit": 100},
                                    threshold=50_000))

    def test_images_and_pdfs_are_silent(self):
        p = self.state / "big.png"
        p.write_bytes(b"x" * 400_000)
        self.assertIsNone(self.hook("Read", {"file_path": str(p)}, threshold=50_000))

    def test_other_tools_are_silent(self):
        self.assertIsNone(self.hook("Bash", {"command": "cat big.txt"}))

    def test_missing_file_is_silent(self):
        self.assertIsNone(self.hook("Read", {"file_path": str(self.state / "nope.txt")}))

    def test_bad_input_never_blocks(self):
        r = self.run_cmd(["pretool"], "{nope")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
