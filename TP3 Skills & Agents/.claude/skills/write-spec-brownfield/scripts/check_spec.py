#!/usr/bin/env python3
"""Chequea que una spec brownfield (plantilla de write-spec-brownfield) no tenga huecos.

Uso: python3 check_spec.py specs/<slug>.md [...]
     python3 check_spec.py --stdin specs/<slug>.md < contenido-del-indice
Imprime la tabla de trazabilidad de cada spec. Sale 0 si todas pasan y 1 si alguna falla.
Cada problema sale como `archivo:línea: problema — qué hacer`.
"""
import pathlib
import re
import sys

REQ = re.compile(r"^### ((?:FR|NFR|INV)-[\w]+)\b")
VC = re.compile(r"^- \*\*VC-((?:FR|NFR|INV)-\w+?)(?:\.\d+)?\*\*")
ANCLA = re.compile(r"[\w./-]+\.\w+:\d+")
BASE = re.compile(r"^\*\*Base:\*\*.*@\s*`?[0-9a-f]{7,40}`?")
# TBD/TODO solo en mayúsculas: "todo" es una palabra común en castellano.
ABIERTO = re.compile(r"\b(TBD|TODO|(?i:a definir|por definir|a confirmar))\b|\?\?")
FUTURO = re.compile(r"\b(v2|en el futuro|más adelante|eventualmente|próxima iteración)\b", re.I)
PLACEHOLDER = re.compile(r"<[^<>\n]{3,}>")
# Los <placeholders> literales de la plantilla se detectan aunque queden dentro de backticks.
PLANTILLA = set(PLACEHOLDER.findall((pathlib.Path(__file__).parent.parent / "plantilla.md").read_text(encoding="utf-8")))
SECCIONES = ["Propósito", "Alcance", "Invariantes", "Requerimientos", "Decisiones"]


def filas(lines, desde, hasta):
    """Filas de datos de tabla (sin encabezado ni separador) o bullets entre dos líneas."""
    out, tabla = [], 0
    for n in range(desde, hasta):
        l = lines[n - 1].strip()
        if l.startswith("|"):
            tabla += 1
            if tabla > 2:
                out.append((n, [c.strip() for c in l.strip("|").split("|")]))
        else:
            tabla = 0
            if l.startswith("- "):
                out.append((n, [l[2:]]))
    return out


def check(path, content=None):
    lines = (open(path, encoding="utf-8").read() if content is None else content).splitlines()
    errs = []
    err = lambda n, msg: errs.append(f"{path}:{n}: {msg}")
    heads = [(n, l) for n, l in enumerate(lines, 1) if l.startswith("#")] + [(len(lines) + 1, "#")]
    h2 = {l[3:].split(" ")[0]: n for n, l in heads if l.startswith("## ")}
    h3 = {l[4:].split(" ")[0]: n for n, l in heads if l.startswith("### ")}
    fin = lambda n: next(m for m, _ in heads if m > n)

    if not any(BASE.match(l) for l in lines):
        err(1, "falta '**Base:** `<proyecto>` @ `<hash>`' — anclá la spec a la revisión del código (git rev-parse HEAD)")
    for s in SECCIONES:
        if s not in h2:
            err(1, f"falta la sección '## {s}' — copiala de plantilla.md")
    for n, l in enumerate(lines, 1):
        sin_codigo = re.sub(r"`[^`]*`", "", l)
        if ABIERTO.search(sin_codigo):
            err(n, f"decisión abierta ('{ABIERTO.search(sin_codigo).group(0)}') — cerrala o sacala del alcance")
        resto = [p for p in PLACEHOLDER.findall(l) if p in PLANTILLA] or PLACEHOLDER.findall(sin_codigo)
        if resto:
            err(n, f"placeholder sin completar '{resto[0]}'")

    for nombre, pide_ruta in (("Dentro", True), ("Fuera", False)):
        if nombre not in h3:
            err(h2.get("Alcance", 1), f"falta '### {nombre}' en el alcance")
            continue
        rows = filas(lines, h3[nombre] + 1, fin(h3[nombre]))
        if not rows:
            err(h3[nombre], f"'{nombre}' está vacío — nombrá módulos o comportamientos concretos")
        for n, cells in rows:
            if pide_ruta and "`" not in cells[0]:
                err(n, "fila de 'Dentro' sin archivo/módulo entre backticks — nombrá qué archivo cambia")
            if not pide_ruta and len(cells) == 1 and " — " in cells[0]:
                cells = cells[0].split(" — ", 1)
            if not pide_ruta and (len(cells) < 2 or cells[1] in ("", "-")):
                err(n, "fila de 'Fuera' sin el porqué — decí por qué queda afuera")

    ids, traza = set(), []
    for n, l in heads:
        m = REQ.match(l)
        if not m:
            continue
        rid, cuerpo = m.group(1), range(n + 1, fin(n))
        if rid in ids:
            err(n, f"{rid} está definido dos veces")
        ids.add(rid)
        texto = [lines[i - 1] for i in cuerpo]
        vcs = [(i, VC.match(lines[i - 1])) for i in cuerpo if VC.match(lines[i - 1])]
        if not vcs:
            err(n, f"{rid} no tiene su '- **VC-{rid}** · `comando` → resultado' — un requerimiento sin VC no es verificable")
        for i, v in vcs:
            if v.group(1) != rid:
                err(i, f"VC-{v.group(1)} está bajo {rid} — cada VC va con el requerimiento que verifica")
            if "`" not in lines[i - 1]:
                err(i, "VC sin comando ni salida observable entre backticks")
            traza.append((rid, lines[i - 1].split("**")[1]))
        if rid.startswith("FR-"):
            for palabra in ("**Dado**", "**Cuando**", "**Entonces**"):
                if not any(palabra in t for t in texto):
                    err(n, f"{rid} sin {palabra} — escribilo como Dado/Cuando/Entonces")
        if rid.startswith("NFR-") and not any(re.search(r"\d", t) for t in texto if not VC.match(t)):
            err(n, f"{rid} sin número — un NFR necesita métrica, umbral y carga")
        for i in cuerpo:
            if FUTURO.search(lines[i - 1]):
                err(i, f"alcance futuro ('{FUTURO.search(lines[i - 1]).group(0)}') dentro de un requerimiento — va al plan")
    if not any(r.startswith("FR-") for r in ids):
        err(h2.get("Requerimientos", 1), "no hay ningún '### FR-N · …'")
    if not any(r.startswith("INV-") for r in ids):
        err(h2.get("Invariantes", 1), "no hay ningún '### INV-N · …' — ¿qué de lo que hoy funciona no se puede romper?")

    if "Decisiones" in h2:
        decs = [(n, c) for n, c in filas(lines, h2["Decisiones"] + 1, fin(h2["Decisiones"])) if c[0].startswith("D-")]
        if not decs:
            err(h2["Decisiones"], "no hay decisiones '| D-N | … |'")
        for n, c in decs:
            if len(c) < 4 or c[2] in ("", "-"):
                err(n, f"{c[0]} sin alternativa descartada")
            elif not ANCLA.search(c[3]):
                err(n, f"{c[0]} sin fundamento 'archivo:línea' del código base — 'lo pide la consigna' no fundamenta")
    return errs, traza


def main(paths):
    sys.stdout.reconfigure(encoding="utf-8")
    if not paths:
        print(__doc__, file=sys.stderr)
        return 1
    if paths[0] == "--stdin":
        if len(paths) != 2:
            print(__doc__, file=sys.stderr)
            return 1
        inputs = [(paths[1], sys.stdin.buffer.read().decode("utf-8"))]
    else:
        inputs = [(p, None) for p in paths]
    total = []
    for p, content in inputs:
        errs, traza = check(p, content)
        total += errs
        estado = "OK" if not errs else f"{len(errs)} problemas"
        print(f"{p}: {estado} — {len({r for r, _ in traza})} requerimientos, {len(traza)} VCs\n")
        print("| Requerimiento | VC |\n|---|---|")
        for rid, vc in traza:
            print(f"| {rid} | {vc} |")
        print()
    for e in total:
        print(e)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
