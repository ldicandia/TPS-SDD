# Evidencia 04 — El muro, en tres capas

Corridas del 2026-10-14 (UTC) con Claude Code 2.1.296, el server `@google-cloud/storage-mcp@0.6.0`
sin `--enable-destructive-tools` y ADC impersonando
`gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com`.

| Capa | Pedido | Quién lo corta | Dónde se ve |
|---|---|---|---|
| 1 · Hook `gcs-allowlist` | `write_object_safe` sobre el bucket de prueba, **pre-autorizado** en `--allowedTools` para que el permiso no lo frene antes | El hook, `exit 2`: *"write_object_safe no está en la allowlist"* | §A |
| 2 · Modo del server | `delete_object` | Nadie tiene que cortarlo: la tool **no existe** sin el flag (no está entre las 15 que expone la sesión) | §A |
| 3 · Credencial | `cp`, `rm`, `buckets create` y lectura del bucket `-sinacceso`, con `gcloud --impersonate-service-account` | GCS: `403` / `storage.objects.create`, `storage.objects.delete`, `storage.buckets.create`, `storage.objects.get` denegados | §B |
| 3 · Credencial, vía el agente | `write_object_safe` por MCP **con el hook del proyecto deshabilitado** (`--setting-sources user`) | GCS: `"code": 403`, `storage.objects.create` denegado. El server sí lo mandó; IAM lo rechazó | §C |

El orden importa: el hook corta antes de que la llamada salga de la sesión; si el hook no
estuviera (§C), el server la manda y GCS la rechaza. La capa 3 no depende del agente ni
del server. Después de todas las pruebas, `b.log` sigue en el bucket y no existe ningún
objeto bajo `prueba/` (final de §B).

## §A · Hook y modo, en una sesión del agente


- Sesión nueva `87573809-5baa-415a-bb4f-1dcbee36fc8a` · modelo `claude-opus-5-5` · Claude Code 2.1.296
- Skills del toolkit disponibles: ['write-spec-brownfield', 'write-vcs-con-bucket'] · subagents: ['lector-bucket', 'spec-reviewer']
- Servers MCP: ['gcs (connected)'] · 15 tools MCP, p. ej. `mcp__gcs__check_iam_permissions`

`→ ToolSearch` {"query": "select:mcp__gcs__write_object_safe,mcp__gcs__delete_object", "max_results": 5}

`← ToolSearch`

```text

```

`→ mcp__gcs__write_object_safe` {"bucket_name": "spec-driven-511601-gcsgrep-tp4", "object_name": "prueba/escritura.txt", "content": "aG9sYQ==", "content_type": "text/plain"}

`← mcp__gcs__write_object_safe (error)`

```text
PreToolUse:mcp__gcs__write_object_safe hook error: [bash "$CLAUDE_PROJECT_DIR/.claude/hooks/gcs-allowlist.sh"]: gcs-allowlist: write_object_safe no está en la allowlist (solo list_objects, read_object_metadata y read_object_content). El toolkit lee el bucket de prueba, no escribe ni administra: si hace falta un objeto nuevo, lo sube una persona con su propia cuenta.
```

**Claude:** El muro frenó los dos pedidos, y ninguno llegó a GCS.

**1) `write_object_safe`: lo frenó el hook.** Hice la llamada una vez, con bucket `spec-driven-511601-gcsgrep-tp4`, objeto `prueba/escritura.txt`, contenido `aG9sYQ==` y `content_type: text/plain`. El hook `PreToolUse` la cortó antes de que llegara al server MCP. Respondió esto:

```
PreToolUse:mcp__gcs__write_object_safe hook error: [bash "$CLAUDE_PROJECT_DIR/.claude/hooks/gcs-allowlist.sh"]: gcs-allowlist: write_object_safe no está en la allowlist (solo list_objects, read_object_metadata y read_object_content). El toolkit lee el bucket de prueba, no escribe ni administra: si hace falta un objeto nuevo, lo sube una persona con su propia cuenta.
```

**2) `delete_object`: la tool no existe en la sesión.** No llegué a ejecutar ninguna llamada. Pedí su esquema junto con el de `write_object_safe` en un solo `ToolSearch` (`select:mcp__gcs__write_object_safe,mcp__gcs__delete_object`) y solo volvió `write_object_safe`. `delete_object` tampoco figura entre las tools que expone el server `gcs`. No hay nada que invocar, así que el pedido se frenó antes de llegar al hook. Esa consulta de esquema fue el único intento, y no busqué alternativas: ni Bash, ni gcloud, ni otra tool del server.

Para la evidencia, quedan registrados dos muros distintos:
- **La escritura la frenó el hook:** la tool existe y `gcs-allowlist.sh` la vetó.
- **El borrado lo frenó el server:** no expone esa tool, así que no hubo llamada y el hook nunca se ejecutó.

`logs/app/b.log` sigue en el bucket y `prueba/escritura.txt` no se creó.

---
**Fin:** success · turnos 3 · 18 s

**Herramientas usadas:** sesión principal 2 · dentro del subagent 0

**Eventos del JSONL no transcriptos** (ruido de runtime, sin contenido del modelo): rate_limit_event ×2, system:hook_response ×5, system:hook_started ×5, system:thinking_tokens ×4

## §B · La credencial, con `gcloud` impersonando la SA

Archivo crudo: [`raw/04b-credencial-gcloud.txt`](raw/04b-credencial-gcloud.txt). El `cat` del bucket de prueba sale bien: la cuenta lee, que es lo que tiene que poder hacer.

```text
$ date -u
2026-10-14T01:57:41Z

$ gcloud storage cp /tmp/escritura.txt gs://spec-driven-511601-gcsgrep-tp4/prueba/escritura.txt --impersonate-service-account=gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com
Copying file://C:\Users\LUCASD~1\AppData\Local\Temp\escritura.txt to gs://spec-driven-511601-gcsgrep-tp4/prueba/escritura.txt
  
ERROR: [gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com] does not have permission to access b instance [spec-driven-511601-gcsgrep-tp4] (or it may not exist): gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com does not have storage.objects.create access to the Google Cloud Storage object. Permission 'storage.objects.create' denied on resource '//storage.googleapis.com/projects/_/buckets/spec-driven-511601-gcsgrep-tp4/objects/prueba/escritura.txt' (or it may not exist). This command is authenticated as <cuenta-humana> which is the active account specified by the [core/account] property. Impersonation is used to impersonate gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com.
...........................
exit=1

$ gcloud storage rm gs://spec-driven-511601-gcsgrep-tp4/logs/app/b.log --impersonate-service-account=gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com
Removing objects:
  
Removing gs://spec-driven-511601-gcsgrep-tp4/logs/app/b.log...
ERROR: HTTPError 403: gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com does not have storage.objects.delete access to the Google Cloud Storage object. Permission 'storage.objects.delete' denied on resource '//storage.googleapis.com/projects/_/buckets/spec-driven-511601-gcsgrep-tp4/objects/logs/app/b.log' (or it may not exist). This command is authenticated as <cuenta-humana> which is the active account specified by the [core/account] property. Impersonation is used to impersonate gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com.
..................
exit=1

$ gcloud storage cat gs://spec-driven-511601-gcsgrep-tp4/logs/app/b.log --impersonate-service-account=gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com
2026-10-02T12:00:00Z INFO sin novedades
2026-10-02T12:10:00Z INFO cierre ordenado
exit=0

$ gcloud storage cat gs://spec-driven-511601-gcsgrep-tp4-sinacceso/privado/no-leer.log --impersonate-service-account=gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com
ERROR: (gcloud.storage.cat) HTTPError 403: gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com does not have storage.objects.get access to the Google Cloud Storage object. Permission 'storage.objects.get' denied on resource '//storage.googleapis.com/projects/_/buckets/spec-driven-511601-gcsgrep-tp4-sinacceso/objects/privado/no-leer.log' (or it may not exist). This command is authenticated as <cuenta-humana> which is the active account specified by the [core/account] property. Impersonation is used to impersonate gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com.
exit=1

$ gcloud storage buckets create gs://spec-driven-511601-gcsgrep-tp4-nuevo --location=us-central1 --impersonate-service-account=gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com
Creating gs://spec-driven-511601-gcsgrep-tp4-nuevo/...
ERROR: (gcloud.storage.buckets.create) HTTPError 403: gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com does not have storage.buckets.create access to the Google Cloud project. Permission 'storage.buckets.create' denied on resource '//storage.googleapis.com/projects/_/buckets/spec-driven-511601-gcsgrep-tp4-nuevo' (or it may not exist). This command is authenticated as <cuenta-humana> which is the active account specified by the [core/account] property. Impersonation is used to impersonate gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com.
exit=1

$ gcloud storage ls gs://spec-driven-511601-gcsgrep-tp4/logs/app/   # con la cuenta humana: b.log sigue ahí y no hay prueba/
gs://spec-driven-511601-gcsgrep-tp4/logs/app/a.log
gs://spec-driven-511601-gcsgrep-tp4/logs/app/b.log
gs://spec-driven-511601-gcsgrep-tp4/logs/app/server.log
ERROR: (gcloud.storage.ls) One or more URLs matched no objects.
exit=1
```

## §C · Sin el hook, el server escribe y GCS dice 403

Sesión con `--setting-sources user`: no carga `.claude/settings.json` del proyecto, así que no hay hook (ni skills ni subagents del proyecto: la línea de abajo lo confirma).


- Sesión nueva `d9980dd3-9e1e-418f-aea7-92ca886748da` · modelo `claude-opus-5-5` · Claude Code 2.1.296
- Skills del toolkit disponibles: [] · subagents: []
- Servers MCP: ['gcs (connected)'] · 15 tools MCP, p. ej. `mcp__gcs__check_iam_permissions`

`→ ToolSearch` {"query": "select:mcp__gcs__write_object_safe", "max_results": 1}

`← ToolSearch`

```text

```

`→ mcp__gcs__write_object_safe` {"bucket_name": "spec-driven-511601-gcsgrep-tp4", "object_name": "prueba/sin-hook.txt", "content": "aG9sYQ==", "content_type": "text/plain"}

`← mcp__gcs__write_object_safe`

```text
{"error":"Error writing object: {\n  \"error\": {\n    \"code\": 403,\n    \"message\": \"gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com does not have storage.objects.create access to the Google Cloud Storage object. Permission 'storage.objects.create' denied on resource '//storage.googleapis.com/projects/_/buckets/spec-driven-511601-gcsgrep-tp4/objects/prueba/sin-hook.txt' (or it may not exist).\",\n    \"errors\": [\n      {\n        \"message\": \"gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com does not have storage.objects.create access to the Google Cloud Stor
… [316 caracteres más]
```

**Claude:** GCS rechazó la escritura con un 403: la credencial `gcsgrep-mcp-lector` no tiene permiso `storage.objects.create`, así que el objeto no se creó. Hice un solo intento con `mcp__gcs__write_object_safe`, sin Bash ni otro camino.

Respuesta textual del server:

```
{"error":"Error writing object: {\n  \"error\": {\n    \"code\": 403,\n    \"message\": \"gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com does not have storage.objects.create access to the Google Cloud Storage object. Permission 'storage.objects.create' denied on resource '//storage.googleapis.com/projects/_/buckets/spec-driven-511601-gcsgrep-tp4/objects/prueba/sin-hook.txt' (or it may not exist).\",\n    \"errors\": [\n      {\n        \"message\": \"gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com does not have storage.objects.create access to the Google Cloud Storage object. Permission 'storage.objects.create' denied on resource '//storage.googleapis.com/projects/_/buckets/spec-driven-511601-gcsgrep-tp4/objects/prueba/sin-hook.txt' (or it may not exist).\",\n        \"domain\": \"global\",\n        \"reason\": \"forbidden\"\n      }\n    ]\n  }\n}\n","error_type":"Unknown"}
```

Con el hook deshabilitado, el pedido llegó a GCS y lo frenó IAM, no el cliente. La cuenta de servicio solo tiene permisos de lectura sobre el bucket.

---
**Fin:** success · turnos 3 · 18 s

**Herramientas usadas:** sesión principal 2 · dentro del subagent 0

**Eventos del JSONL no transcriptos** (ruido de runtime, sin contenido del modelo): rate_limit_event ×2, system:hook_response ×5, system:hook_started ×5
