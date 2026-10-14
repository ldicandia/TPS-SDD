"""Regresiones del hook gcs-allowlist: se alimenta el evento por stdin, como lo hace Claude Code.

Desde `TP4 Plugins adn MCP/`:  py -3 -m unittest discover -s Tarea/tests -v
"""
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT_PY = RAIZ / ".claude" / "hooks" / "gcs_allowlist.py"
SCRIPT_SH = RAIZ / ".claude" / "hooks" / "gcs-allowlist.sh"
BUCKET = "bucket-de-prueba-tp4"


def buscar_bash():
    # En Windows, si WSL está instalado, `bash` resuelve a System32\bash.exe y no ve
    # el Python de Windows. Claude Code usa el de Git for Windows: probamos ese primero.
    if os.name == "nt" and shutil.which("git"):
        git = Path(shutil.which("git")).resolve()
        for candidato in (git.parent.parent / "bin" / "bash.exe", git.parent / "bash.exe"):
            if candidato.exists():
                return str(candidato)
    return shutil.which("bash")


BASH = buscar_bash()


def correr(evento, bucket=BUCKET, opcion_plugin=None, crudo=None, via_bash=False):
    env = {k: v for k, v in os.environ.items()
           if k not in ("GCSGREP_BUCKET", "CLAUDE_PLUGIN_OPTION_BUCKET")}
    if bucket is not None:
        env["GCSGREP_BUCKET"] = bucket
    if opcion_plugin is not None:
        env["CLAUDE_PLUGIN_OPTION_BUCKET"] = opcion_plugin
    entrada = crudo if crudo is not None else json.dumps(evento)
    cmd = [BASH, str(SCRIPT_SH)] if via_bash else [sys.executable, str(SCRIPT_PY)]
    r = subprocess.run(cmd, input=entrada, capture_output=True, text=True, env=env)
    return r.returncode, r.stderr


def evento(tool, prefijo="mcp__gcs__", **entrada):
    entrada.setdefault("bucket_name", BUCKET)
    return {"hook_event_name": "PreToolUse", "tool_name": prefijo + tool, "tool_input": entrada}


PLUGIN = "mcp__plugin_gcsgrep-sdd_gcs__"


class Permitidas(unittest.TestCase):
    def test_tres_lecturas_pasan(self):
        for tool in ("list_objects", "read_object_metadata", "read_object_content"):
            with self.subTest(tool=tool):
                self.assertEqual(correr(evento(tool, object_name="logs/app/server.log"))[0], 0)

    def test_nombres_del_plugin_pasan(self):
        self.assertEqual(correr(evento("read_object_content", PLUGIN, object_name="x"))[0], 0)

    def test_bucket_desde_opcion_del_plugin(self):
        codigo, _ = correr(evento("list_objects", PLUGIN), bucket=None, opcion_plugin=BUCKET)
        self.assertEqual(codigo, 0)


class Vetadas(unittest.TestCase):
    def test_escrituras_del_modo_seguro(self):
        for tool in ("write_object_safe", "upload_object_safe", "copy_object_safe", "create_bucket"):
            for prefijo in ("mcp__gcs__", PLUGIN):
                with self.subTest(tool=tool, prefijo=prefijo):
                    codigo, err = correr(evento(tool, prefijo, object_name="x", content="eA=="))
                    self.assertEqual(codigo, 2)
                    self.assertIn("allowlist", err)

    def test_lecturas_no_revisadas(self):
        # Leen, pero no las usa el toolkit: quedan afuera hasta que alguien las mire.
        for tool in ("list_buckets", "view_iam_policy", "execute_insights_query", "get_bucket_metadata"):
            with self.subTest(tool=tool):
                self.assertEqual(correr(evento(tool))[0], 2)

    def test_destructivas_y_tool_futura(self):
        for tool in ("delete_object", "move_object", "write_object", "tool_que_todavia_no_existe"):
            with self.subTest(tool=tool):
                self.assertEqual(correr(evento(tool))[0], 2)

    def test_otro_bucket(self):
        codigo, err = correr(evento("read_object_content", bucket_name="bucket-de-produccion", object_name="x"))
        self.assertEqual(codigo, 2)
        self.assertIn("bucket-de-produccion", err)

    def test_sin_bucket_en_argumentos(self):
        e = evento("list_objects")
        del e["tool_input"]["bucket_name"]
        self.assertEqual(correr(e)[0], 2)

    def test_sin_bucket_configurado(self):
        codigo, err = correr(evento("list_objects"), bucket=None)
        self.assertEqual(codigo, 2)
        self.assertIn("GCSGREP_BUCKET", err)

    def test_otro_server_u_otro_plugin(self):
        for nombre in ("mcp__otro__list_objects", "mcp__plugin_otro_gcs__list_objects", "Bash"):
            with self.subTest(nombre=nombre):
                e = evento("list_objects")
                e["tool_name"] = nombre
                self.assertEqual(correr(e)[0], 2)

    def test_evento_ilegible(self):
        for crudo in ("", "{no es json", "[]", '{"tool_name": 3}', '{"tool_name": "mcp__gcs__list_objects"}'):
            with self.subTest(crudo=crudo):
                self.assertEqual(correr(None, crudo=crudo)[0], 2)


@unittest.skipUnless(BASH, "sin bash en el PATH")
class ViaBash(unittest.TestCase):
    """El registro invoca el .sh: comprueba que encuentre Python y propague el código."""

    def test_pasa_y_veta_por_el_wrapper(self):
        self.assertEqual(correr(evento("list_objects"), via_bash=True)[0], 0)
        self.assertEqual(correr(evento("write_object_safe"), via_bash=True)[0], 2)


if __name__ == "__main__":
    unittest.main()
