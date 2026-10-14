#!/usr/bin/env bash
# armar.sh — arma el plugin adr-toolkit a partir de los ejemplos guiados de L3 y L4.
#
# Convertir un toolkit en plugin es mover archivos (Lección 4, "¿Qué es un plugin?"),
# así que este script los copia en vez de duplicarlos en el repo. Lo que sí está
# commiteado acá es lo que cambia al empaquetar: el manifiesto, el .mcp.json con la
# credencial por userConfig y hooks/hooks.json con los matchers nuevos.
#
#   ./armar.sh
#   claude plugin validate .
#   claude --plugin-dir .            # probarlo sin publicar nada
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
L3="$AQUI/../../../../03-skills/ejemplo-guiado"
L4="$AQUI/../.."

rm -rf "$AQUI/skills" "$AQUI/agents"
mkdir -p "$AQUI/skills" "$AQUI/agents"

cp -R "$L3/skills/write-adr" "$L3/skills/supersede-adr" "$AQUI/skills/"
cp -R "$L4/skills/write-adr-con-datos" "$AQUI/skills/"
cp "$L3/subagents/adr-explorer.md" "$L3/subagents/adr-reviewer.md" "$AQUI/agents/"
cp "$L4/subagents/muestreador-texto.md" "$AQUI/agents/"
cp "$L3/hooks/adr-immutable.sh" "$L3/hooks/adr-for-deps.sh" "$L3/hooks/adr-index.sh" \
   "$L4/hooks/postgres-allowlist.sh" "$AQUI/hooks/"
chmod +x "$AQUI"/hooks/*.sh

# Lo que cambia al empaquetar (2): las tools MCP del plugin cambian de nombre.
# mcp__postgres__X pasa a mcp__plugin_adr-toolkit_postgres__X. Sin esto, el
# allowed-tools del skill y el tools del subagent apuntan a tools que no existen.
for f in "$AQUI"/skills/*/SKILL.md "$AQUI"/agents/*.md; do
  sed -i.bak 's/mcp__postgres__/mcp__plugin_adr-toolkit_postgres__/g' "$f" && rm -f "$f.bak"
done

echo "Plugin armado en $AQUI"
echo "Siguiente: claude plugin validate \"$AQUI\""
