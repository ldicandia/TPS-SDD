"""Regresiones estructurales del checker; no ejecutan los VCs de la spec."""
import importlib.util
from pathlib import Path
import re
import subprocess
import sys
import unittest


PROJECT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT / ".claude/skills/write-spec-brownfield/scripts/check_spec.py"
VALID = (PROJECT / "tarea/evidencia/specs/gcsgrep-count.md").read_text(encoding="utf-8")
MODULE_SPEC = importlib.util.spec_from_file_location("check_spec", SCRIPT)
CHECKER = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(CHECKER)


def replace_line(content, prefix, replacement):
    return re.sub(r"^" + re.escape(prefix) + r".*$",
                  lambda match: replacement, content, count=1, flags=re.M)


class CheckSpecTests(unittest.TestCase):
    def errors(self, content):
        return CHECKER.check("specs/caso.md", content)[0]

    def assert_problem(self, content, expected):
        errors = self.errors(content)
        self.assertTrue(any(expected in error for error in errors), errors)
        self.assertTrue(all(re.match(r"specs/caso.md:\d+: ", e) for e in errors))

    def test_current_spec_passes_with_complete_trace(self):
        errors, trace = CHECKER.check("specs/caso.md", VALID)
        self.assertEqual(errors, [])
        self.assertEqual(len(trace), 12)
        self.assertEqual(len({rid for rid, vc in trace}), 12)

    def test_vc_without_expected_result_is_rejected_for_all_requirement_types(self):
        for rid in ("FR-1", "INV-1", "NFR-1"):
            with self.subTest(rid=rid):
                content = replace_line(VALID, "- **VC-" + rid + "**",
                                       "- **VC-" + rid + "** · `comando de prueba`")
                self.assert_problem(content, "VC sin resultado esperado")

    def test_empty_expected_result_is_rejected(self):
        for result in ("", "...", "``", "—", "__"):
            with self.subTest(result=result):
                content = replace_line(VALID, "- **VC-FR-1**",
                                       "- **VC-FR-1** · `run(datos)` → " + result)
                self.assert_problem(content, "VC sin resultado esperado")

    def test_missing_or_empty_input_is_rejected_even_with_output(self):
        for value in ("", "``", "`...`"):
            with self.subTest(value=value):
                content = replace_line(VALID, "- **VC-FR-1**",
                                       "- **VC-FR-1** · " + value + " → stdout `ok`, exit 0")
                self.assert_problem(content, "VC sin entrada/comando")

    def test_arrow_inside_command_does_not_replace_result_separator(self):
        content = replace_line(VALID, "- **VC-FR-1**",
                               '- **VC-FR-1** · `run(["→"])`')
        self.assert_problem(content, "VC sin resultado esperado")

    def test_literal_arrow_and_explicit_empty_stdout_are_valid(self):
        content = replace_line(VALID, "- **VC-FR-1**",
                               '- **VC-FR-1** · `run(["→"])` → stdout `""`, exit 1')
        self.assertEqual(self.errors(content), [])

    def test_last_scenario_cannot_have_empty_result(self):
        content = replace_line(VALID, "- **VC-FR-1**",
                               '- **VC-FR-1** · `run(a)` → stdout `ok`; `run(b)` →')
        self.assert_problem(content, "VC sin resultado esperado")

    def test_unclosed_backticks_are_rejected(self):
        content = replace_line(VALID, "- **VC-FR-1**",
                               '- **VC-FR-1** · `run(datos)` → stdout `ok, exit 0')
        self.assert_problem(content, "VC con backticks sin cerrar")

    def test_each_given_when_then_must_have_content(self):
        for field in ("Dado", "Cuando", "Entonces"):
            for value in ("", "...", ": ``", "__"):
                with self.subTest(field=field, value=value):
                    content = replace_line(VALID, "- **" + field + "**",
                                           "- **" + field + "** " + value)
                    self.assert_problem(content, "con **" + field + "** vacío")

    def test_given_when_then_mentions_in_prose_are_not_fields(self):
        content = replace_line(VALID, "- **Dado**", "La descripción menciona **Dado** los objetos.")
        self.assert_problem(content, "FR-1 sin **Dado**")

    def test_duplicate_field_is_rejected(self):
        content = VALID.replace("- **Dado** el objeto", "- **Dado** otra condición\n- **Dado** el objeto", 1)
        self.assert_problem(content, "FR-1 repite **Dado**")

    def test_each_nfr_field_is_required_and_nonempty(self):
        for field in ("Métrica", "Umbral", "Carga"):
            with self.subTest(field=field, missing=True):
                self.assert_problem(replace_line(VALID, "- **" + field + "**", ""),
                                    "NFR-1 sin **" + field + "**")
            with self.subTest(field=field, missing=False):
                self.assert_problem(replace_line(VALID, "- **" + field + "**", "- **" + field + "**"),
                                    "con **" + field + "** vacío")

    def test_source_line_numbers_do_not_count_as_threshold_or_load(self):
        for field in ("Umbral", "Carga"):
            for value in ("Según `src/gcs.py:94-101`.", "Debe ser rápido.", "100"):
                with self.subTest(field=field, value=value):
                    content = replace_line(VALID, "- **" + field + "**", "- **" + field + "** " + value)
                    self.assert_problem(content, "con **" + field + "** sin medida numérica")

    def test_nfr_metric_must_name_a_measure(self):
        for value in ("`src/gcs.py:94-101`", "100"):
            with self.subTest(value=value):
                self.assert_problem(replace_line(VALID, "- **Métrica**", "- **Métrica** " + value),
                                    "NFR-1 sin métrica nombrada")

    def test_nfr_is_optional(self):
        content = re.sub(r"^### NFR-1.*?(?=^## Decisiones)", "", VALID, flags=re.M | re.S)
        self.assertEqual(self.errors(content), [])

    def test_cli_stdin_reports_the_same_structural_error_and_exit_one(self):
        content = replace_line(VALID, "- **VC-FR-1**", "- **VC-FR-1** · `run(datos)` →")
        result = subprocess.run([sys.executable, str(SCRIPT), "--stdin", "specs/caso.md"],
                                input=content.encode("utf-8"), capture_output=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(self.errors(content)[0], result.stdout.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
