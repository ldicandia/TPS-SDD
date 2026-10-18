#!/usr/bin/env bash
# ralph.sh — el loop de Ralph (Geoffrey Huntley), con techo.
#
# El original es una línea:   while :; do cat PROMPT.md | claude ; done
# Esta versión es la misma idea con los límites que la clase pide para dejarlo correr:
#
#   - Un directorio de trabajo propio, con git: cada vuelta deja un commit y se puede
#     volver atrás. Nunca corre sobre tu repo.
#   - Un techo de vueltas (MAX_VUELTAS) y de gasto por vuelta (--max-budget-usd).
#   - Permisos justos: edita archivos y corre pytest y git, nada más. Sin
#     --dangerously-skip-permissions, y sin servers MCP (--strict-mcp-config): un loop
#     desatendido no carga integraciones que nadie aprobó (Lección 4, la trifecta).
#   - --setting-sources project: solo la configuración del proyecto, no la de tu usuario.
#     Sin esto, `claude -p` corre los hooks que tengas configurados — en la prueba de este
#     script, unos hooks del usuario dejaron archivos que terminaron commiteados por el
#     loop. (Con una API key, `--bare` es todavía más limpio; con login de suscripción no
#     anda, porque saltea la lectura de credenciales.)
#   - Termina solo cuando el agente escribe RALPH_DONE y la suite está verde de verdad:
#     la palabra del modelo no alcanza, la verifica el script.
#   - Contrapresión: si una vuelta deja la suite roja, la siguiente arranca sabiéndolo.
#
#   ./ralph.sh /tmp/taskcli-ralph            # arma el directorio y corre
#   MAX_VUELTAS=3 ./ralph.sh /tmp/taskcli-ralph
set -euo pipefail

DIR="${1:?Uso: ./ralph.sh <directorio-de-trabajo>}"
MAX_VUELTAS="${MAX_VUELTAS:-20}"
USD_POR_VUELTA="${USD_POR_VUELTA:-1.50}"
AQUI="$(cd "$(dirname "$0")" && pwd)"
SPEC="$AQUI/../../../01-greenfield/ejemplo-guiado/taskcli-spec.md"

# 1 · Preparar el directorio: spec, plan y prompt; y git para poder auditar y volver atrás.
if [[ ! -d "$DIR/.git" ]]; then
  mkdir -p "$DIR/specs"
  cp "$AQUI/PROMPT.md" "$AQUI/AGENT.md" "$AQUI/fix_plan.md" "$DIR/"
  cp "$SPEC" "$DIR/specs/taskcli-spec.md"
  git -C "$DIR" init -q
  git -C "$DIR" add -A
  git -C "$DIR" -c user.name=ralph -c user.email=ralph@localhost commit -qm "Vuelta 0: spec, plan y prompt"
fi
cd "$DIR"
mkdir -p .ralph

# Un entorno propio con pytest: el agente no instala nada (no tiene permiso para hacerlo).
if [[ ! -x .venv/bin/python3 ]]; then
  if command -v uv >/dev/null; then uv venv -q .venv && uv pip install -q --python .venv/bin/python3 pytest
  else python3 -m venv .venv && .venv/bin/pip install -q pytest; fi
  printf '.venv/\n.ralph/\n__pycache__/\n.pytest_cache/\n' > .gitignore
fi
export PATH="$DIR/.venv/bin:$PATH"   # python3 -m pytest usa el del venv

suite_verde() { python3 -m pytest -q >/dev/null 2>&1; }

for ((v = 1; v <= MAX_VUELTAS; v++)); do
  echo "── Vuelta $v / $MAX_VUELTAS · $(grep -c '^- \[ \]' fix_plan.md) ítems pendientes"

  # 2 · Una vuelta = un contexto nuevo. El estado está en disco, no en la conversación.
  claude -p "$(cat PROMPT.md)" \
    --setting-sources project \
    --permission-mode acceptEdits \
    --allowedTools "Read" "Edit" "Write" "Glob" "Grep" \
                   "Bash(python3 -m pytest:*)" "Bash(python3 -m taskcli:*)" \
                   "Bash(git add:*)" "Bash(git commit:*)" "Bash(git status:*)" "Bash(git diff:*)" \
    --max-budget-usd "$USD_POR_VUELTA" \
    --strict-mcp-config \
    --output-format text \
    < /dev/null > ".ralph/vuelta-$v.log" 2>&1 || true

  tail -n 3 ".ralph/vuelta-$v.log"

  # 3 · La contrapresión la mide el script, no el modelo.
  if suite_verde; then
    echo "   suite: verde"
  else
    echo "   suite: ROJA — la próxima vuelta tiene que arreglarla antes de seguir"
    printf '\n- [ ] La vuelta %s dejó la suite roja: arreglarla antes de seguir (sin tocar los tests)\n' "$v" >> fix_plan.md
  fi

  # 4 · Terminar solo con las dos condiciones: el agente dice que terminó y la suite lo confirma.
  if grep -q '^RALPH_DONE$' ".ralph/vuelta-$v.log" && suite_verde && ! grep -q '^- \[ \]' fix_plan.md; then
    echo "✓ Terminado en $v vueltas. Revisá el log: git log --oneline"
    exit 0
  fi
done

echo "✗ Se alcanzó el techo de $MAX_VUELTAS vueltas sin terminar. Revisá fix_plan.md y .ralph/."
exit 1
