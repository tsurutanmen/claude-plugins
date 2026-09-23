"""Tests for commitcoach. Run: python -m unittest discover -s plugins/commit-coach/tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "commit-coach" / "scripts" / "commitcoach.py"


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def init(path):
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "t@t")
    git(path, "config", "user.name", "t")
    git(path, "config", "commit.gpgsign", "false")
    return path


def commit(repo, name, text, msg=None):
    (repo / name).write_text(text, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-qm", msg or f"add {name}")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = init(self.root / "repo")
        commit(self.repo, "a.txt", "one\n")

    def tearDown(self):
        self.tmp.cleanup()

    def hook(self, command, cwd=None, env=None):
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                   "tool_input": {"command": command}, "cwd": str(cwd or self.repo)}
        r = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(payload),
                           capture_output=True, text=True, encoding="utf-8",
                           env={**os.environ, "COMMIT_COACH_LANG": "en", **(env or {})})
        self.assertEqual(r.returncode, 0, r.stderr)
        if not r.stdout.strip():
            return None
        out = json.loads(r.stdout)["hookSpecificOutput"]
        return out["permissionDecision"], out["permissionDecisionReason"]


class Reset(Base):
    def test_clean_tree_is_silent(self):
        self.assertIsNone(self.hook("git reset --hard"))

    def test_uncommitted_changes_are_named(self):
        (self.repo / "a.txt").write_text("changed\n", encoding="utf-8")
        decision, reason = self.hook("git reset --hard")
        self.assertEqual(decision, "ask")
        self.assertIn("a.txt", reason)
        self.assertIn("git stash", reason)  # a safer way is offered

    def test_moving_back_names_commit_count(self):
        commit(self.repo, "b.txt", "two\n")
        commit(self.repo, "c.txt", "three\n")
        decision, reason = self.hook("git reset --hard HEAD~2")
        self.assertEqual(decision, "ask")
        self.assertIn("2 commits", reason)
        self.assertIn("reflog", reason)

    def test_soft_reset_is_silent(self):
        commit(self.repo, "b.txt", "two\n")
        self.assertIsNone(self.hook("git reset --soft HEAD~1"))


class Clean(Base):
    def test_lists_files_that_would_be_deleted(self):
        (self.repo / "notes.txt").write_text("mine\n", encoding="utf-8")
        decision, reason = self.hook("git clean -fd")
        self.assertEqual(decision, "ask")
        self.assertIn("notes.txt", reason)

    def test_nothing_to_delete_is_silent(self):
        self.assertIsNone(self.hook("git clean -fd"))

    def test_dry_run_is_silent(self):
        (self.repo / "notes.txt").write_text("mine\n", encoding="utf-8")
        self.assertIsNone(self.hook("git clean -n"))
        self.assertIsNone(self.hook("git clean -nfd"))


class Discard(Base):
    def test_checkout_dashdash_names_changed_file(self):
        (self.repo / "a.txt").write_text("changed\n", encoding="utf-8")
        decision, reason = self.hook("git checkout -- a.txt")
        self.assertEqual(decision, "ask")
        self.assertIn("a.txt", reason)

    def test_restore_dot_names_changed_file(self):
        (self.repo / "a.txt").write_text("changed\n", encoding="utf-8")
        decision, reason = self.hook("git restore .")
        self.assertEqual(decision, "ask")
        self.assertIn("a.txt", reason)

    def test_restore_staged_only_is_silent(self):
        (self.repo / "a.txt").write_text("changed\n", encoding="utf-8")
        git(self.repo, "add", "a.txt")
        self.assertIsNone(self.hook("git restore --staged a.txt"))

    def test_checkout_branch_is_silent(self):
        git(self.repo, "branch", "other")
        self.assertIsNone(self.hook("git checkout other"))


class Push(Base):
    def setUp(self):
        super().setUp()
        self.remote = self.root / "remote.git"
        git(self.root, "init", "-q", "--bare", str(self.remote))
        git(self.repo, "remote", "add", "origin", str(self.remote))
        git(self.repo, "push", "-q", "-u", "origin", "main")
        other = self.root / "other"
        git(self.root, "clone", "-q", "-b", "main", str(self.remote), str(other))
        git(other, "config", "user.email", "o@o")
        git(other, "config", "user.name", "o")
        commit(other, "theirs.txt", "theirs\n", "their work")
        git(other, "push", "-q", "origin", "main")
        git(self.repo, "fetch", "-q")
        commit(self.repo, "mine.txt", "mine\n", "my work")

    def test_force_push_names_commits_it_would_overwrite(self):
        decision, reason = self.hook("git push --force")
        self.assertEqual(decision, "ask")
        self.assertIn("1 commit", reason)
        self.assertIn("their work", reason)
        self.assertIn("--force-with-lease", reason)

    def test_short_flag_and_explicit_branch(self):
        decision, _ = self.hook("git push -f origin main")
        self.assertEqual(decision, "ask")

    def test_force_with_lease_is_silent(self):
        self.assertIsNone(self.hook("git push --force-with-lease"))

    def test_plain_push_is_silent(self):
        self.assertIsNone(self.hook("git push"))

    def test_force_push_with_nothing_to_overwrite_is_silent(self):
        git(self.repo, "pull", "-q", "--rebase")
        self.assertIsNone(self.hook("git push --force"))

    def test_amend_of_pushed_commit(self):
        git(self.repo, "reset", "-q", "--hard", "origin/main")
        decision, reason = self.hook("git commit --amend -m x")
        self.assertEqual(decision, "ask")
        self.assertIn("pushed", reason)

    def test_amend_of_local_commit_is_silent(self):
        self.assertIsNone(self.hook("git commit --amend -m x"))


class Branches(Base):
    def test_delete_unmerged_branch_names_commits(self):
        git(self.repo, "checkout", "-q", "-b", "idea")
        commit(self.repo, "idea.txt", "x\n", "half-done idea")
        git(self.repo, "checkout", "-q", "main")
        decision, reason = self.hook("git branch -D idea")
        self.assertEqual(decision, "ask")
        self.assertIn("half-done idea", reason)

    def test_delete_merged_branch_is_silent(self):
        git(self.repo, "branch", "done")
        self.assertIsNone(self.hook("git branch -D done"))

    def test_stash_clear_counts_entries(self):
        for i in range(2):
            (self.repo / "a.txt").write_text(f"v{i}\n", encoding="utf-8")
            git(self.repo, "stash", "-q")
        decision, reason = self.hook("git stash clear")
        self.assertEqual(decision, "ask")
        self.assertIn("2", reason)

    def test_stash_clear_with_no_stash_is_silent(self):
        self.assertIsNone(self.hook("git stash clear"))


class Parsing(Base):
    def dirty(self):
        (self.repo / "a.txt").write_text("changed\n", encoding="utf-8")

    def test_chained_command(self):
        self.dirty()
        decision, _ = self.hook("git status && git reset --hard")
        self.assertEqual(decision, "ask")

    def test_dash_C_uses_that_repo(self):
        self.dirty()
        decision, reason = self.hook(f'git -C "{self.repo}" reset --hard', cwd=self.root)
        self.assertEqual(decision, "ask")
        self.assertIn("a.txt", reason)

    def test_quoted_text_is_not_a_command(self):
        self.dirty()
        self.assertIsNone(self.hook("echo 'git reset --hard'"))

    def test_other_tools_are_silent(self):
        payload = {"tool_name": "Read", "tool_input": {"file_path": "x"}, "cwd": str(self.repo)}
        r = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(payload),
                           capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, ""))

    def test_bad_input_never_blocks(self):
        r = subprocess.run([sys.executable, str(SCRIPT)], input="{nope",
                           capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, ""))

    def test_outside_a_repo_is_silent(self):
        self.assertIsNone(self.hook("git reset --hard", cwd=self.root))

    def test_deny_mode(self):
        self.dirty()
        decision, _ = self.hook("git reset --hard", env={"COMMIT_COACH_MODE": "deny"})
        self.assertEqual(decision, "deny")

    def test_japanese(self):
        self.dirty()
        _, reason = self.hook("git reset --hard", env={"COMMIT_COACH_LANG": "ja"})
        self.assertIn("a.txt", reason)
        self.assertIn("消え", reason)


if __name__ == "__main__":
    unittest.main()
