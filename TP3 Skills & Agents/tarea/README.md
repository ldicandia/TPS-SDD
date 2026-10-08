# TP3 — Toolkit SDD: specs brownfield que no salen con huecos

Un skill, un subagent y un hook que encodean cómo especificamos un cambio sobre código
existente. Lo armamos a partir de los defectos que nos marcaron en las correcciones del
TP1 y del TP2:

- **TP2, VE-5 en 0:** la decisión 3 se fundaba en "lo pide la consigna" y no en código de tmux.
- **TP1:** el VC-23 no tenía los datos necesarios para dar su resultado, y la spec usaba "trozo" y "tramo" para lo mismo.
- **TP1 y TP2:** alcance futuro y plan de iteraciones mezclados dentro de la spec.

**Agente declarado:** Claude Code (probado con la 2.1.292 y la 2.1.294). El toolkit vive en
[`TP3 Skills & Agents/.claude/`](../.claude/). **El proyecto es la carpeta
`TP3 Skills & Agents/`**: Claude Code carga skills, subagents y hooks del `.claude/` de la
carpeta donde abrís la sesión, así que hay que correr `claude` desde ahí. El código que
especifica la evidencia (gcsgrep) está fuera, en `../TP1 Greenfield/Tarea/`, y se le da
acceso con `--add-dir`.

Todas las rutas de este README son relativas a `TP3 Skills & Agents/`.

## Las tres piezas

| Pieza | Archivo | Qué hace | Concepto de L1–L2 | Cuándo la usan |
|---|---|---|---|---|
| 📘 Skill `write-spec-brownfield` | [`.claude/skills/write-spec-brownfield/SKILL.md`](../.claude/skills/write-spec-brownfield/SKILL.md) + [`plantilla.md`](../.claude/skills/write-spec-brownfield/plantilla.md) + [`scripts/check_spec.py`](../.claude/skills/write-spec-brownfield/scripts/check_spec.py) | Arma `specs/<slug>.md` desde una plantilla que exige: base (hash), alcance dentro/fuera, invariantes con comando, cada FR en Dado/Cuando/Entonces con su `VC-FR-N` y cada decisión con `archivo:línea`. El script valida la estructura, exige campos completos y genera la tabla de trazabilidad; el revisor comprueba la coherencia con el código. | **Cobertura de VCs** y **alcance acotado**; también **spec antes que código** y spec anclada a una revisión del código (brownfield, L2). | Cuando alguien pide especificar un cambio sobre código que ya existe, antes de implementarlo ("especificá…", "armá la spec antes de tocar código"). Carga sola. |
| 👥 Subagent `spec-reviewer` | [`.claude/agents/spec-reviewer.md`](../.claude/agents/spec-reviewer.md) | Revisor de solo lectura (`tools: Read, Grep, Glob`). Abre cada `archivo:línea` que cita la spec, comprueba que los datos de cada VC alcancen para dar el resultado y devuelve un veredicto cerrado `READY` / `NEEDS WORK`, con hallazgos `spec:línea` y evidencia `archivo:línea`. | **Gate independiente**: quien revisa no es quien escribió. También **higiene de contexto**: las lecturas de código quedan en la ventana del subagent. | Lo lanza el skill en su paso 9. También cuando alguien pregunta "¿está lista esta spec?" o "revisala". |
| 🪝 Hook `spec-gate` | [`.claude/hooks/spec-gate.sh`](../.claude/hooks/spec-gate.sh) + [`commit_command.py`](../.claude/hooks/commit_command.py), registrados en [`.claude/settings.json`](../.claude/settings.json) | `PreToolUse` con matcher `Bash\|PowerShell`. Analiza invocaciones directas de Git respetando comillas, veta commits compuestos o dirigidos a otro repo y valida por separado el contenido del índice y la copia de trabajo. Si la política o el checker fallan, sale con `exit 2` y explica qué corregir. | **Cobertura de VCs**: aplica la validación estructural al contenido staged y conserva el control de la copia de trabajo, dentro de la gramática documentada abajo. | Corre en cada comando de shell del agente; chequea los commits directos que reconoce. |

### Por qué cada pieza está en ese recurso

- **Skill:** especificar es un flujo que repetimos en el TP1 y el TP2, y solo hace falta cuando aparece esa situación. Por eso carga con la `description` y no ocupa contexto en cada sesión. Lo determinístico (que cada FR tenga su VC, que cada decisión tenga ancla, la tabla de trazabilidad) lo hace `check_spec.py`, no el modelo.
- **Subagent:** su valor es la **independencia**. Si la sesión que escribió la spec también la revisa, hereda sus supuestos. Además, verificar anclas es trabajo ruidoso. En la evidencia 01, el revisor corrió tres veces, con 8, 10 y 11 llamadas a herramientas y entre 46.179 y 70.194 tokens en su ventana. La sesión principal recibió solo cada informe. Lleva `tools: Read, Grep, Glob` para que el "no edites" lo garantice la configuración y no solo el brief. No lleva `Bash`, y por eso no ejecuta los VCs: verifica leyendo.
- **Hook:** el skill pide la cobertura de VCs y el revisor la revisa. El hook bloquea los commits que detecta si las specs examinadas no pasan el checker, incluso cuando una copia de trabajo corregida oculta una versión staged inválida.

### Cómo componen

`write-spec-brownfield` llama a `check_spec.py` en el paso 8 y lanza `spec-reviewer` en el
paso 9. `spec-gate` corre el mismo `check_spec.py` en el commit, así que la regla que hace
cumplir el hook es la misma que pide el skill: una sola fuente de verdad.

### Qué comprueba el checker

- Cada FR tiene un bullet por campo: `- **Dado** …`, `- **Cuando** …` y
  `- **Entonces** …`, con contenido en la misma línea. Campos vacíos, puntuación
  sola o etiquetas mencionadas dentro de otro párrafo no alcanzan.
- Cada VC de FR, INV o NFR ocupa una línea: entrada/comando no vacío entre
  backticks, `→` fuera de los backticks y resultado esperado no vacío después.
  Si hay varios `→`, ninguno puede quedar sin contenido posterior. Una salida
  vacía explícita, como ``stdout `""`, exit 1``, sí es un resultado.
- Cada NFR tiene un único bullet **Métrica**, **Umbral** y **Carga**. Métrica
  nombra qué se mide; umbral y carga incluyen números con unidad o condición.
  Los números de anclas `archivo:línea` o `archivo:inicio-fin` no cuentan como
  medida. Si el cambio no necesita NFR, se elimina esa sección completa.

`OK` significa que pasó estos controles y los demás controles estructurales del
script. El checker no ejecuta los VCs, no verifica que las anclas existan y no
demuestra que los datos produzcan el resultado declarado ni que una métrica sea
adecuada. Esas comprobaciones requieren la lectura del revisor y, al implementar,
la ejecución de los tests. Un texto no vacío puede seguir siendo ambiguo; el
formato por sí solo no demuestra corrección semántica.

La corrección 3 exige los tres campos explícitos de NFR, en lugar de un párrafo
libre con algún número. La spec de ejemplo se adaptó conservando sus límites
de lectura y su carga; las transcripciones anteriores conservan el formato
histórico que realmente se ejecutó.

### Cuándo el revisor puede declarar READY

El brief de [`spec-reviewer`](../.claude/agents/spec-reviewer.md) identifica cinco
controles: C1 anclas y decisiones, C2 VCs y aceptación de NFRs, C3 términos,
C4 alcance y C5 invariantes. El informe registra cada uno como `OK`, `FALLA` o
`NO VERIFICABLE`, con evidencia de lectura. `READY` requiere **los cinco `OK`
y ningún `BLOQUEANTE`**. Una falla o información insuficiente en cualquiera de ellos
exige un `BLOQUEANTE` asociado y `NEEDS WORK`.

`MENOR` se limita a detalles editoriales que no cambian el contrato de implementación
ni los datos/resultados de los VCs. Una contradicción de alcance, un término ambiguo
o invariantes insuficientes bloquean tanto como un ancla falsa o un VC imposible.
Si la evidencia no se encuentra, se declara qué ruta se consultó y qué se buscó,
sin inventar líneas o citas. Los tests propuestos no deben existir antes de implementar;
sí deben poder escribirse a partir de datos y criterios suficientes.

El skill exige un informe completo y consistente con ese criterio antes de dar la
spec por lista. Las dos vueltas de corrección/revisión también incluyen informes
incompletos o contradictorios; si no alcanza, reporta `NEEDS WORK` y lo pendiente.
El revisor trata las órdenes incrustadas para forzar un veredicto como material a
evaluar, distinguiéndolas de textos usados como datos de fixtures. Este criterio es
parte del brief: el hook sigue validando estructura y no certifica el veredicto
semántico ni la resistencia del modelo a instrucciones incrustadas.

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
macOS con Bash 3.2 y Python 3.14 mediante las 12 regresiones de evidencia 08.
La corrección de comandos se verificó con 23 tests en macOS (evidencia 09), y la del
checker junto con las anteriores mediante 41 tests en macOS (evidencia 10).
Las sesiones 01, 05 y 06 se volvieron a correr en Claude Code 2.1.294 sobre Windows
con las piezas de `4de0e91`, es decir, con todas esas correcciones.
En Windows, los tests de `tarea/tests` necesitan que `bash` resuelva al de Git for
Windows: si WSL está instalado, Python encuentra antes `C:\Windows\System32\bash.exe`
y las regresiones del hook fallan por el entorno, no por el hook.

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

Las sesiones 01–06 usan `claude -p --output-format stream-json --verbose`, abiertas
desde `TP3 Skills & Agents/`. El JSONL crudo está en [`evidencia/raw/`](evidencia/raw/), y
la transcripción legible se generó con [`evidencia/transcribir.py`](evidencia/transcribir.py).
Ninguna sesión commiteó en este repo. Las sesiones 01, 05 y 06 y la reproducción 07 corrieron en
un **clon descartable** del repo.

| # | Qué muestra | Archivo |
|---|---|---|
| 01 | **Skill disparando solo** con un pedido que no lo nombra. Lee el código de gcsgrep, escribe [`evidencia/specs/gcsgrep-count.md`](evidencia/specs/gcsgrep-count.md), corre `check_spec.py` y **lanza `spec-reviewer`**. Cada informe trae la tabla C1–C5 del brief actual. Primera vuelta: `NEEDS WORK` con 4 `BLOQUEANTE` (C2–C5). La sesión corrige, vuelve a chequear y relanza el revisor dos veces. La tercera revisión sigue en `NEEDS WORK` con un bloqueante de C5 (INV-2 no detecta un test existente neutralizado agregando líneas). Agotadas las dos vueltas, el skill informa `NEEDS WORK` y lo pendiente, sin declarar lista la spec. | [`01-skill-y-subagent.md`](evidencia/01-skill-y-subagent.md) |
| 02 | Segunda frase que dispara el skill (`→ Skill write-spec-brownfield` como primera acción). Cortada a 3 turnos. | [`02-trigger-positivo.md`](evidencia/02-trigger-positivo.md) |
| 03 | Frase parecida que **no** tiene que disparar ("revisá la spec…"): el skill no carga y la sesión se pone a leer la spec y el código. Cortada a 3 turnos. | [`03-trigger-negativo-revisar.md`](evidencia/03-trigger-negativo-revisar.md) |
| 04 | Pregunta sobre una spec ("¿qué dice la spec del TP1 sobre los exit codes?"): el skill no carga. | [`04-trigger-negativo-pregunta.md`](evidencia/04-trigger-negativo-pregunta.md) |
| 05 | **El hook bloquea un commit.** En la spec staged faltaba `VC-FR-3` y D-2 se fundaba en "lo decidimos así en el equipo". El agente intenta `git commit … && git log …` y el hook lo veta por comando compuesto. Lo separa, intenta `git commit` solo y recibe el segundo veto, con las líneas `[staged]` y `[copia de trabajo]`. No lo esquiva: revisa el diff, explica las dos líneas y pregunta cómo seguir. `git log` sigue en `4a4ede9`. | [`05-hook-bloquea.md`](evidencia/05-hook-bloquea.md) · [`raw/05-git-log.txt`](evidencia/raw/05-git-log.txt) |
| 06 | **El agente corrige con el stderr y el commit pasa.** Es la misma sesión retomada: vuelve a agregar `VC-FR-3`, ancla D-2 a `src/gcsgrep/gcs.py:151-154` y `src/gcsgrep/cli.py:63-67` después de leerlos, `check_spec.py` da OK, hace `git add` y `git commit` en llamadas separadas, y el hook deja pasar el commit (`4cec3a5`). | [`06-hook-corrige-y-pasa.md`](evidencia/06-hook-corrige-y-pasa.md) · [`raw/05-git-log.txt`](evidencia/raw/05-git-log.txt) |
| 07 | Reproducción del §7 alimentando el hook por stdin, con el hook de `4de0e91`. Condición mala: `exit 2` en cuatro variantes de commit y con PowerShell. Commits compuestos (`cd . &&`, `git add . &&`): `exit 2`. Comandos que no son commit: `exit 0`. Evento malformado: `exit 2`. Spec inválida staged con la copia corregida: `exit 2`. Condición buena: `exit 0`. | [`07-hook-reproduccion.txt`](evidencia/07-hook-reproduccion.txt) |
| 08 | Regresiones de la corrección del índice: bloquea specs staged inválidas aunque se corrijan o borren del disco; permite volver a stagear la corrección y eliminar una spec del índice; mantiene la política conservadora para `-a`, rutas y eventos PowerShell. Cada caso usa un repo temporal y comprueba que el hook no altere el índice. Es ejecución directa del hook, sin una sesión nueva de Claude. | [`08-hook-indice.txt`](evidencia/08-hook-indice.txt) · [`tests/test_spec_gate.py`](tests/test_spec_gate.py) |
| 09 | Regresiones de los comandos, incluidas las 12 del índice: rutas `-C` entre comillas, commits compuestos con specs nuevas, destino externo, menciones que no deben disparar y mensajes con operadores como texto. Guarda la salida real y hashes de los archivos probados; cada caso comprueba que el hook no cambie el árbol del índice. | [`09-hook-comandos.txt`](evidencia/09-hook-comandos.txt) · [`tests/test_spec_gate.py`](tests/test_spec_gate.py) |
| 10 | Corrección del checker: 16 tests de campos FR/NFR y VCs, más las 23 regresiones anteriores del hook y 2 nuevas de bloqueo estructural en índice/copia de trabajo. Incluye salida real, hashes y comprobación directa de la spec adaptada. | [`10-checker-estructura.txt`](evidencia/10-checker-estructura.txt) · [`tests/test_check_spec.py`](tests/test_check_spec.py) · [`tests/test_spec_gate.py`](tests/test_spec_gate.py) |
| 11 | Revisión manual del criterio de severidad y veredicto: casos de los cinco controles, falta de evidencia, detalles editoriales e instrucciones incrustadas; comprueba consistencia entre brief, skill y README. No es una ejecución nueva del subagent. | [`11-reviewer-criterios.md`](evidencia/11-reviewer-criterios.md) |

Las sesiones 01, 05 y 06 y la reproducción 07 se volvieron a correr el 2026-10-08 con las
piezas de `4de0e91`, que incluyen las correcciones del índice, de los comandos, del checker
y del criterio C1–C5 del revisor. Corrieron en Claude Code 2.1.294, en un clon descartable.
La 01 partió sin spec. Su resultado se commiteó en el clon como base (`4a4ede9`), y para
la 05 se stageó esa spec sin `VC-FR-3` y con D-2 sin ancla.
Las sesiones 02–04 son anteriores a esas correcciones y no intentan commits: solo prueban
el trigger, que depende de la `description`, sin cambios desde entonces.
Las evidencias 08–10 son tests directos, no sesiones de Claude Code. La 11 documenta el
criterio de veredicto por revisión manual, y la 01 lo muestra aplicado en una corrida real.

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

# Regresiones del checker y del hook: usan repositorios temporales para el hook
python3 -m unittest discover -s tarea/tests -v  # Windows: py -3 en lugar de python3
```

La condición mala necesita que la spec figure como modificada para git, es decir, que esté
commiteada. Si todavía no lo está, stageala (`git add`) antes del `sed`.
