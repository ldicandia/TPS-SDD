# Ejemplo guiado — Lección 5 · Soltar el volante

**El caso:** `taskcli`, el CLI de tareas del ejemplo guiado de la Lección 1. Ya tiene lo
que un agente autónomo necesita para trabajar sin que lo mires: una spec con 15 VCs
([`taskcli-spec.md`](../../01-greenfield/ejemplo-guiado/taskcli-spec.md)) y un plan de
cuatro iteraciones ([`taskcli-plan.md`](../../01-greenfield/ejemplo-guiado/taskcli-plan.md)).

Acá lo construye un **loop**, sin un humano en cada paso. Tres demos, de lo más crudo a
lo más gobernado:

| Demo | Qué muestra | Dónde corre |
|---|---|---|
| 1 · Ralph acotado | El loop de Huntley con techo: contexto fresco por vuelta, un ítem por vuelta, la suite como contrapresión | Tu máquina, en un directorio aparte |
| 2 · Flow-Next | El loop con gates: spec con criterios numerados, review cruzado, receipts | Tu máquina, como plugin |
| 3 · Cloud y background | El mismo trabajo en una VM, mientras hacés otra cosa | La nube del proveedor, o en background local |

Los comandos de este documento están verificados contra Claude Code 2.1.286 (`claude
--help`) y la documentación de cada herramienta, en octubre de 2026. Cambian rápido:
antes de dar la clase, corré `--help` y mirá los changelogs.

## Qué hay acá

| Archivo | Qué es |
|---|---|
| [`ralph/ralph.sh`](./ralph/ralph.sh) | El loop de Ralph con techo de vueltas, de gasto y de permisos |
| [`ralph/PROMPT.md`](./ralph/PROMPT.md) | Lo que se le da al agente en cada vuelta, siempre igual |
| [`ralph/fix_plan.md`](./ralph/fix_plan.md) | El estado entre vueltas: el plan de L1 convertido en checklist de VCs |
| [`ralph/AGENT.md`](./ralph/AGENT.md) | Cómo se construye y se prueba; el agente le agrega lo que aprende |
| [`checklist.md`](./checklist.md) | "¿Lo dejarías correr de noche?" — el ejercicio de la clase |

## Demo 1 · Ralph acotado

El original de Geoffrey Huntley ([ghuntley.com/ralph](https://ghuntley.com/ralph/),
14/07/2025) es una línea:

```bash
while :; do cat PROMPT.md | claude-code ; done
```

Funciona por cuatro cosas que ya vieron en la materia, aunque no con estos nombres:

| Ralph | En la materia |
|---|---|
| `specs/` y `PROMPT.md` se cargan iguales en cada vuelta | La spec como fuente de verdad fuera del chat (L1) |
| `fix_plan.md`: el plan priorizado, que el agente mantiene | El plan de iteraciones (L1) |
| Un ítem por vuelta, contexto fresco cada vez | Economía de contexto y re-anclar (L4) |
| Tests, tipos y linters que rechazan lo malo ("backpressure") | Los VCs y los hooks que garantizan (L1, L3) |

`ralph.sh` es esa línea con los techos que pide la clase:

```bash
cd ralph
MAX_VUELTAS=5 USD_POR_VUELTA=1.50 ./ralph.sh /tmp/taskcli-ralph
```

Qué mirar mientras corre:

1. **Cada vuelta es un `claude -p` nuevo.** No hay conversación que crezca. Lo que una
   vuelta sabe de las anteriores está en `fix_plan.md`, en `AGENT.md` y en el código.
2. **Un commit por VC.** `git log --oneline` en el directorio de trabajo cuenta la
   historia: `VC-7: …`, `VC-1: …`, `VC-9: …`.
3. **La contrapresión la mide el script.** Si la suite queda roja, `ralph.sh` lo escribe
   en `fix_plan.md` y la próxima vuelta lo arregla primero. Que el modelo diga "terminé"
   (`RALPH_DONE`) no alcanza: el script lo verifica.
4. **Los permisos son los justos.** Editar, `pytest`, `git add/commit`. No puede instalar
   nada ni salir a la red por Bash. Sin `--dangerously-skip-permissions`.

Lo que pasó al probarlo, y vale contarlo en clase:

- **Sin pytest instalado**, la primera vuelta no pudo correr la suite. No inventó un
  verde: dijo que estaba trabada y por qué. La contrapresión funcionó, y el arreglo fue del
  script (prepara un entorno con pytest), no del prompt.
- **Los hooks del usuario se metieron en el loop.** `claude -p` cargaba la configuración
  del usuario que lo corría, y unos hooks dejaron archivos que el agente commiteó con
  `git add -A`. Por eso `ralph.sh` usa `--setting-sources project` y
  `--strict-mcp-config`. Es lo de la Lección 4 en otra forma: en modo no interactivo, lo
  que está configurado corre sin preguntar.

### El plugin oficial, y por qué no es lo mismo

Anthropic publicó el loop como plugin: `ralph-wiggum`, renombrado **`ralph-loop`** en el
marketplace oficial (enero de 2026).

```
/ralph-loop "Implementá taskcli según specs/… Escribí <promise>RALPH_DONE</promise> al terminar." --completion-promise "RALPH_DONE" --max-iterations 20
/cancel-ralph
```

Funciona con un **Stop hook** que, cuando Claude quiere terminar, le devuelve el mismo
prompt **dentro de la misma sesión**. Es la crítica que le hacen (issue #125 de
`claude-plugins-official`): el contexto crece y los intentos fallidos quedan en la
ventana, cuando la idea de Huntley era empezar limpio cada vuelta. Y `--max-iterations` no
tiene límite por defecto: el README del plugin lo recomienda como la red de seguridad
principal.

Claude Code trae además `/goal <condición>`: un Stop hook en el que un modelo chico decide,
después de cada turno, si la condición se cumplió.

## Demo 2 · Flow-Next: el loop con gates

[Flow-Next](https://flow-next.dev/) (Gordon Mickel, MIT) lleva "un bug, una idea o un
ticket a un pull request verificado". Es Ralph con todo lo que Ralph deja librado al
prompt, convertido en gates:

| Flow-Next | Lo que ya conocen |
|---|---|
| `.flow/specs/<id>.md` con criterios de aceptación numerados | La spec con FR y VC (L1) |
| Tasks con re-anclaje: cada tarea relee spec y estado | Un ítem por vuelta, contexto fresco |
| Review cruzado entre modelos según el riesgo, hasta *SHIP* | `review-spec` y los subagents revisores (L3) |
| Receipts: cada decisión, review y QA queda registrado en el repo | La evidencia con procedencia (L4) |
| `--auto` sigue solo hasta el punto de decisión humana | El gate humano que no se saltea |

```
/plugin marketplace add https://github.com/gmickel/flow-next
/plugin install flow-next
/reload-plugins
/flow-next:setup

/flow-next:flow "taskcli: agregar `taskcli done` según specs/taskcli-spec.md (FR-4, FR-5)"
/flow-next:flow "…" --auto        # sin supervisión, hasta un punto de decisión humana
```

Un dato para la clase: Flow-Next **tuvo** un "Ralph mode" (bash externo, un `claude -p`
nuevo por iteración, bloqueo de la tarea tras 5 fallos) y lo **eliminó en la v7.0.0**
(1/10/2026): "`/flow-next:flow --auto` is the one unattended mode". El loop crudo terminó
absorbido por un flujo con gates. Ese es el arco de la clase.

## Demo 3 · Cloud y background

El mismo pedido, sin que ocupe tu terminal:

```bash
# Una sesión en la nube: una VM clona el repo de GitHub en tu rama actual
claude --cloud "Implementá VC-4 y VC-5 de taskcli según specs/taskcli-spec.md"

# Traerla a tu terminal cuando termine (git limpio, mismo repo)
claude --teleport            # o /teleport dentro de una sesión

# En tu máquina, pero en background
claude --bg "…"              # imprime un id
claude agents                # lista las sesiones en background
claude attach <id>           # la abre en esta terminal
claude logs <id>             # o solo mirá su salida
```

| Herramienta | Cómo se le delega | Dónde corre | Qué devuelve |
|---|---|---|---|
| Claude Code en la nube | `claude --cloud "…"`, o claude.ai/code | VM con red **None**, **Trusted** (por defecto), **Full** o **Custom** | Rama y PR; `/autofix-pr` vigila CI y comentarios |
| Codex cloud | `codex cloud exec --env <id> --attempts 1-4 "…"` | VM; sin internet en la fase del agente salvo que se habilite | Commit o PR; `--attempts` = best-of-N |
| Copilot cloud agent | Asignarle un issue | GitHub Actions, máximo 59 minutos | PR en **draft** en una rama `copilot/` |
| Jules | Prompt sobre un repo y una rama | VM | **Primero un plan que aprobás**, después rama o PR |
| Cursor Cloud Agents | Editor, web, Slack, PRs, Linear | VM aislada | PR en una rama aparte |

Lo que conviene mostrar, más que la lista: **dónde está el gate humano en cada una.** Copilot
no puede pasar su PR a "ready" ni aprobarlo, y quien lo pidió tampoco puede aprobarlo.
Jules pide aprobar el plan antes de tocar código. Codex en la nube no tiene internet
mientras trabaja salvo que se lo des.

### Lo que corre sin que nadie apruebe

- `claude -p` en un repo carga sus hooks de `.claude/settings.json` y sus servers de
  `.mcp.json` **sin diálogo de confianza ni aprobación por server** (documentación de
  modo headless). Un repo ajeno con `claude -p` es código ajeno corriendo.
- Las **routines** de Claude Code (en preview) corren en la nube por schedule, por API o
  por eventos de GitHub, sin selector de permisos.
- `bypassPermissions` / `--dangerously-skip-permissions`: la documentación lo marca para
  contenedores o VMs aislados, nada más.

## Advertencia, esta va en serio

Un loop autónomo gasta, escribe y commitea solo. **Siempre** con techo de vueltas y de gasto,
en un directorio o una rama aparte, con los permisos justos, y nunca con credenciales que no
le darías a un desconocido. `ralph.sh` no corre sobre tu repo: arma uno nuevo.
