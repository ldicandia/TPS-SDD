"""Regresiones estructurales del checker; no ejecutan los VCs de la spec."""
import importlib.util
from pathlib import Path
import re
import subprocess
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixtures import SPEC_VALIDA as VALID  # noqa: E402

PROJECT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT / ".claude/skills/write-spec-brownfield/scripts/check_spec.py"
# La spec entregada es salida de una sesión y cambia en cada corrida: se comprueba
# entera en test_delivered_spec_passes, pero las mutaciones usan el fixture fijo.
ENTREGADA = PROJECT / "tarea/evidencia/specs/gcsgrep-count.md"
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

    def test_fixture_passes_with_complete_trace(self):
        errors, trace = CHECKER.check("specs/caso.md", VALID)
        self.assertEqual(errors, [])
        self.assertEqual(len(trace), 3)
        self.assertEqual(len({rid for rid, vc in trace}), 3)

    def test_delivered_spec_passes(self):
        """La spec que produjo la sesión 01 pasa el checker tal como se entrega."""
        errors, trace = CHECKER.check(str(ENTREGADA), ENTREGADA.read_text(encoding="utf-8"))
        self.assertEqual(errors, [])
        # Un VC por requerimiento, sin requerimientos sueltos ni VCs duplicados.
        self.assertTrue(trace)
        self.assertEqual(len(trace), len({rid for rid, vc in trace}))

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

    def test_api_versions_are_not_future_scope(self):
        """`v2` como versión de API no es "alcance futuro" (mismo caso que todo/TODO)."""
        for value in ("`gcloud --api-version=v2 ls` → exit 0",
                      "`curl /storage/v2/objects` → HTTP 200",
                      '`run(["v2"])` → stdout `v2`, exit 0'):
            with self.subTest(value=value):
                content = replace_line(VALID, "- **VC-FR-1**", "- **VC-FR-1** · " + value)
                self.assertEqual(self.errors(content), [])

    def test_deferred_scope_inside_a_requirement_is_still_rejected(self):
        for value in ("queda para v2", "se completa en v3", "lo vemos más adelante"):
            with self.subTest(value=value):
                content = replace_line(VALID, "- **Entonces**", "- **Entonces** " + value)
                self.assert_problem(content, "alcance futuro")

    def test_decision_anchor_must_look_like_a_source_file(self):
        """"Lo pide la consigna" no se arregla pegándole cualquier número."""
        for value in ("la consigna RFC 2616 sección 3.1:20 lo pide",
                      "según el manual v1.2:30",
                      "lo decidimos así en el equipo"):
            with self.subTest(value=value):
                content = VALID.replace("`src/gcsgrep/cli.py:96` fija que sin coincidencias stdout queda vacío con exit 1",
                                        value)
                self.assert_problem(content, "sin fundamento 'archivo:línea'")

    def test_real_anchors_are_still_accepted(self):
        for value in ("`src/gcsgrep/cli.py:96` lo fija",
                      "`README.md:12` documenta el flag",
                      "`tests/test_gcsgrep.py:291-295` lo cubre"):
            with self.subTest(value=value):
                content = VALID.replace("`src/gcsgrep/cli.py:96` fija que sin coincidencias stdout queda vacío con exit 1",
                                        value)
                self.assertEqual(self.errors(content), [])

    def test_angle_bracket_data_is_not_a_placeholder(self):
        for value in ("lee de <stdin> cuando no hay archivo",
                      "el header es Content-Type: <application/json>",
                      "avisa a <soporte@itba.edu.ar>"):
            with self.subTest(value=value):
                content = replace_line(VALID, "- **Dado**", "- **Dado** " + value)
                self.assertEqual(self.errors(content), [])

    def test_template_placeholders_are_still_rejected(self):
        for value in ("<estado inicial concreto, con los datos que hacen falta>",
                      "<poner acá el estado inicial>"):
            with self.subTest(value=value):
                content = replace_line(VALID, "- **Dado**", "- **Dado** " + value)
                self.assert_problem(content, "placeholder sin completar")

    def test_traceability_section_is_required(self):
        content = re.sub(r"^## Trazabilidad.*", "", VALID, flags=re.M | re.S)
        self.assert_problem(content, "falta la sección '## Trazabilidad'")

    def test_cli_stdin_reports_the_same_structural_error_and_exit_one(self):
        content = replace_line(VALID, "- **VC-FR-1**", "- **VC-FR-1** · `run(datos)` →")
        result = subprocess.run([sys.executable, str(SCRIPT), "--stdin", "specs/caso.md"],
                                input=content.encode("utf-8"), capture_output=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(self.errors(content)[0], result.stdout.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
