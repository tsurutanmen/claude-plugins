"""Tests for kledger. Run: python -m unittest discover -s plugins/knowledge-ledger/tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "knowledge-ledger" / "scripts" / "kledger.py"


def run(root, *args, stdin=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin, capture_output=True, text=True, encoding="utf-8",
        cwd=root, env={**{k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")},
                       "CLAUDE_PROJECT_DIR": str(root)},
    )


def hook(root, tool, tool_input):
    payload = {"hook_event_name": "PostToolUse", "tool_name": tool,
               "tool_input": tool_input, "cwd": str(root), "session_id": "s1"}
    return run(root, "record", stdin=json.dumps(payload, ensure_ascii=False))  # Claude Code sends raw UTF-8


def status(root):
    r = run(root, "status", "--json")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


BODY = "def add(a, b):\n    total = a + b\n    return total\n\n}\n"


class Ledger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.f = self.root / "calc.py"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text):
        self.f.write_text(text, encoding="utf-8")
        return hook(self.root, "Write", {"file_path": str(self.f), "content": text})

    # --- recording -------------------------------------------------------
    def test_write_records_nontrivial_lines_only(self):
        self.assertEqual(self.write(BODY).returncode, 0)
        s = status(self.root)
        # blank line and a lone "}" are not counted
        self.assertEqual(s["ai_lines"], 3)
        self.assertEqual(s["explained"], 0)
        self.assertEqual(s["debt"], 3)

    def test_ledger_is_a_file_in_the_project(self):
        self.write(BODY)
        self.assertTrue((self.root / ".knowledge-ledger" / "ledger.jsonl").exists())

    def test_edit_records_only_new_lines(self):
        self.f.write_text(BODY, encoding="utf-8")  # human-written file, not recorded
        new = BODY.replace("    return total\n", "    log_call(a, b)\n    return total\n")
        self.f.write_text(new, encoding="utf-8")
        hook(self.root, "Edit", {"file_path": str(self.f),
                                 "old_string": "    return total\n",
                                 "new_string": "    log_call(a, b)\n    return total\n"})
        s = status(self.root)
        self.assertEqual(s["ai_lines"], 1)          # only log_call(...)
        self.assertEqual(s["total_lines"], 4)

    def test_multiedit_records_each_edit(self):
        self.f.write_text("alpha_one = 1\nbeta_two = 2\n", encoding="utf-8")
        self.f.write_text("alpha_one = 10\nbeta_two = 20\n", encoding="utf-8")
        hook(self.root, "MultiEdit", {"file_path": str(self.f), "edits": [
            {"old_string": "alpha_one = 1", "new_string": "alpha_one = 10"},
            {"old_string": "beta_two = 2", "new_string": "beta_two = 20"}]})
        self.assertEqual(status(self.root)["ai_lines"], 2)

    def test_other_tools_are_ignored(self):
        r = hook(self.root, "Bash", {"command": "echo hi > calc.py"})
        self.assertEqual(r.returncode, 0)
        self.assertEqual(status(self.root)["ai_lines"], 0)

    def test_bad_hook_input_never_blocks(self):
        r = run(self.root, "record", stdin="{not json")
        self.assertEqual(r.returncode, 0)

    # --- the lines that are still there ---------------------------------
    def test_human_rewrite_removes_line_from_ai_count(self):
        self.write(BODY)
        self.f.write_text(BODY.replace("total = a + b", "total = sum((a, b))"), encoding="utf-8")
        s = status(self.root)
        self.assertEqual(s["ai_lines"], 2)
        self.assertEqual(s["total_lines"], 3)

    def test_deleted_file_drops_out(self):
        self.write(BODY)
        self.f.unlink()
        self.assertEqual(status(self.root)["ai_lines"], 0)

    def test_duplicate_lines_counted_by_multiplicity(self):
        text = "counter += 1\ncounter += 1\n"
        self.write(text)
        self.f.write_text("counter += 1\n", encoding="utf-8")
        self.assertEqual(status(self.root)["ai_lines"], 1)

    # --- explaining ------------------------------------------------------
    def test_short_explanation_is_refused(self):
        self.write(BODY)
        r = run(self.root, "explain", "calc.py", "--lines", "1-3", stdin="adds")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(status(self.root)["explained"], 0)

    def test_explanation_pays_down_debt(self):
        self.write(BODY)
        text = "add takes two numbers, stores their sum in total, and returns it unchanged."
        r = run(self.root, "explain", "calc.py", "--lines", "1-2", stdin=text)
        self.assertEqual(r.returncode, 0, r.stderr)
        s = status(self.root)
        self.assertEqual(s["explained"], 2)
        self.assertEqual(s["debt"], 1)

    def test_explained_line_survives_moving(self):
        self.write(BODY)
        text = "add takes two numbers, stores their sum in total, and returns it unchanged."
        run(self.root, "explain", "calc.py", "--lines", "2-2", stdin=text)
        self.f.write_text("# header comment here\n\n" + BODY, encoding="utf-8")
        self.assertEqual(status(self.root)["explained"], 1)

    def test_explain_outside_ai_lines_counts_nothing(self):
        self.f.write_text(BODY, encoding="utf-8")  # human-written
        text = "add takes two numbers, stores their sum in total, and returns it unchanged."
        run(self.root, "explain", "calc.py", "--lines", "1-3", stdin=text)
        s = status(self.root)
        self.assertEqual((s["ai_lines"], s["explained"]), (0, 0))

    # --- agents without hooks -------------------------------------------
    def test_git_mode_records_added_lines(self):
        g = lambda *a: subprocess.run(["git", *a], cwd=self.root, capture_output=True, check=True)
        g("init", "-q"); g("config", "user.email", "t@t"); g("config", "user.name", "t")
        self.f.write_text("keep_this_line = 1\n", encoding="utf-8")
        g("add", "."); g("commit", "-qm", "base")
        self.f.write_text("keep_this_line = 1\nagent_added_line = 2\n", encoding="utf-8")
        r = run(self.root, "record", "--git")
        self.assertEqual(r.returncode, 0, r.stderr)
        run(self.root, "record", "--git")  # twice must not double-count
        s = status(self.root)
        self.assertEqual((s["ai_lines"], s["total_lines"]), (1, 2))

    def test_japanese_content_is_recorded(self):
        # Claude Code sends UTF-8; on Windows Python would read stdin as CP932
        self.f = self.root / "日本語.py"
        self.write("# 設定ファイル\nname = '日本語のテスト'\nprint('こんにちは')\n")
        s = status(self.root)
        self.assertEqual(s["ai_lines"], 3)
        self.assertEqual(s["files"][0]["file"], "日本語.py")

    def test_japanese_explanation(self):
        self.write(BODY)
        r = run(self.root, "explain", "calc.py", "--lines", "1-2",
                stdin="二つの数を受け取り、その和を total に入れて、そのまま返す関数です。")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(status(self.root)["explained"], 2)

    def test_short_japanese_explanation_is_refused(self):
        self.write(BODY)
        r = run(self.root, "explain", "calc.py", "--lines", "1-2", stdin="足す関数")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(status(self.root)["explained"], 0)

    def test_status_text_mentions_debt(self):
        self.write(BODY)
        r = run(self.root, "status")
        self.assertEqual(r.returncode, 0)
        self.assertIn("calc.py", r.stdout)
        self.assertIn("3", r.stdout)


if __name__ == "__main__":
    unittest.main()
