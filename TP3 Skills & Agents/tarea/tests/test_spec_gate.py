"""Regresiones del índice y de los comandos de spec-gate en repos temporales.

Desde TP3 Skills & Agents/: python3 -m unittest discover -s tarea/tests -v
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixtures import SPEC_VALIDA as VALID  # noqa: E402

PROJECT = Path(__file__).resolve().parents[2]
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

    def gate(self, command="git commit -m prueba", tool="Bash", cwd=None):
        event = {"tool_name": tool, "hook_event_name": "PreToolUse",
                 "cwd": str(cwd or self.project),
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

    def test_structural_defects_in_index_stay_blocked_after_worktree_fix(self):
        cases = (
            ("- **VC-FR-1**", "- **VC-FR-1** · `run(datos)` →", "VC sin resultado esperado"),
            ("- **Dado**", "- **Dado**", "FR-1 con **Dado** vacío"),
            ("- **Umbral**", "- **Umbral** Debe ser rápido (`src/gcs.py:94-101`).",
             "NFR-1 con **Umbral** sin medida numérica"),
        )
        for prefix, replacement, diagnostic in cases:
            with self.subTest(prefix=prefix):
                content = "\n".join(replacement if line.startswith(prefix) else line
                                    for line in VALID.splitlines()) + "\n"
                self.spec.write_text(content, encoding="utf-8")
                self.git("add", "specs/caso con espacios.md")
                self.spec.write_text(VALID, encoding="utf-8")
                code, error = self.gate()
                self.assertEqual(code, 2, error)
                self.assertIn("[staged]", error)
                self.assertIn(diagnostic, error)

    def test_empty_then_in_worktree_blocks_valid_index(self):
        content = "\n".join("- **Entonces**" if line.startswith("- **Entonces**") else line
                            for line in VALID.splitlines()) + "\n"
        self.spec.write_text(content, encoding="utf-8")
        code, error = self.gate()
        self.assertEqual(code, 2, error)
        self.assertIn("[copia de trabajo]", error)
        self.assertIn("FR-1 con **Entonces** vacío", error)

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

    def test_quoted_c_with_spaces_blocks_invalid_index(self):
        self.stage_invalid()
        for quote in ('"', "'"):
            with self.subTest(quote=quote):
                self.assert_blocked("git -C " + quote + str(self.project) + quote + " commit -m prueba")

    def test_quoted_c_same_repo_passes_valid_spec(self):
        for command in (
            'git -C "' + str(self.project) + '" commit -m prueba',
            'git -C "' + str(self.repo) + '" -C "TP3 Skills & Agents" commit -m prueba',
            'git -C "" --no-pager commit -m prueba',
        ):
            with self.subTest(command=command):
                self.assertEqual(self.gate(command), (0, ""))

    def test_quoted_c_powershell_blocks_invalid_index(self):
        self.stage_invalid()
        command = 'git -C "' + str(self.project) + '" commit -m prueba'
        code, error = self.gate(command, tool="PowerShell")
        self.assertEqual(code, 2, error)
        self.assertIn("[staged]", error)

    def test_add_and_commit_with_new_invalid_spec_blocks_before_add(self):
        new = self.project / "specs/nueva.md"
        new.write_text(INVALID, encoding="utf-8")
        code, error = self.gate("git add specs/nueva.md && git commit -m prueba")
        self.assertEqual(code, 2, error)
        self.assertIn("separá el commit", error)
        self.assertEqual(self.git("ls-files", "--", "specs/nueva.md"), b"")
        self.assertEqual(new.read_text(encoding="utf-8"), INVALID)

    def test_add_and_commit_is_also_rejected_with_valid_spec(self):
        new = self.project / "specs/nueva.md"
        new.write_text(VALID, encoding="utf-8")
        code, error = self.gate("git add specs/nueva.md && git commit -m prueba")
        self.assertEqual(code, 2, error)
        self.assertIn("separá el commit", error)

    def test_compound_commits_require_separate_calls(self):
        for command in (
            "git add .; git commit -m prueba",
            "git add .\ngit commit -m prueba",
            "cd . && git commit -m prueba",
            "git commit -m prueba && git status",
            "(git commit -m prueba)",
        ):
            with self.subTest(command=command):
                code, error = self.gate(command)
                self.assertEqual(code, 2, error)
                self.assertIn("separá el commit", error)

    def test_other_repo_and_event_cwd_are_rejected(self):
        other = self.repo / "otro repo"
        self.git("init", "-q", str(other))
        for command, cwd in (
            ('git -C "' + str(other) + '" commit -m prueba', None),
            ("git commit -m prueba", other),
        ):
            with self.subTest(command=command, cwd=cwd):
                code, error = self.gate(command, cwd=cwd)
                self.assertEqual(code, 2, error)
                self.assertIn("otro repositorio", error)

    def test_mentions_of_commit_are_not_git_commits(self):
        self.stage_invalid()
        for command in (
            "git log --grep commit", "echo git commit", 'echo "git commit"',
            'git status && echo "git commit"', "git status # git commit -m prueba",
            "git status # nota; git commit -m prueba",
            'git commit-not-a-command',
        ):
            with self.subTest(command=command):
                self.assertEqual(self.gate(command), (0, ""))

    def test_quoted_message_operators_are_data(self):
        for command in (
            'git commit -m "&&"', "git commit -m ';'", 'git commit -m "()"',
            'git commit -m "git add . && git commit"', "git commit -m prueba\n",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.gate(command), (0, ""))

    def test_overrides_and_dynamic_c_paths_are_rejected(self):
        for command in (
            "git -c user.name=Prueba commit -m prueba",
            "git --git-dir=otro commit -m prueba",
            "GIT_INDEX_FILE=otro git commit -m prueba",
            'git -C "$PWD" commit -m prueba',
            'git "$subcommand" -m prueba',
            'git co`mmit -m prueba',
        ):
            with self.subTest(command=command):
                code, error = self.gate(command)
                self.assertEqual(code, 2, error)
                self.assertIn("commit bloqueado", error)

    def test_unbalanced_quotes_are_rejected(self):
        code, error = self.gate('git -C "ruta sin cierre commit')
        self.assertEqual(code, 2, error)
        self.assertIn("commit bloqueado", error)

    def test_unparseable_commands_without_commit_are_not_blocked(self):
        """Un comando raro que no es commit no tiene por qué frenar la sesión."""
        self.stage_invalid()
        for command in (r"echo $'don\'t panic'", "awk '{print $1}' archivo", "echo ok"):
            with self.subTest(command=command):
                self.assertEqual(self.gate(command), (0, ""))

    def test_wrapped_commits_are_rejected(self):
        """Prefijos como time/sudo no convierten un commit en otro comando."""
        self.stage_invalid()
        for command in (
            "time git commit -m prueba", "sudo git commit -m prueba",
            "nohup git commit -m prueba", "nice -n 5 git commit -m prueba",
            "stdbuf -o0 git commit -m prueba", "timeout 5 git commit -m prueba",
            "sudo -u alguien git commit -m prueba",
        ):
            with self.subTest(command=command):
                code, error = self.gate(command)
                self.assertEqual(code, 2, error)
                self.assertIn("commit con wrapper", error)

    def test_wrappers_without_a_commit_still_pass(self):
        self.stage_invalid()
        for command in ("time pytest -q", "sudo git status", "nohup ls"):
            with self.subTest(command=command):
                self.assertEqual(self.gate(command), (0, ""))

    def test_specs_in_subdirectories_are_validated(self):
        """specs/<subcarpeta>/x.md sigue siendo una spec: el gate la mira."""
        anidada = self.project / "specs/2026-10/anidada.md"
        anidada.parent.mkdir(parents=True)
        anidada.write_text(INVALID, encoding="utf-8")
        self.git("add", "specs/2026-10/anidada.md")
        code, error = self.gate()
        self.assertEqual(code, 2, error)
        self.assertIn("specs/2026-10/anidada.md:", error)

    def test_markdown_outside_specs_is_still_ignored(self):
        fuera = self.project / "docs/notas.md"
        fuera.parent.mkdir()
        fuera.write_text(INVALID, encoding="utf-8")
        self.git("add", "docs/notas.md")
        self.assertEqual(self.gate(), (0, ""))


if __name__ == "__main__":
    unittest.main()
