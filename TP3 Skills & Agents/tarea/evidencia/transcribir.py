#!/usr/bin/env python3
"""Convierte una sesión `claude -p --output-format stream-json --verbose` en una transcripción legible.

Uso: python3 transcribir.py raw/<sesion>.jsonl > <sesion>.md
Marca con [subagent] lo que corrió dentro de un subagent (parent_tool_use_id) y cuenta,
al final, cuántas herramientas usó la sesión principal y cuántas el subagent.
Transcribe también los permisos denegados, y declara al pie qué eventos del JSONL
quedaron afuera, para que la transcripción no esconda nada sin decirlo.
"""
import collections
import json
import sys

LARGO = 600  # recorte de resultados de herramientas; el del subagent y los vetos van enteros


def limpio(texto):
    """CRLF del output de Windows → LF.

    Sin esto la transcripción queda con los CR que trae el JSONL, git los
    normaliza o no según el core.autocrlf de cada máquina, y el archivo deja de
    regenerarse igual en otra plataforma.
    """
    return texto.replace("\r\n", "\n").replace("\r", "\n")


def corto(texto, n=LARGO):
    texto = limpio(texto).strip()
    return texto if len(texto) <= n else texto[:n] + f"\n… [{len(texto) - n} caracteres más]"


def texto_de(contenido):
    if isinstance(contenido, str):
        return contenido
    return "\n".join(c.get("text", "") for c in contenido if isinstance(c, dict))


def main(path):
    sys.stdout.reconfigure(encoding="utf-8")
    nombres, cuenta = {}, {"principal": 0, "subagent": 0}
    omitido = collections.Counter()
    print(f"# Transcripción — `{path.replace(chr(92), '/').split('/')[-1]}`\n")
    for linea in open(path, encoding="utf-8"):
        ev = json.loads(linea)
        quien = "[subagent] " if ev.get("parent_tool_use_id") else ""
        if ev["type"] == "system" and ev.get("subtype") == "init":
            print(f"- Sesión nueva `{ev['session_id']}` · modelo `{ev['model']}` · Claude Code {ev.get('claude_code_version', '?')}")
            propios = [s for s in ev.get("skills", []) if s == "write-spec-brownfield"]
            agentes = [a for a in ev.get("agents", []) if a == "spec-reviewer"]
            print(f"- Skill del toolkit disponible: {propios} · subagent: {agentes}\n")
        elif ev["type"] == "assistant":
            for c in ev["message"]["content"]:
                if c["type"] == "text" and c["text"].strip():
                    print(f"**{quien}Claude:** {corto(c['text'], 4000)}\n")
                elif c["type"] == "tool_use":
                    nombres[c["id"]] = c["name"]
                    cuenta["subagent" if quien else "principal"] += 1
                    args = json.dumps(c["input"], ensure_ascii=False)
                    print(f"`{quien}→ {c['name']}` {corto(args, 400)}\n")
        elif ev["type"] == "user":
            contenido = ev["message"]["content"]
            if isinstance(contenido, str):
                continue
            for c in contenido:
                if c.get("type") != "tool_result":
                    continue
                nombre = nombres.get(c["tool_use_id"], "?")
                cuerpo = texto_de(c.get("content", ""))
                entero = nombre in ("Agent", "Task") or "spec-gate" in cuerpo
                marca = " (error)" if c.get("is_error") else ""
                print(f"`{quien}← {nombre}{marca}`\n\n```text\n{limpio(cuerpo).strip() if entero else corto(cuerpo)}\n```\n")
        elif ev["type"] == "system" and ev.get("subtype") == "permission_denied":
            # No se omite: es el agente chocando con otro gate, no con el hook.
            motivo = ev.get("decision_reason") or ev.get("message", "")
            print(f"`{quien}✗ permiso denegado · {ev.get('tool_name', '?')}`\n\n```text\n{corto(motivo)}\n```\n")
        elif ev["type"] == "result":
            print(f"---\n**Fin:** {ev.get('subtype')} · turnos {ev.get('num_turns')} · "
                  f"{ev.get('duration_ms', 0) / 1000:.0f} s")
        elif ev["type"] == "system":
            omitido["system:" + str(ev.get("subtype"))] += 1
        else:
            omitido[ev["type"]] += 1
    print(f"\n**Herramientas usadas:** sesión principal {cuenta['principal']} · dentro del subagent {cuenta['subagent']}")
    if omitido:
        resumen = ", ".join(f"{k} ×{v}" for k, v in sorted(omitido.items()))
        print(f"\n**Eventos del JSONL no transcriptos** (ruido de runtime, sin contenido del modelo): {resumen}")


if __name__ == "__main__":
    main(sys.argv[1])
