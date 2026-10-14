#!/usr/bin/env bash
# postgres-allowlist.sh — PreToolUse sobre las tools MCP del server postgres.
#
# Allowlist, no denylist: deja pasar las tools de lectura que conocemos y veta todo lo
# demás, incluida cualquier tool nueva que traiga la próxima versión del server.
# execute_sql pasa solo si es una única sentencia SELECT (o WITH … SELECT): es el caso
# en que el hook necesita mirar los argumentos, no solo el nombre.
#
# No es un parser de SQL: un "SELECT … INTO nueva_tabla" empieza con SELECT y escribe.
# Por eso es la tercera capa, no la garantía. Las dos de abajo no dependen de este
# archivo: el modo restringido del server y, la que garantiza, el rol turnos_lector.
#
# Sirve igual en .claude/ y en el plugin: el nombre cambia de
#   mcp__postgres__<tool>   a   mcp__plugin_adr-toolkit_postgres__<tool>
set -euo pipefail

INPUT=$(cat)
TOOL=$(jq -r '.tool_name' <<<"$INPUT")
NAME=$(sed -E 's/^mcp__(plugin_adr-toolkit_)?postgres__//' <<<"$TOOL")

case "$NAME" in
  list_schemas|list_objects|get_object_details|explain_query)
    exit 0 ;;
  execute_sql)
    SQL=$(jq -r '.tool_input.sql // ""' <<<"$INPUT")
    # Sin comentarios ni espacios al principio, en minúsculas.
    NORM=$(sed -E 's/--[^\n]*//g' <<<"$SQL" | tr '[:upper:]' '[:lower:]' | tr -s '[:space:]' ' ' | sed -E 's/^ +//; s/[ ;]+$//')
    if [[ "$NORM" =~ ^(select|with)[[:space:]] && "$NORM" != *";"* ]]; then
      exit 0
    fi
    echo "execute_sql bloqueado: solo una sentencia SELECT. Si la decisión necesita escribir, va como migración en migrations/ para revisar en el MR." >&2
    exit 2 ;;
esac

echo "$TOOL no está en la allowlist de este toolkit (lectura de schema y planes). Si hace falta, revisá la tool y agregala acá a propósito." >&2
exit 2
