#!/usr/bin/env bash
# armar.sh — arma el plugin gcsgrep-sdd a partir del toolkit de `TP4 Plugins adn MCP/.claude/`.
#
# Empaquetar es mover archivos. Lo que se escribe a mano está commiteado acá
# (.claude-plugin/plugin.json, .mcp.json, hooks/hooks.json); el resto se copia del
# toolkit para que haya una sola fuente. El resultado también se commitea, para que el
# plugin se pueda leer sin correr nada.
#
#   bash plugin/gcsgrep-sdd/armar.sh        # desde `TP4 Plugins adn MCP/`
#   claude plugin validate plugin/gcsgrep-sdd
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
TK="$AQUI/../../.claude"

rm -rf "$AQUI/skills" "$AQUI/agents"
mkdir -p "$AQUI/skills" "$AQUI/agents" "$AQUI/hooks" "$AQUI/mcp"
cp "$AQUI/../../mcp/register-generation.mjs" "$AQUI/../../mcp/generation-loader.mjs" \
   "$AQUI/../../mcp/start-storage-mcp.mjs" "$AQUI/mcp/"
cp -R "$TK/skills/write-spec-brownfield" "$TK/skills/write-vcs-con-bucket" "$AQUI/skills/"
cp "$TK/agents/spec-reviewer.md" "$TK/agents/lector-bucket.md" "$AQUI/agents/"
cp "$TK/hooks/spec-gate.sh" "$TK/hooks/commit_command.py" \
   "$TK/hooks/gcs-allowlist.sh" "$TK/hooks/gcs_allowlist.py" "$AQUI/hooks/"
find "$AQUI" -name __pycache__ -type d -prune -exec rm -rf {} +

# Lo que cambia al empaquetar: las tools MCP del plugin se llaman
# mcp__plugin_gcsgrep-sdd_gcs__<tool>, no mcp__gcs__<tool>. Sin esto, el allowed-tools
# del skill y las tools del subagent apuntan a tools que no existen (y el subagent
# queda sin ninguna tool). El matcher del hook ya está escrito con el nombre nuevo en
# hooks/hooks.json, y gcs_allowlist.py acepta los dos prefijos.
for f in "$AQUI"/skills/*/SKILL.md "$AQUI"/agents/*.md; do
  sed -i.bak 's/mcp__gcs__/mcp__plugin_gcsgrep-sdd_gcs__/g' "$f" && rm -f "$f.bak"
done
# En el plugin, el bucket llega por userConfig, no por GCSGREP_BUCKET.
sed -i.bak 's/`GCSGREP_BUCKET` en el entorno/la opción `bucket` del plugin (o `GCSGREP_BUCKET`)/' \
  "$AQUI/skills/write-vcs-con-bucket/SKILL.md" && rm -f "$AQUI/skills/write-vcs-con-bucket/SKILL.md.bak"

if grep -rn 'mcp__gcs__' "$AQUI/skills" "$AQUI/agents"; then
  echo "armar.sh: quedaron nombres viejos de tools (arriba)." >&2; exit 1
fi
echo "Plugin armado en $AQUI"
echo "Siguiente: claude plugin validate \"$AQUI\""
