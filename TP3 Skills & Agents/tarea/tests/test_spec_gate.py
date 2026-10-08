"""Regresiones del índice de spec-gate; solo usa repositorios temporales.

Desde TP3 Skills & Agents/: python3 -m unittest discover -s tarea/tests -v
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[2]
VALID = (PROJECT / "tarea/evidencia/specs/gcsgrep-count.md").read_text(encoding="utf-8")
INVALID = "\n".join(
    line for line in VALID.splitlines() if not line.startswith("- **VC-FR-1**")
) + "\n"


class SpecGateIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="spec-gate-test-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.project = self.repo / "TP3 Skills & Agents"
        self.project.mkdir()
        shutil.copytree(PROJECT / ".claude", self.project / ".claude")
        # Es el mismo caso de subcarpeta y espacios que el proyecto real.
        self.spec = self.project / "specs/caso con espacios.md"
        self.spec.parent.mkdir()
        self.spec.write_text(VALID, encoding="utf-8")
        self.env = {
            key: value for key, value in os.environ.items()
            if not key.startswith("GIT_")
        }
        self.env.update(
            GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
            CLAUDE_PROJECT_DIR=str(self.project), PYTHONDONTWRITEBYTECODE="1",
        )
        self.git("init", "-q", str(self.repo))
        self.git("add", "specs/caso con espacios.md")
        # Baseline ficticia, sin hooks de usuario y sin tocar el repo del equipo.
        self.git("-c", "user.name=Prueba", "-c", "user.email=prueba@example.invalid",
                 "-c", "core.hooksPath=" + str(self.repo / "sin-hooks"),
                 "-c", "commit.gpgsign=false", "commit", "-qm", "baseline de prueba")

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.project, env=self.env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        ).stdout

    def stage_invalid(self):
        self.spec.write_text(INVALID, encoding="utf-8")
        self.git("add", "specs/caso con espacios.md")

    def gate(self, command="git commit -m prueba", tool="Bash"):
        event = {"tool_name": tool, "hook_event_name": "PreToolUse",
                 "tool_input": {"command": command}}
        before = self.git("write-tree")
        result = subprocess.run(
            ["bash", ".claude/hooks/spec-gate.sh"], cwd=self.project, env=self.env,
            input=json.dumps(event).encode(), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(before, self.git("write-tree"), "el hook modificó el índice")
        return result.returncode, result.stderr.decode("utf-8")

    def assert_blocked(self, command="git commit -m prueba", source="staged"):
        code, error = self.gate(command)
        self.assertEqual(code, 2, error)
        self.assertIn("[" + source + "]", error)
        self.assertIn("FR-1 no tiene", error)
        self.assertIn("specs/caso con espacios.md:", error)

    def test_invalid_index_stays_blocked_after_worktree_fix(self):
        self.stage_invalid()
        self.spec.write_text(VALID, encoding="utf-8")
        self.assert_blocked()
        self.assertNotIn(b"- **VC-FR-1**", self.git("show", ":TP3 Skills & Agents/specs/caso con espacios.md"))

    def test_invalid_index_stays_blocked_after_worktree_deletion(self):
        self.stage_invalid()
        self.spec.unlink()
        self.assert_blocked()

    def test_restage_fixed_spec_passes(self):
        self.stage_invalid()
        self.spec.write_text(VALID, encoding="utf-8")
        self.git("add", "specs/caso con espacios.md")
        self.assertEqual(self.gate(), (0, ""))

    def test_valid_staged_change_passes(self):
        self.spec.write_text(VALID + "\nNota cerrada.\n", encoding="utf-8")
        self.git("add", "specs/caso con espacios.md")
        self.assertEqual(self.gate(), (0, ""))

    def test_valid_index_invalid_worktree_blocks_conservatively(self):
        self.spec.write_text(INVALID, encoding="utf-8")
        self.assert_blocked(source="copia de trabajo")

    def test_commit_a_checks_both_versions(self):
        self.stage_invalid()
        self.spec.write_text(VALID, encoding="utf-8")
        self.assert_blocked("git commit -am prueba")

    def test_commit_with_path_checks_both_versions(self):
        self.stage_invalid()
        self.spec.write_text(VALID, encoding="utf-8")
        self.assert_blocked('git commit -m prueba -- "specs/caso con espacios.md"')

    def test_new_invalid_staged_spec_blocks_after_worktree_fix(self):
        self.spec = self.project / "specs/nueva.md"
        self.spec.write_text(INVALID, encoding="utf-8")
        self.git("add", "specs/nueva.md")
        self.spec.write_text(VALID, encoding="utf-8")
        code, error = self.gate()
        self.assertEqual(code, 2, error)
        self.assertIn("[staged] specs/nueva.md:", error)

    def test_staged_deletion_passes(self):
        self.git("rm", "specs/caso con espacios.md")
        self.assertEqual(self.gate(), (0, ""))

    def test_staged_deletion_with_invalid_recreated_file_blocks(self):
        self.git("rm", "specs/caso con espacios.md")
        self.spec.parent.mkdir(exist_ok=True)
        self.spec.write_text(INVALID, encoding="utf-8")
        self.assert_blocked('git commit -m prueba -- "specs/caso con espacios.md"',
                            source="copia de trabajo")

    def test_non_commit_passes_with_invalid_index(self):
        self.stage_invalid()
        self.assertEqual(self.gate("git status"), (0, ""))

    def test_powershell_event_validates_index(self):
        self.stage_invalid()
        self.spec.write_text(VALID, encoding="utf-8")
        code, error = self.gate(tool="PowerShell")
        self.assertEqual(code, 2, error)
        self.assertIn("[staged]", error)


if __name__ == "__main__":
    unittest.main()
