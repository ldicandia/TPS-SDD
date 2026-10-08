# TP3 — Toolkit SDD: specs brownfield que no salen con huecos

Un skill, un subagent y un hook que encodean cómo especificamos un cambio sobre código
existente. Lo armamos a partir de los defectos que nos marcaron en las correcciones del
TP1 y del TP2:

- **TP2, VE-5 en 0:** la decisión 3 se fundaba en "lo pide la consigna" y no en código de tmux.
- **TP1:** el VC-23 no tenía los datos necesarios para dar su resultado, y la spec usaba "trozo" y "tramo" para lo mismo.
- **TP1 y TP2:** alcance futuro y plan de iteraciones mezclados dentro de la spec.

**Agente declarado:** Claude Code (probado con la 2.1.292). El toolkit vive en
[`TP3 Skills & Agents/.claude/`](../.claude/). **El proyecto es la carpeta
`TP3 Skills & Agents/`**: Claude Code carga skills, subagents y hooks del `.claude/` de la
carpeta donde abrís la sesión, así que hay que correr `claude` desde ahí. El código que
especifica la evidencia (gcsgrep) está fuera, en `../TP1 Greenfield/Tarea/`, y se le da
acceso con `--add-dir`.

Todas las rutas de este README son relativas a `TP3 Skills & Agents/`.

## Las tres piezas

| Pieza | Archivo | Qué hace | Concepto de L1–L2 | Cuándo la usan |
|---|---|---|---|---|
| 📘 Skill `write-spec-brownfield` | [`.claude/skills/write-spec-brownfield/SKILL.md`](../.claude/skills/write-spec-brownfield/SKILL.md) + [`plantilla.md`](../.claude/skills/write-spec-brownfield/plantilla.md) + [`scripts/check_spec.py`](../.claude/skills/write-spec-brownfield/scripts/check_spec.py) | Arma `specs/<slug>.md` desde una plantilla que exige: base (hash), alcance dentro/fuera, invariantes con comando, cada FR en Dado/Cuando/Entonces con su `VC-FR-N` y cada decisión con `archivo:línea`. Un script valida todo eso y genera la tabla de trazabilidad. | **Cobertura de VCs** y **alcance acotado**; también **spec antes que código** y spec anclada a una revisión del código (brownfield, L2). | Cuando alguien pide especificar un cambio sobre código que ya existe, antes de implementarlo ("especificá…", "armá la spec antes de tocar código"). Carga sola. |
| 👥 Subagent `spec-reviewer` | [`.claude/agents/spec-reviewer.md`](../.claude/agents/spec-reviewer.md) | Revisor de solo lectura (`tools: Read, Grep, Glob`). Abre cada `archivo:línea` que cita la spec, comprueba que los datos de cada VC alcancen para dar el resultado y devuelve un veredicto cerrado `READY` / `NEEDS WORK`, con hallazgos `spec:línea` y evidencia `archivo:línea`. | **Gate independiente**: quien revisa no es quien escribió. También **higiene de contexto**: las lecturas de código quedan en la ventana del subagent. | Lo lanza el skill en su paso 9. También cuando alguien pregunta "¿está lista esta spec?" o "revisala". |
| 🪝 Hook `spec-gate` | [`.claude/hooks/spec-gate.sh`](../.claude/hooks/spec-gate.sh) + [`commit_command.py`](../.claude/hooks/commit_command.py), registrados en [`.claude/settings.json`](../.claude/settings.json) | `PreToolUse` con matcher `Bash\|PowerShell`. Analiza invocaciones directas de Git respetando comillas, veta commits compuestos o dirigidos a otro repo y valida por separado el contenido del índice y la copia de trabajo. Si la política o el checker fallan, sale con `exit 2` y explica qué corregir. | **Cobertura de VCs**: aplica la validación estructural al contenido staged y conserva el control de la copia de trabajo, dentro de la gramática documentada abajo. | Corre en cada comando de shell del agente; chequea los commits directos que reconoce. |

### Por qué cada pieza está en ese recurso

- **Skill:** especificar es un flujo que repetimos en el TP1 y el TP2, y solo hace falta cuando aparece esa situación. Por eso carga con la `description` y no ocupa contexto en cada sesión. Lo determinístico (que cada FR tenga su VC, que cada decisión tenga ancla, la tabla de trazabilidad) lo hace `check_spec.py`, no el modelo.
- **Subagent:** su valor es la **independencia**. Si la sesión que escribió la spec también la revisa, hereda sus supuestos. Además, verificar anclas es trabajo ruidoso. En la evidencia 01, el revisor hizo 8 llamadas a herramientas y usó 34.816 tokens en su ventana, y la sesión principal recibió solo el informe (unos 7.500 caracteres). Lleva `tools: Read, Grep, Glob` para que el "no edites" lo garantice la configuración y no solo el brief. No lleva `Bash`, y por eso no ejecuta los VCs: verifica leyendo.
- **Hook:** el skill pide la cobertura de VCs y el revisor la revisa. El hook bloquea los commits que detecta si las specs examinadas no pasan el checker, incluso cuando una copia de trabajo corregida oculta una versión staged inválida.

### Cómo componen

`write-spec-brownfield` llama a `check_spec.py` en el paso 8 y lanza `spec-reviewer` en el
paso 9. `spec-gate` corre el mismo `check_spec.py` en el commit, así que la regla que hace
cumplir el hook es la misma que pide el skill: una sola fuente de verdad.

## Instalación

Las tres piezas ya están en `TP3 Skills & Agents/.claude/`: alcanza con abrir `claude`
desde `TP3 Skills & Agents/`. Para instalarlas en otro proyecto, copiá estos archivos con
la misma estructura dentro de la carpeta donde se abre la sesión:

```text
.claude/skills/write-spec-brownfield/   (SKILL.md, plantilla.md, scripts/check_spec.py)
.claude/agents/spec-reviewer.md
.claude/hooks/spec-gate.sh
.claude/hooks/commit_command.py          (clasificación de comandos, sin ejecutarlos)
.claude/settings.json                   (si ya tenés uno, sumá el bloque hooks.PreToolUse)
.claude/.gitattributes                  (fuerza LF en .sh y .py; con CRLF, bash no corre el hook)
```

**Dependencias:**

- `bash` y `git`. En Windows, el bash que trae Git for Windows.
- Python ≥ 3.8 accesible como `python3`, `python` o `py -3`. El hook prueba los tres en ese orden.
- No hace falta `jq`: el JSON del evento se parsea con Python.
- Ningún paquete de pip.

**Probado en:** Windows 11 Pro, Git Bash 5.2.37 y Python 3.14 (vía `py`). En Linux y macOS
tendría que bastar con `python3`. La corrección de validación del índice se probó en
macOS con Bash 3.2 y Python 3.14 mediante las 12 regresiones de evidencia 08;
esa corrección aún no se volvió a ejecutar dentro de Claude Code en Windows.
La corrección de comandos se verificó con 23 tests en macOS (evidencia 09).
Incluyen eventos etiquetados PowerShell alimentados por stdin al hook; no prueban
una sesión nativa de PowerShell ni Claude Code en Windows.

**Bit de ejecución:** en Windows git no lo registra solo. Al commitear el toolkit, corré
desde la raíz del repo:

```bash
git add --chmod=+x "TP3 Skills & Agents/.claude/hooks/spec-gate.sh" "TP3 Skills & Agents/.claude/skills/write-spec-brownfield/scripts/check_spec.py"
```

El registro invoca `bash <script>`, así que el hook corre aunque falte el bit.

**Comprobar que quedó instalado:** abrí `claude` en `TP3 Skills & Agents/` y mirá `/hooks`,
que tiene que listar `PreToolUse · Bash|PowerShell`, y `/agents`, que tiene que listar
`spec-reviewer`.

## Qué bloquea el hook, exactamente

| Caso | Resultado |
|---|---|
| `git commit …` con una spec en `specs/` (staged o modificada) cuyo índice o copia de trabajo no pasa `check_spec.py` | `exit 2` y stderr con `[staged]` / `[copia de trabajo]` y `archivo:línea: problema — qué hacer` |
| Spec inválida staged, corregida o borrada del disco sin actualizar el índice | `exit 2`: Git conserva el contenido inválido staged |
| Spec corregida y vuelta a stagear; ambas versiones válidas | `exit 0` |
| Eliminación staged de una spec, sin archivo recreado en disco | `exit 0`: el índice ya no contiene esa spec |
| `git commit -am`, `git -C . commit`, `git -C "/ruta con espacios" commit`, `git --no-pager commit` | Valida ambas versiones y bloquea si alguna spec es inválida; `-C` debe apuntar al mismo repositorio |
| `git add … && git commit …`, `cd x && git commit …`, o commit junto con otras operaciones | `exit 2`, aun con specs válidas: pedí llamadas separadas para inspeccionar el índice después del `add` |
| `git -C <otro-repo> commit` o evento con `cwd` de otro repositorio | `exit 2`: requiere una sesión y un hook en ese otro proyecto |
| `echo "git commit"`, `git log --grep commit` | `exit 0`: son menciones, no invocaciones de commit |
| El mismo commit lanzado con la herramienta PowerShell en vez de Bash | `exit 2` |
| `git commit` con todas las specs bien, o sin specs tocadas | `exit 0` |
| Cualquier comando que no sea un commit (`git status`, `pytest`, `ls`, …) | `exit 0`, aunque haya una spec rota |
| Evento ilegible, falta Python o no se puede entrar al proyecto | `exit 2` con el motivo (falla cerrada) |

Tarda unos 0,5 s por comando de shell en Windows y 0,75 s en un commit.
Estas mediciones son anteriores a las correcciones del índice y de los comandos;
ahora se comprueba el repositorio de destino y puede ejecutarse el checker dos veces
por spec. La evidencia 09 registra el tiempo de la suite, no una medición por commit.

**Gramática de comandos soportada:** una invocación directa de `git commit`, con
opciones de commit, argumentos literales y comillas simples o dobles. Antes de
`commit` se admite `-C <ruta>` (también repetido), `--no-pager`, `--paginate`,
`--literal-pathspecs` y `--no-optional-locks`. `-C` se resuelve desde el `cwd` del
evento, o desde el proyecto si el evento no declara uno, y debe conservar el mismo
repo. Los separadores fuera de comillas (`&&`, `;`, pipes, redirecciones, paréntesis
y saltos de línea entre operaciones) bloquean un comando que incluye un commit.
Los separadores dentro del mensaje del commit se tratan como texto.
Los overrides `-c`, variables de entorno antepuestas, opciones globales desconocidas
y rutas `-C` con variables/expresiones se rechazan para los commits detectados.
El mensaje de bloqueo indica la alternativa: llamadas independientes y rutas
literales. El clasificador nunca ejecuta el comando recibido.

**Política para `commit -a` y commits con rutas:** se validan conservadoramente las
dos versiones de todas las specs staged o modificadas dentro del proyecto, sin
intentar calcular la selección exacta de esos comandos. Un índice inválido bloquea
aunque `-a` o una ruta fueran a reemplazarlo por una copia de trabajo válida. Una
copia de trabajo inválida también bloquea un commit normal con índice válido.
Para continuar, corregí la spec y sincronizá el índice con `git add`; si la eliminás,
stageá la eliminación con `git add -u`. El hook solo lee: nunca cambia el índice.

**Límites conocidos:**

- No es un git hook: un `git commit` que hace una persona en su terminal no pasa por él. Su trabajo es ser el guardrail del agente.
- Solo chequea archivos `.md` dentro de una carpeta `specs/` **dentro del proyecto** (`git diff --relative`). Las specs del TP1 y del TP2, con otro formato y fuera de esta carpeta, no se tocan.
- No es un intérprete completo de Bash o PowerShell: no se garantiza detectar commits ocultos en aliases, funciones, scripts o invocaciones indirectas como `bash -c '…'`. Para esas formas hace falta un git hook adicional; usá las invocaciones directas documentadas.
- En Windows, para `-C` usá rutas literales entre comillas con `/` (`C:/ruta con espacios`). Las correcciones nuevas aún no tienen una corrida nativa allí.

### Dos defectos que encontró la evidencia (y cómo quedaron)

- **Bypass por otro tool.** En Windows, Claude Code tiene una herramienta PowerShell además de Bash. En una corrida, el agente commiteó con PowerShell y el hook, que entonces tenía matcher `Bash`, no se enteró. El matcher pasó a `Bash|PowerShell`, que reciben el mismo `tool_input.command`. Las sesiones 05–07 se volvieron a correr con esa versión.
- **Falso positivo de `check_spec.py`.** Con `re.I`, la palabra "todo" ("con todo el prefijo") se marcaba como un `TODO` pendiente. Ahora `TBD`/`TODO` solo cuentan en mayúsculas.

## Evidencia

Todas son sesiones nuevas de `claude -p --output-format stream-json --verbose`, abiertas
desde `TP3 Skills & Agents/`. El JSONL crudo está en [`evidencia/raw/`](evidencia/raw/), y
la transcripción legible se generó con [`evidencia/transcribir.py`](evidencia/transcribir.py).
Ninguna sesión commiteó en este repo. El bloqueo y el commit que pasa (05–07) corrieron en
un **clon descartable** del repo con el toolkit copiado.

| # | Qué muestra | Archivo |
|---|---|---|
| 01 | **Skill disparando solo** con un pedido que no lo nombra. Lee el código de gcsgrep, escribe [`evidencia/specs/gcsgrep-count.md`](evidencia/specs/gcsgrep-count.md), corre `check_spec.py` y **lanza `spec-reviewer`**. El revisor devuelve `## Veredicto: READY` con 5 hallazgos `MENOR` y las anclas verificadas, después de 8 llamadas a herramientas dentro del subagent. La sesión principal corrige los menores y vuelve a chequear. | [`01-skill-y-subagent.md`](evidencia/01-skill-y-subagent.md) |
| 02 | Segunda frase que dispara el skill (`→ Skill write-spec-brownfield` como primera acción). Cortada a 3 turnos. | [`02-trigger-positivo.md`](evidencia/02-trigger-positivo.md) |
| 03 | Frase parecida que **no** tiene que disparar ("revisá la spec…"): el skill no carga y la sesión se pone a leer la spec y el código. Cortada a 3 turnos. | [`03-trigger-negativo-revisar.md`](evidencia/03-trigger-negativo-revisar.md) |
| 04 | Pregunta sobre una spec ("¿qué dice la spec del TP1 sobre los exit codes?"): el skill no carga. | [`04-trigger-negativo-pregunta.md`](evidencia/04-trigger-negativo-pregunta.md) |
| 05 | **El hook bloquea un commit.** En la spec staged faltaba `VC-FR-3` y D-2 se fundaba en "lo decidimos así en el equipo". El agente intenta `git commit`, recibe `exit 2` con el stderr y no lo esquiva: explica las dos líneas y pide confirmación antes de inventar el fundamento. `git log` sigue en `b28ad1f`. | [`05-hook-bloquea.md`](evidencia/05-hook-bloquea.md) · [`raw/05-git-log.txt`](evidencia/raw/05-git-log.txt) |
| 06 | **El agente corrige con el stderr y el commit pasa.** Es la misma sesión retomada: agrega el VC, ancla D-2 a `src/gcsgrep/cli.py:96`, `check_spec.py` da OK, vuelve a commitear y el hook deja pasar el commit (`b4c1ad5`). | [`06-hook-corrige-y-pasa.md`](evidencia/06-hook-corrige-y-pasa.md) · [`raw/05-git-log.txt`](evidencia/raw/05-git-log.txt) |
| 07 | Reproducción del §7 alimentando el hook por stdin. Condición mala: `exit 2` en las cinco variantes de commit y con PowerShell. Comandos que no son commit: `exit 0`. Evento malformado: `exit 2`. Condición buena: `exit 0`. | [`07-hook-reproduccion.txt`](evidencia/07-hook-reproduccion.txt) |
| 08 | Regresiones de la corrección del índice: bloquea specs staged inválidas aunque se corrijan o borren del disco; permite volver a stagear la corrección y eliminar una spec del índice; mantiene la política conservadora para `-a`, rutas y eventos PowerShell. Cada caso usa un repo temporal y comprueba que el hook no altere el índice. Es ejecución directa del hook, sin una sesión nueva de Claude. | [`08-hook-indice.txt`](evidencia/08-hook-indice.txt) · [`tests/test_spec_gate.py`](tests/test_spec_gate.py) |
| 09 | Regresiones de los comandos, incluidas las 12 del índice: rutas `-C` entre comillas, commits compuestos con specs nuevas, destino externo, menciones que no deben disparar y mensajes con operadores como texto. Guarda la salida real y hashes de los archivos probados; cada caso comprueba que el hook no cambie el árbol del índice. | [`09-hook-comandos.txt`](evidencia/09-hook-comandos.txt) · [`tests/test_spec_gate.py`](tests/test_spec_gate.py) |

Las sesiones 01–04 corrieron antes de los dos arreglos de arriba. Ninguna intentó un commit,
y la spec de 01 da OK también con el `check_spec.py` actual.
Las evidencias 05–07 también son anteriores a la corrección del índice; se conservan
como historial. La evidencia 08 verifica la corrección del índice y la 09 ambas
correcciones. Las evidencias 08–09 son tests directos, no sesiones de Claude Code.

### Casos de trigger del skill (como VCs)

| Frase (sesión nueva) | ¿Tiene que disparar? | Resultado |
|---|---|---|
| "Quiero sumarle a gcsgrep … un flag -c / --count … Antes de tocar código necesito la spec del cambio" | Sí | Cargó `write-spec-brownfield` (01) |
| "Antes de tocar código, armame la spec para que gcsgrep acepte varios prefijos gs://" | Sí | Cargó `write-spec-brownfield` (02) |
| "Revisá la spec de tarea/evidencia/specs/gcsgrep-count.md y decime si está lista para implementar" | No | No cargó (03) |
| "¿Qué dice la spec del TP1 … sobre los exit codes de gcsgrep?" | No | No cargó; respondió con un Grep (04) |

### Reproducir

Desde `TP3 Skills & Agents/`, con `claude` instalado:

```bash
# Skill + subagent (sesión nueva, sin nombrar el skill)
claude -p 'Quiero sumarle a gcsgrep (el CLI que está en ../TP1 Greenfield/Tarea) un flag -c / --count … Antes de tocar código necesito la spec del cambio.' --add-dir "../TP1 Greenfield/Tarea"

# Hook, sin agente: condición mala y buena
SPEC=tarea/evidencia/specs/gcsgrep-count.md
EVENT='{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git commit -m prueba"}}'
cp "$SPEC" /tmp/spec.bak && sed -i '/^- \*\*VC-FR-1\*\*/d' "$SPEC"
echo "$EVENT" | CLAUDE_PROJECT_DIR="$PWD" bash .claude/hooks/spec-gate.sh; echo "exit=$?"   # exit=2
cp /tmp/spec.bak "$SPEC"
echo "$EVENT" | CLAUDE_PROJECT_DIR="$PWD" bash .claude/hooks/spec-gate.sh; echo "exit=$?"   # exit=0

# Chequeo directo de una spec
py -3 .claude/skills/write-spec-brownfield/scripts/check_spec.py tarea/evidencia/specs/gcsgrep-count.md

# Regresiones del índice: crean y eliminan repositorios temporales
python3 -m unittest discover -s tarea/tests -v  # Windows: py -3 en lugar de python3
```

La condición mala necesita que la spec figure como modificada para git, es decir, que esté
commiteada. Si todavía no lo está, stageala (`git add`) antes del `sed`.
