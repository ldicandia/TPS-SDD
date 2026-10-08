# TP3 — Toolkit SDD

Proyecto: el toolkit de `.claude/` (skill + subagent + hook) que encodea cómo
especificamos un cambio sobre código existente. El código que se especifica en la
evidencia es `gcsgrep`, que vive fuera, en `../TP1 Greenfield/Tarea/`.

## Comandos

- Tests del toolkit: `python3 -m unittest discover -s tarea/tests` (en Windows, `py -3`)
- Chequear una spec: `python3 .claude/skills/write-spec-brownfield/scripts/check_spec.py specs/<slug>.md`

## Convenciones

- Las specs van en `specs/<slug>.md` del proyecto abierto. El hook `spec-gate` solo
  mira archivos `.md` bajo una carpeta `specs/`: una spec fuera de ahí no se valida.
- `git add` y `git commit` van en **llamadas separadas**. El hook veta un commit que
  venga pegado a otra operación con `&&`, `;` o pipes, porque no puede inspeccionar
  el índice resultante antes de que se escriba.
- Los tests de `tarea/tests/` mutan el fixture de `tarea/tests/fixtures.py`, no la
  spec de `tarea/evidencia/specs/`: esa es salida de una sesión y se regenera.
- No reescribir las evidencias `01`–`11`: son el registro de corridas puntuales. Una
  corrida nueva se agrega con número nuevo.

## SDD

- Para especificar un cambio sobre código existente, el flujo está en el skill
  `write-spec-brownfield`; la revisión, en el subagent `spec-reviewer`.
- Una spec no está lista hasta que `check_spec.py` sale 0 **y** el revisor da `READY`
  con C1–C5 en `OK`. Ningún veredicto se declara sin su informe.
