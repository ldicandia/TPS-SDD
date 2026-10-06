#!/usr/bin/env bash
# spec-gate · PreToolUse(Bash|PowerShell). Veta un `git commit` si alguna spec en una carpeta specs/
# que el commit puede llevar (staged o modificada) no pasa check_spec.py.
cd "${CLAUDE_PROJECT_DIR:-.}" || { echo "spec-gate: no pude entrar a CLAUDE_PROJECT_DIR; bloqueo el commit." >&2; exit 2; }
CHECK=.claude/skills/write-spec-brownfield/scripts/check_spec.py
PY=""; for c in python3 python "py -3"; do $c -c 'import sys' >/dev/null 2>&1 && { PY=$c; break; }; done
[ -n "$PY" ] || { echo "spec-gate: no encontré Python 3 (python3, python o py). Instalalo: sin él no puedo chequear las specs y bloqueo el commit." >&2; exit 2; }
CMD=$($PY -c 'import json,sys; sys.stdout.reconfigure(encoding="utf-8"); print(json.load(sys.stdin.buffer)["tool_input"]["command"])' 2>/dev/null) \
  || { echo "spec-gate: el evento no trae tool_input.command legible; bloqueo por las dudas." >&2; exit 2; }
# El matcher filtra por tool (Bash|PowerShell); acá se decide por contenido: ¿es un git commit?
# Cubre `git commit -am`, `git -C . commit`, `cd x && git commit`, `git --no-pager commit`.
printf '%s\n' "$CMD" | grep -Eq '(^|[;&|(]|\s)git(\s+-[Cc]\s+\S+|\s+--\S+)*\s+commit(\s|$)' || exit 0
git rev-parse --git-dir >/dev/null 2>&1 || exit 0
FALLAS=""
while IFS= read -r f; do
  [ -f "$f" ] || continue
  OUT=$($PY "$CHECK" "$f" </dev/null 2>&1) && continue
  FALLAS+=$(printf '%s\n' "$OUT" | grep -E '\.md:[0-9]+: ' || printf '%s: check_spec.py falló:\n%s' "$f" "$OUT")$'\n'
# --relative: rutas relativas al proyecto (que puede ser una subcarpeta del repo), no a la raíz de git.
done < <({ git -c core.quotePath=false diff --cached --name-only --relative; git -c core.quotePath=false diff --name-only --relative; } 2>/dev/null \
         | grep -E '(^|/)specs/[^/]+\.md$' | sort -u)
[ -z "$FALLAS" ] && exit 0
{ echo "spec-gate: commit bloqueado. Estas specs no pasan check_spec.py:"
  printf '%s' "$FALLAS"
  echo "Corregí cada línea (sumá el VC, el fundamento archivo:línea o el porqué que falta), hacé git add y volvé a commitear."
  echo "Para ver la spec entera: $PY $CHECK <spec>. No lo esquives con otro comando: el commit tiene que llevar specs completas."; } >&2
exit 2
