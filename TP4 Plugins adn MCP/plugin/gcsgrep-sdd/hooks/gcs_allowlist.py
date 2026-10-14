"""gcs-allowlist · PreToolUse sobre las tools MCP del server de Cloud Storage.

Allowlist, no denylist: pasan solo las tres tools de lectura que usa el toolkit, y solo
contra el bucket de prueba. Todo lo demás se veta, incluida cualquier tool nueva que
traiga la próxima versión del server, hasta que alguien la revise y la agregue acá.

Es la capa de arriba, no la garantía. Debajo están el modo del server (sin
--enable-destructive-tools no existen delete_object ni move_object) y, la que garantiza,
la credencial: la service account solo tiene roles/storage.objectViewer sobre el bucket.

El nombre de la tool cambia al empaquetar:
    mcp__gcs__<tool>   ->   mcp__plugin_gcsgrep-sdd_gcs__<tool>
Este script acepta los dos. Un matcher que no matchea no avisa: simplemente no veta.

Sale 0 para dejar pasar y 2 para vetar (el stderr le llega al agente).
"""
import json
import os
import re
import sys

PERMITIDAS = {"list_objects", "read_object_metadata", "read_object_content"}
PREFIJO = re.compile(r"^mcp__(?:plugin_gcsgrep-sdd_)?gcs__(?P<tool>[A-Za-z0-9_]+)$")


def bucket_permitido():
    # Proyecto: GCSGREP_BUCKET en el entorno. Plugin: la opción `bucket` del userConfig.
    return (os.environ.get("GCSGREP_BUCKET")
            or os.environ.get("CLAUDE_PLUGIN_OPTION_BUCKET")
            or "").strip()


def vetar(motivo):
    print("gcs-allowlist: " + motivo, file=sys.stderr)
    return 2


def decidir(evento):
    nombre = evento.get("tool_name")
    if not isinstance(nombre, str):
        return vetar("el evento no trae tool_name; bloqueo por las dudas.")
    m = PREFIJO.match(nombre)
    if not m:
        return vetar(nombre + " no es una tool del server gcs que este hook conozca. "
                     "Si el matcher la mandó acá, revisá el nombre del server.")
    tool = m.group("tool")
    if tool not in PERMITIDAS:
        return vetar(tool + " no está en la allowlist (solo list_objects, "
                     "read_object_metadata y read_object_content). El toolkit lee el "
                     "bucket de prueba, no escribe ni administra: si hace falta un objeto "
                     "nuevo, lo sube una persona con su propia cuenta.")
    esperado = bucket_permitido()
    if not esperado:
        return vetar("no sé cuál es el bucket de prueba: definí GCSGREP_BUCKET (o la "
                     "opción bucket del plugin). Sin eso no dejo leer ningún bucket.")
    entrada = evento.get("tool_input")
    if not isinstance(entrada, dict):
        return vetar("el evento no trae tool_input; bloqueo por las dudas.")
    bucket = entrada.get("bucket_name")
    if bucket != esperado:
        return vetar("%s sobre el bucket %r: este toolkit solo lee %r, el bucket de "
                     "prueba con objetos sintéticos." % (tool, bucket, esperado))
    return 0


def main():
    # En Windows, con stderr a un pipe, Python escribe en cp1252 y Claude Code lee UTF-8:
    # el agente recibía "est�" en vez de "está".
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        evento = json.load(sys.stdin)
    except (ValueError, UnicodeDecodeError):
        return vetar("no pude leer el evento JSON; bloqueo por las dudas.")
    if not isinstance(evento, dict):
        return vetar("el evento no es un objeto JSON; bloqueo por las dudas.")
    return decidir(evento)


if __name__ == "__main__":
    sys.exit(main())
