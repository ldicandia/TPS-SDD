#!/usr/bin/env bash
# spec-gate · PreToolUse(Bash|PowerShell). Veta un `git commit` si alguna spec en una carpeta specs/
# que el commit puede llevar no pasa check_spec.py: índice y copia de trabajo.
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
PREFIX=$(git rev-parse --show-prefix) || { echo "spec-gate: no pude resolver la ruta del proyecto; bloqueo el commit." >&2; exit 2; }
FALLAS=""
FILES=()
validar() {
  local fuente=$1 archivo=$2 OUT
  shift 2
  OUT=$($PY "$CHECK" "$@" 2>&1) && return 0
  FALLAS+="[$fuente] "$(printf '%s\n' "$OUT" | grep -E '\.md:[0-9]+: ' || printf '%s: check_spec.py falló:\n%s' "$archivo" "$OUT")$'\n'
}
while IFS= read -r -d '' f; do
  printf '%s\n' "$f" | grep -Eq '(^|/)specs/[^/]+\.md$' || continue
  for previo in "${FILES[@]}"; do [ "$previo" != "$f" ] || continue 2; done
  FILES+=("$f")
  # git show lee el índice aunque el archivo haya sido corregido o borrado del disco.
  # Las entradas ausentes del índice son eliminaciones staged, no specs a validar.
  INDEX_ENTRY=$(git ls-files --stage -- "$f") || { echo "spec-gate: no pude leer el índice; bloqueo el commit." >&2; exit 2; }
  if [ -n "$INDEX_ENTRY" ]; then
    CONTENT=$(git show ":${PREFIX}${f}" 2>/dev/null) || { echo "spec-gate: no pude leer $f del índice (¿conflicto sin resolver?); bloqueo el commit." >&2; exit 2; }
    validar staged "$f" --stdin "$f" <<< "$CONTENT"
  fi
  # Política conservadora para -a y commits con rutas: ambas versiones deben pasar.
  [ ! -f "$f" ] || validar 'copia de trabajo' "$f" "$f" </dev/null
# --relative: rutas relativas al proyecto (que puede ser una subcarpeta del repo), no a la raíz de git.
done < <({ git diff --cached --name-only --relative -z; git diff --name-only --relative -z; } 2>/dev/null)
[ -z "$FALLAS" ] && exit 0
{ echo "spec-gate: commit bloqueado. Estas specs no pasan check_spec.py:"
  printf '%s' "$FALLAS"
  echo "Se validan por separado el contenido staged y la copia de trabajo. Corregir o borrar el archivo del disco no cambia lo que ya está staged."
  echo "Corregí cada línea (sumá el VC, el fundamento archivo:línea o el porqué que falta), hacé git add y volvé a commitear."
  echo "Para ver la spec entera: $PY $CHECK <spec>. No lo esquives con otro comando: el commit tiene que llevar specs completas."; } >&2
exit 2
