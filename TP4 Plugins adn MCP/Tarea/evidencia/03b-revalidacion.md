# Evidencia 03b — La evidencia envejece: la revalidación falla

Después de la evidencia 03 (spec `READY`, huellas leídas entre 02:03Z y 02:07Z), una
persona reemplazó `logs/app/server.log` por afuera del agente, con su propia cuenta,
agregándole una línea. Es lo que haría un compañero. El objeto pasó a tener otra
generation:

```text
# Cambio por afuera del agente, como lo haría un compañero (cuenta humana), 2026-10-14T02:15:50Z
$ gcloud storage objects describe gs://spec-driven-511601-gcsgrep-tp4/logs/app/server.log  # antes
1791942299203604	2026-10-14T01:44:59+0000	314
$ gcloud storage cp server.log (+1 línea) gs://spec-driven-511601-gcsgrep-tp4/logs/app/server.log --content-type=text/plain
Copying file://C:\Users\LUCASD~1\AppData\Local\Temp\server.log to gs://spec-driven-511601-gcsgrep-tp4/logs/app/server.log
$ gcloud storage objects describe gs://spec-driven-511601-gcsgrep-tp4/logs/app/server.log  # después
1791944156350391	2026-10-14T02:15:56+0000	366
```

Después, una sesión nueva pide **implementar** contra la spec, sin decir qué cambió:

> Vamos a implementar el flag -l de gcsgrep siguiendo specs/gcsgrep-files-with-matches.md.
> Antes de tocar código, confirmá que la spec sigue valiendo contra el bucket. Todavía no
> implementes nada.

**Resultado:** la sesión vuelve a pedir `read_object_metadata` de los 9 objetos, compara
la huella de cada uno con la tabla "Evidencia del bucket", encuentra que **solo**
`server.log` cambió (`01:44:59.210Z · 314 B` → `02:15:56.365Z · 366 B`), declara la spec
en **`NEEDS WORK`** citando la regla de la propia spec, lista los VCs que dependen de ese
objeto (VC-INV-2, VC-FR-1, -2, -3 y -6) y los que no, y propone volver a correr el skill
para releerlo. No aprueba ni implementa contra un objeto que ya no es el que se leyó.

Distingue bien `updated` de la huella: los otros 8 objetos tienen `updated` posterior a
`time_created` (por el cambio de `content-type` de la evidencia 03a) y los da por
iguales, porque eso es metadata, no una generation nueva.

**Estado que queda:** la spec entregada conserva la evidencia de las 02:03Z; el bucket ya
no coincide en `server.log`. Es a propósito: es lo que esta evidencia muestra. Para
volver a `READY` hay que correr de nuevo el skill (que relee el objeto y actualiza la fila
y los VCs) y el revisor.

## Transcripción


- Sesión nueva `b7f0a9c6-f5e8-439d-a0aa-46997582ea2f` · modelo `claude-opus-5-5` · Claude Code 2.1.296
- Skills del toolkit disponibles: ['write-spec-brownfield', 'write-vcs-con-bucket'] · subagents: ['lector-bucket', 'spec-reviewer']
- Servers MCP: ['gcs (connected)'] · 15 tools MCP, p. ej. `mcp__gcs__check_iam_permissions`

`→ Read` {"file_path": "C:\\Users\\Lucas Di Candia\\Desktop\\SDD\\TPS-SDD\\TP4 Plugins adn MCP\\specs\\gcsgrep-files-with-matches.md"}

`← Read`

```text
1	# Spec — flag `-l` / `--files-with-matches` en `gcsgrep`
2	
3	**Base:** `gcsgrep` @ `4edac8e21ab512e34549798768e49bfa5d8dd868` · **Fecha:** 2026-10-13
4	
5	Rutas al código relativas a `../TP1 Greenfield/Tarea/` (raíz del proyecto gcsgrep).
6	Los VCs `gcsgrep …` corren desde esa raíz con el paquete instalado (`pip install -e .`),
7	ADC impersonando `gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com` y
8	shell bash. Los VCs `pytest` corren desde la misma raíz con `py -3 -m pytest`.
9	
10	## Propósito
11	
12	Quien busca un patrón en un bucket puede obtener solo la lista de objetos q
… [16445 caracteres más]
```

`→ ToolSearch` {"query": "select:mcp__gcs__list_objects,mcp__gcs__read_object_metadata", "max_results": 2}

`← ToolSearch`

```text

```

`→ mcp__gcs__list_objects` {"bucket_name": "spec-driven-511601-gcsgrep-tp4"}

`← mcp__gcs__list_objects`

```text
{
  "bucket": "spec-driven-511601-gcsgrep-tp4",
  "object_count": 9,
  "objects": [
    "archive/old.log.gz",
    "bin/blob.bin",
    "edge/empty.log",
    "edge/nonl.log",
    "fixtures/hostil/notas.log",
    "logs/2026/10/13/deep/worker.log",
    "logs/app/a.log",
    "logs/app/b.log",
    "logs/app/server.log"
  ],
  "next_page_token": null
}
```

`→ mcp__gcs__read_object_metadata` {"bucket_name": "spec-driven-511601-gcsgrep-tp4", "object_name": "archive/old.log.gz"}

`→ mcp__gcs__read_object_metadata` {"bucket_name": "spec-driven-511601-gcsgrep-tp4", "object_name": "bin/blob.bin"}

`→ mcp__gcs__read_object_metadata` {"bucket_name": "spec-driven-511601-gcsgrep-tp4", "object_name": "edge/empty.log"}

`← mcp__gcs__read_object_metadata`

```text
{
  "bucket": "spec-driven-511601-gcsgrep-tp4",
  "object": "archive/old.log.gz",
  "size": 81,
  "content_type": "application/gzip",
  "time_created": "2026-10-14T01:44:58.190Z",
  "updated": "2026-10-14T02:03:22.770Z",
  "storage_class": "STANDARD"
}
```

`→ mcp__gcs__read_object_metadata` {"bucket_name": "spec-driven-511601-gcsgrep-tp4", "object_name": "edge/nonl.log"}

`→ mcp__gcs__read_object_metadata` {"bucket_name": "spec-driven-511601-gcsgrep-tp4", "object_name": "fixtures/hostil/notas.log"}

`→ mcp__gcs__read_object_metadata` {"bucket_name": "spec-driven-511601-gcsgrep-tp4", "object_name": "logs/2026/10/13/deep/worker.log"}

`← mcp__gcs__read_object_metadata`

```text
{
  "bucket": "spec-driven-511601-gcsgrep-tp4",
  "object": "bin/blob.bin",
  "size": 36,
  "content_type": "application/octet-stream",
  "time_created": "2026-10-14T01:44:58.581Z",
  "updated": "2026-10-14T01:44:58.581Z",
  "storage_class": "STANDARD"
}
```

`→ mcp__gcs__read_object_metadata` {"bucket_name": "spec-driven-511601-gcsgrep-tp4", "object_name": "logs/app/a.log"}

`→ mcp__gcs__read_object_metadata` {"bucket_name": "spec-driven-511601-gcsgrep-tp4", "object_name": "logs/app/b.log"}

`→ mcp__gcs__read_object_metadata` {"bucket_name": "spec-driven-511601-gcsgrep-tp4", "object_name": "logs/app/server.log"}

`← mcp__gcs__read_object_metadata`

```text
{
  "bucket": "spec-driven-511601-gcsgrep-tp4",
  "object": "edge/empty.log",
  "size": 0,
  "content_type": "text/plain",
  "time_created": "2026-10-14T01:44:59.311Z",
  "updated": "2026-10-14T02:03:15.679Z",
  "storage_class": "STANDARD"
}
```

`← mcp__gcs__read_object_metadata`

```text
{
  "bucket": "spec-driven-511601-gcsgrep-tp4",
  "object": "edge/nonl.log",
  "size": 11,
  "content_type": "text/plain",
  "time_created": "2026-10-14T01:44:59.255Z",
  "updated": "2026-10-14T02:03:16.548Z",
  "storage_class": "STANDARD"
}
```

`← mcp__gcs__read_object_metadata`

```text
{
  "bucket": "spec-driven-511601-gcsgrep-tp4",
  "object": "fixtures/hostil/notas.log",
  "size": 265,
  "content_type": "text/plain",
  "time_created": "2026-10-14T01:44:58.543Z",
  "updated": "2026-10-14T02:03:16.494Z",
  "storage_class": "STANDARD"
}
```

`← mcp__gcs__read_object_metadata`

```text
{
  "bucket": "spec-driven-511601-gcsgrep-tp4",
  "object": "logs/2026/10/13/deep/worker.log",
  "size": 171,
  "content_type": "text/plain",
  "time_created": "2026-10-14T01:44:59.392Z",
  "updated": "2026-10-14T02:03:16.549Z",
  "storage_class": "STANDARD"
}
```

`← mcp__gcs__read_object_metadata`

```text
{
  "bucket": "spec-driven-511601-gcsgrep-tp4",
  "object": "logs/app/a.log",
  "size": 97,
  "content_type": "text/plain",
  "time_created": "2026-10-14T01:44:59.680Z",
  "updated": "2026-10-14T02:03:16.501Z",
  "storage_class": "STANDARD"
}
```

`← mcp__gcs__read_object_metadata`

```text
{
  "bucket": "spec-driven-511601-gcsgrep-tp4",
  "object": "logs/app/b.log",
  "size": 82,
  "content_type": "text/plain",
  "time_created": "2026-10-14T01:44:59.291Z",
  "updated": "2026-10-14T02:03:16.515Z",
  "storage_class": "STANDARD"
}
```

`← mcp__gcs__read_object_metadata`

```text
{
  "bucket": "spec-driven-511601-gcsgrep-tp4",
  "object": "logs/app/server.log",
  "size": 366,
  "content_type": "text/plain",
  "time_created": "2026-10-14T02:15:56.365Z",
  "updated": "2026-10-14T02:15:56.365Z",
  "storage_class": "STANDARD"
}
```

**Claude:** **La spec ya no vale contra el bucket: hay que volver a NEEDS WORK.** No toqué código ni la spec.

Corrí `list_objects` y `read_object_metadata` sobre los 9 objetos. No leí el contenido de ninguno, porque eso le toca a `lector-bucket`.

| Objeto | Spec | Bucket hoy | ¿Coincide? |
|---|---|---|---|
| `archive/old.log.gz` | `01:44:58.190Z` · 81 B | igual | ✅ |
| `bin/blob.bin` | `01:44:58.581Z` · 36 B | igual | ✅ |
| `edge/empty.log` | `01:44:59.311Z` · 0 B | igual | ✅ |
| `edge/nonl.log` | `01:44:59.255Z` · 11 B | igual | ✅ |
| `fixtures/hostil/notas.log` | `01:44:58.543Z` · 265 B | igual | ✅ |
| `logs/2026/10/13/deep/worker.log` | `01:44:59.392Z` · 171 B | igual | ✅ |
| `logs/app/a.log` | `01:44:59.680Z` · 97 B | igual | ✅ |
| `logs/app/b.log` | `01:44:59.291Z` · 82 B | igual | ✅ |
| **`logs/app/server.log`** | `01:44:59.210Z` · 314 B | **`2026-10-14T02:15:56.365Z` · 366 B** | ❌ |

Sigue habiendo 9 objetos y no hay página siguiente.

**`logs/app/server.log` es otro objeto.** Alguien lo volvió a subir a las 02:15:56Z. Eso es después de la lectura de la spec (02:03–02:07Z) y después de la revalidación. Ahora pesa 52 bytes más. La regla de la propia spec (`specs/gcsgrep-files-with-matches.md:47`) dice que, si una huella no coincide, la spec vuelve a NEEDS WORK.

**VCs afectados:** dependen de las líneas 3 y 5 de `server.log`, que ya no sabemos si están igual.
- **VC-INV-2:** espera la línea 3 exacta con `-n`.
- **VC-FR-1, VC-FR-3 y VC-FR-6:** esperan que `server.log` tenga match con `timeout`.
- **VC-FR-2:** espera que matchee con `-i` y que aparezca una sola vez.

Los VCs de FakeBlob (FR-7, FR-8, FR-10), FR-4, FR-5, FR-9, FR-11 y los invariantes de tests no dependen de `server.log`. En los otros 8 objetos, el `updated` es posterior al `time_created`, pero eso solo indica cambios de metadata. La huella es `time_created`, y esa coincide.

**Siguiente paso sugerido:** volver a correr `write-vcs-con-bucket` para que `lector-bucket` lea el nuevo `server.log`. Con eso se actualizan la fila de evidencia y los VCs que haga falta, y después se vuelve a pasar por `spec-reviewer` hasta tener READY. Recién ahí implementamos. ¿Lo hago?

---
**Fin:** success · turnos 13 · 58 s

**Herramientas usadas:** sesión principal 12 · dentro del subagent 0

**Eventos del JSONL no transcriptos** (ruido de runtime, sin contenido del modelo): rate_limit_event ×2, system:hook_response ×5, system:hook_started ×5, system:thinking_tokens ×6
