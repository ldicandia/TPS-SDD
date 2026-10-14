#!/usr/bin/env bash
# gcs-allowlist · PreToolUse(mcp__gcs__.* | mcp__plugin_gcsgrep-sdd_gcs__.*).
# La decisión está en gcs_allowlist.py; esto solo encuentra Python (>= 3.8) y falla
# cerrado si no hay. Sin jq: el JSON del evento lo parsea Python, como en spec-gate.
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY=""; for c in python3 python "py -3"; do $c -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1 && { PY=$c; break; }; done
[ -n "$PY" ] || { echo "gcs-allowlist: no encontré Python >= 3.8; bloqueo la tool del bucket." >&2; exit 2; }
exec $PY "$AQUI/gcs_allowlist.py"
