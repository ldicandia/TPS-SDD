# TP4 — `gcsgrep` contra un bucket real, por MCP

> Índice de entrega (integrantes, artefactos, cómo verificar): [`ENTREGA.md`](ENTREGA.md).
> Consigna: [`enunciado.md`](enunciado.md).

El toolkit SDD del TP3 (spec brownfield + revisor independiente + gate de commits) ahora
**lee un bucket de GCS real** antes de escribir los VCs de `gcsgrep`. Lo hace a través del
server MCP oficial de Cloud Storage, con una cuenta de solo lectura, detrás de un muro de
tres capas probadas, y con el contenido de los objetos leído por un subagent que no tiene
con qué obedecer lo que lee. Todo se instala como un plugin.

**Paso SDD que alimenta: especificar los VCs.** Cada VC de la spec nombra un objeto real
del bucket, su `generation` real de GCS y la línea real que contiene el
patrón. Antes de dar la spec por lista, el skill vuelve a pedir la huella: si un objeto
cambió, la spec vuelve a `NEEDS WORK`.

**Agente:** Claude Code 2.1.296 en Windows 11. **El proyecto es la carpeta
`TP4 Plugins adn MCP/`**: hay que abrir `claude` desde ahí. El código de gcsgrep está en
`../TP1 Greenfield/Tarea/` y se le da acceso con `--add-dir`. Las rutas de este README son
relativas a `TP4 Plugins adn MCP/`.

## Las piezas

| Pieza | Archivo | Qué hace |
|---|---|---|
| 🔌 Config MCP | [`.mcp.json`](../.mcp.json) | Server `gcs`: launcher Node → `npx -y @google-cloud/storage-mcp@0.6.0`, versión fijada, **sin** `--enable-destructive-tools`, sin secretos; carga `mcp/register-generation.mjs` |
| 🎼 Skill `write-vcs-con-bucket` | [`.claude/skills/write-vcs-con-bucket/SKILL.md`](../.claude/skills/write-vcs-con-bucket/SKILL.md) | `write-spec-brownfield` (TP3) con un paso previo: inventario con `list_objects` y `read_object_metadata`, contenido por `lector-bucket`, sección "Evidencia del bucket" en la spec, revalidación de huellas antes de terminar. Frena si falta el server |
| 👁️ Subagent `lector-bucket` | [`.claude/agents/lector-bucket.md`](../.claude/agents/lector-bucket.md) | `tools:` solo `list_objects`, `read_object_metadata`, `read_object_content`. Sin Bash, sin archivos, sin red. Devuelve inventario, líneas con match y, **aparte**, las líneas que parecen instrucciones (solo 40 caracteres) |
| 🧱 Hook `gcs-allowlist` | [`.claude/hooks/gcs-allowlist.sh`](../.claude/hooks/gcs-allowlist.sh) + [`gcs_allowlist.py`](../.claude/hooks/gcs_allowlist.py) | `PreToolUse` sobre `mcp__gcs__.*`. **Allowlist**: pasan las tres tools de lectura y solo contra el bucket de prueba (mira `bucket_name`). Todo lo demás, `exit 2`, incluida cualquier tool nueva del server. Falla cerrado |
| 📘 Toolkit de TP3 | `.claude/skills/write-spec-brownfield/`, `.claude/agents/spec-reviewer.md`, `.claude/hooks/spec-gate.sh` | Sin cambios de comportamiento; `spec-gate` aprendió a encontrar el checker dentro del plugin |
| 📦 Plugin `gcsgrep-sdd` | [`plugin/gcsgrep-sdd/`](../plugin/gcsgrep-sdd/) | Todo lo anterior empaquetado, versión `1.0.1`, armado por [`armar.sh`](../plugin/gcsgrep-sdd/armar.sh) |
| 🪣 Bucket de prueba | [`bucket/crear-bucket.sh`](../bucket/crear-bucket.sh) + [`bucket/objetos/`](../bucket/objetos/) | Arma el bucket con objetos sintéticos, el bucket sin acceso, la SA y los bindings. Lo corre una persona, nunca el agente |

### Cómo componen

```
pedido "especificá -l de gcsgrep con los objetos del bucket"
  └─ skill write-vcs-con-bucket                         (sesión principal: Bash, red, credenciales)
       ├─ list_objects, read_object_metadata  ──hook──▶  server gcs ──SA objectViewer──▶ GCS
       ├─ Agent lector-bucket                             (sin Bash ni red)
       │    └─ read_object_content            ──hook──▶  server gcs ──────────────────▶ GCS
       ├─ specs/<slug>.md con "Evidencia del bucket"
       ├─ check_spec.py + spec-reviewer                   (TP3)
       └─ read_object_metadata otra vez: ¿misma huella?  → si no, NEEDS WORK
```

### Dos cosas del server que el enunciado no dice

- **En `@google-cloud/storage-mcp` 0.6.0, las tools de escritura del modo seguro se llaman
  `write_object_safe`, `upload_object_safe` y `copy_object_safe`** (no `*_new`), y el modo
  seguro expone 15 tools, entre ellas `create_bucket`, `view_iam_policy` y
  `execute_insights_query`. Ver la evidencia 01.
- **El server oficial 0.6.0 omite `generation` en su respuesta de metadata.** La
  config carga el ajuste local [`generation-v1`](../mcp/generation-loader.mjs) con
  `NODE_OPTIONS=--import ...register-generation.mjs`. El loader agrega el campo
  original `metadata.generation` de la misma consulta GCS, conservado como **string**.
  Comprueba el SHA-256 del bundle oficial antes de aplicar el ajuste y rechaza otra
  versión o un bundle alterado. No modifica la instalación de npm, no agrega tools
  ni permisos, y conserva las 15 tools del modo seguro.
  El skill y el lector comparan generations antes y después de leer, y al revalidar.
  Si falta el dato, una lectura falla o cambia la versión, el objeto no se aprueba;
  fecha y tamaño no son un fallback. `generation` es un identificador de versión,
  no una fecha que debamos convertir. `updated` puede cambiar solo por metadata.
  [Documentación de GCS](https://docs.cloud.google.com/storage/docs/metadata#generation_and_metageneration_numbers).
  Las evidencias 01–07 conservan la implementación anterior. El ajuste se verifica
  con los tests Node del loader y la integración MCP contra una API local.
- Además, `read_object_content` se niega a leer como texto un objeto
  `application/octet-stream`. En Windows, `gcloud storage cp` subió los `.log` con ese
  tipo; `crear-bucket.sh` ahora fija `text/plain` (lo encontró el propio skill, que frenó
  en vez de inventar: evidencia 03a).

## Instalación

### 1. El bucket y la cuenta (una vez, una persona con permisos en el proyecto)

```bash
cp .env.example .env      # completá PROYECTO; opcional CUENTA_HUMANA y BUCKET
bash bucket/crear-bucket.sh
```

`.env` está en `.gitignore`: el proyecto y la cuenta de cada equipo no van al repo. Lo
que esté exportado en el entorno tiene prioridad sobre `.env`. En las evidencias, la
cuenta humana que impersona la SA aparece como `<cuenta-humana>`.

Crea `gs://$PROYECTO-gcsgrep-tp4` (9 objetos sintéticos: `.log` con matches conocidos, un
`.gz`, un binario, un vacío, uno sin `\n` final, un prefijo anidado y el fixture hostil),
`gs://$PROYECTO-gcsgrep-tp4-sinacceso`, la SA `gcsgrep-mcp-lector` con
`roles/storage.objectViewer` **sobre el primer bucket** y nada más, y le da a quien lo corre
`roles/iam.serviceAccountTokenCreator` sobre la SA para impersonarla.

### 2. La credencial del agente (cada persona, en su máquina)

```bash
gcloud auth application-default login \
  --impersonate-service-account=gcsgrep-mcp-lector@$PROYECTO.iam.gserviceaccount.com
```

Queda en `%APPDATA%\gcloud\application_default_credentials.json` (Linux/macOS:
`~/.config/gcloud/`), fuera del repo, de tipo `impersonated_service_account`. No hay key
JSON de la SA en ningún lado. Comprobalo: el `type` de ese archivo tiene que ser
`impersonated_service_account`, no `authorized_user` (si es este último, el server corre
con tu cuenta humana y la capa de la credencial no existe).

### 3a. Como plugin (recomendado)

```bash
claude --plugin-dir "<ruta al repo>/TP4 Plugins adn MCP/plugin/gcsgrep-sdd"
```

Se puede abrir desde cualquier repo: el plugin trae su server, sus hooks, skills y
subagents. No lo combines con la carpeta `TP4 Plugins adn MCP/` abierta como proyecto,
porque tendrías dos servers `gcs` (el del proyecto y el del plugin).

Al habilitarlo, Claude Code pide la opción **`bucket`** (el nombre del bucket de prueba,
sin `gs://`). Le llega al hook como `CLAUDE_PLUGIN_OPTION_BUCKET`. Si cambiás algo en
`.claude/` o `mcp/`, regenerá el plugin con `bash plugin/gcsgrep-sdd/armar.sh` y validalo con
`claude plugin validate plugin/gcsgrep-sdd`.

### 3b. Como proyecto

```bash
cd "TP4 Plugins adn MCP"
export GCSGREP_BUCKET=$PROYECTO-gcsgrep-tp4      # PowerShell: $env:GCSGREP_BUCKET = "…"
claude --add-dir "../TP1 Greenfield/Tarea"
```

Sin `GCSGREP_BUCKET`, el hook veta toda tool del bucket. Comprobá con `/mcp` que aparezca
`gcs` con 15 tools y con `/hooks` que estén `mcp__gcs__.*` y `Bash|PowerShell`.

**Dependencias:** Node 24 (`npx` y soporte de `--import`/`module.register`), Python ≥ 3.8 (`python3`, `python` o `py -3`), `bash`
(en Windows, el de Git for Windows) y `gcloud` solo para el paso 1 y para la
autenticación. No hace falta `jq`.

### Tests

```bash
py -3 -m unittest discover -s Tarea/tests -v       # Linux/macOS: python3
```

12 tests del hook: las tres lecturas pasan (con los dos prefijos de nombre); vetan las
escrituras del modo seguro, las lecturas no revisadas, las destructivas, una tool futura,
otro bucket, bucket faltante, otro server y eventos ilegibles; y el wrapper `.sh`
propaga el código.

Tests del ajuste (sin GCP):

```bash
node --test mcp/generation-loader.test.mjs
```

Para incluir el formatter y la integración contra la API local, instalá el paquete
oficial en una carpeta temporal y definí `STORAGE_MCP_BUNDLE` con la ruta absoluta a
su `node_modules/@google-cloud/storage-mcp/dist/bundle.js`. La integración arranca
el server real desde el proyecto y el plugin desde otra carpeta; usa solo una API
local de metadata, sin ADC. Sin bundle, ese test se saltea explícitamente.

Ejemplo en bash (Node 24 en PATH):

```bash
PRUEBA=$(mktemp -d)
npm install --prefix "$PRUEBA" --ignore-scripts --no-audit --no-fund @google-cloud/storage-mcp@0.6.0
export STORAGE_MCP_BUNDLE="$PRUEBA/node_modules/@google-cloud/storage-mcp/dist/bundle.js"
node --test mcp/generation-loader.test.mjs
python3 -m unittest discover -s Tarea/tests -v
```

En PowerShell, usar `npm install --prefix "$env:TEMP/gcsgrep-generation-test" ...`
y definir `$env:STORAGE_MCP_BUNDLE` con la ruta absoluta al bundle instalado.
Para probar el comando completo del launcher y `npx`, definir además
`GCSGREP_MCP_NPX=1` antes de ejecutar la suite Python. En ese modo `npx` puede
completar su caché con el paquete fijado en 0.6.0.

## Nota de seguridad

> **Acceso.** Conectamos el server MCP `@google-cloud/storage-mcp` **0.6.0** (fijado en
> `.mcp.json` y en el `.mcp.json` del plugin) al bucket de prueba
> `gs://spec-driven-511601-gcsgrep-tp4`, del proyecto de prueba `spec-driven-511601`.
> La config añade el launcher y loader locales `generation-v1`: solo expone la generation original
> de la respuesta GCS. Los tests comprueban su integridad y arranque desde otro
> directorio; la nueva corrida contra GCS real queda pendiente.
>
> **Modo.** Sin `--enable-destructive-tools`. Ese modo **no es de solo lectura**: expone 15
> tools, y cuatro crean recursos (`create_bucket`, `write_object_safe`,
> `upload_object_safe`, `copy_object_safe`); deja afuera las que pisan o borran
> (`delete_object`, `move_object`, `write_object`, `update_object_metadata`,
> `delete_bucket`, …). El toolkit usa tres: `list_objects`, `read_object_metadata` y
> `read_object_content`.
>
> **Credencial.** La service account `gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com`,
> con `roles/storage.objectViewer` **sobre ese bucket** y ningún rol en el proyecto
> (evidencia 02). El server la usa por ADC con impersonación; el archivo de ADC vive en
> el perfil de cada persona, no tiene key de la SA y no está en el repo ni en el plugin.
>
> **Datos.** Nueve objetos sintéticos generados por `crear-bucket.sh` desde
> `bucket/objetos/` (logs inventados, un `.gz`, un binario de 36 bytes y un fixture hostil
> que apunta a `recolector.invalid`, RFC 2606). Nada de logs reales; el bucket se puede
> borrar y regenerar.
>
> **Peor caso.** Si el agente intenta escribir o borrar: (1) el hook `gcs-allowlist` lo
> veta antes de que la llamada salga de la sesión, porque solo deja pasar tres lecturas
> sobre el bucket de prueba; (2) si el pedido es borrar, la tool ni existe en este modo;
> (3) si el hook no estuviera y el server escribiera, **GCS responde `403`** porque la SA
> no tiene `storage.objects.create` ni `delete`. Probado en las tres capas (evidencia 04),
> incluida una sesión **sin el hook** donde `write_object_safe` llegó a GCS y volvió con
> `"code": 403`, y repetido con el plugin y sus nombres nuevos (evidencia 06). La capa que
> garantiza es la tercera: no depende ni del agente ni del server.
>
> **Trifecta.** La sesión principal tiene las tres patas: **datos privados** (el ADC, la
> config de gcloud y todo lo de la máquina), **contenido no confiable** (lo que diga
> cualquier objeto del bucket, incluida su metadata custom) y **un canal hacia afuera**
> (Bash con red). Cortamos el canal donde entra lo no confiable: el contenido de los
> objetos lo lee solo `lector-bucket`, cuyas únicas tools son las tres de lectura del
> server (sin Bash, sin `Read`, sin web), y que devuelve las líneas que parecen órdenes
> marcadas aparte y truncadas a 40 caracteres. El skill no tiene `read_object_content`.
> Probado con `fixtures/hostil/notas.log`, que pide un `curl` de las credenciales: el
> subagent lo marcó y en toda la sesión no hubo ningún intento de ejecutarlo
> (evidencia 05). Límite: `read_object_metadata` sí corre en la sesión principal, y la
> metadata custom de un objeto también es contenido de terceros.
>
> **Contexto.** El server suma **3,2k tokens** (15 tools en carga diferida, medido con
> `/context`); con los skills, subagents y el `CLAUDE.md`, el toolkit agrega ≈ 4,6k
> (evidencia 07). Tres cuartos de las tools que ocupan ventana son las que el hook igual
> veta, y el plugin arranca un `npx` por sesión: conviene habilitarlo **solo en el repo de
> gcsgrep**, no en todos.

## Evidencia

Las sesiones usan `claude -p --output-format stream-json --verbose`, desde
`TP4 Plugins adn MCP/`. El JSONL crudo está en [`evidencia/raw/`](evidencia/raw/); la
transcripción legible la genera [`evidencia/transcribir.py`](evidencia/transcribir.py)
(el de TP3, que ahora reconoce los skills, subagents y servers del TP4).

| # | Qué muestra | Archivo |
|---|---|---|
| 01 | El agente listando las 15 tools del server, `list_objects` pasando el hook, y los dos `tools/list` (con y sin flag destructivo) | [`01-descubrimiento.md`](evidencia/01-descubrimiento.md) |
| 02 | La política IAM del bucket con `objectViewer` para la SA, sin roles de proyecto, y el bucket sin acceso | [`02-iam.md`](evidencia/02-iam.md) |
| 03a | **El skill frena sin datos.** Con los objetos subidos como `octet-stream`, `lector-bucket` no pudo leer contenido y el skill no escribió ningún VC: explicó qué faltaba | [`03a-skill-frena.md`](evidencia/03a-skill-frena.md) |
| 03 | El skill escribiendo la spec de `-l` con VCs sobre objetos reales, **la línea que solo pudo venir del bucket** marcada, la sección de procedencia y la revalidación | [`03-skill.md`](evidencia/03-skill.md) |
| 03b | **La evidencia envejece.** Una persona reemplaza `server.log`; una sesión que va a implementar revalida las huellas, detecta que solo cambió ese objeto y deja la spec en `NEEDS WORK` con los VCs afectados | [`03b-revalidacion.md`](evidencia/03b-revalidacion.md) |
| 04 | Veto del hook, tool que no existe, `403` de GCS con `gcloud` y con el agente sin hook | [`04-muro.md`](evidencia/04-muro.md) |
| 05 | La salida del subagent marcando el objeto hostil, y que no hubo ningún intento de ejecutarlo | [`05-fixture-hostil.md`](evidencia/05-fixture-hostil.md) |
| 06 | `claude plugin validate`, las tools con sus nombres nuevos y la prueba del muro repetida con el plugin | [`06-plugin.md`](evidencia/06-plugin.md) |
| 07 | `/context` con y sin el server (medición histórica) | [`07-contexto.md`](evidencia/07-contexto.md) |
