#!/usr/bin/env python3
"""Convierte una sesión `claude -p --output-format stream-json --verbose` en una transcripción legible.

Uso: python3 transcribir.py raw/<sesion>.jsonl > <sesion>.md
Marca con [subagent] lo que corrió dentro de un subagent (parent_tool_use_id) y cuenta,
al final, cuántas herramientas usó la sesión principal y cuántas el subagent.
"""
import json
import sys

LARGO = 600  # recorte de resultados de herramientas; el del subagent y los vetos van enteros


def corto(texto, n=LARGO):
    texto = texto.strip()
    return texto if len(texto) <= n else texto[:n] + f"\n… [{len(texto) - n} caracteres más]"


def texto_de(contenido):
    if isinstance(contenido, str):
        return contenido
    return "\n".join(c.get("text", "") for c in contenido if isinstance(c, dict))


def main(path):
    sys.stdout.reconfigure(encoding="utf-8")
    nombres, cuenta = {}, {"principal": 0, "subagent": 0}
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
                print(f"`{quien}← {nombre}{marca}`\n\n```text\n{cuerpo.strip() if entero else corto(cuerpo)}\n```\n")
        elif ev["type"] == "result":
            print(f"---\n**Fin:** {ev.get('subtype')} · turnos {ev.get('num_turns')} · "
                  f"{ev.get('duration_ms', 0) / 1000:.0f} s")
    print(f"\n**Herramientas usadas:** sesión principal {cuenta['principal']} · dentro del subagent {cuenta['subagent']}")


if __name__ == "__main__":
    main(sys.argv[1])
