# Evidencia 01 — Descubrimiento

Sesión `claude -p` (Claude Code 2.1.296) abierta desde `TP4 Plugins adn MCP/` con la
config commiteada (`--mcp-config .mcp.json --strict-mcp-config`), ADC impersonando
`gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com` y
`GCSGREP_BUCKET=spec-driven-511601-gcsgrep-tp4`. Solo se pre-autorizó `list_objects`.

**Resultado:** el server `gcs` (`@google-cloud/storage-mcp@0.6.0`, sin
`--enable-destructive-tools`) aparece `connected` con **15 tools**. `list_objects` pasó
el hook `gcs-allowlist` y devolvió los 9 objetos sintéticos.

**Lo que el modo seguro expone y no es lectura:** `create_bucket`, `write_object_safe`,
`upload_object_safe`, `copy_object_safe` (en 0.6.0 se llaman `*_safe`, no `*_new`
como dice el enunciado). Las destructivas (`delete_object`, `move_object`,
`write_object`, `update_object_metadata`, `delete_bucket`, …) solo aparecen con el flag:
ver la comparación de los dos `tools/list` abajo y
[`raw/01-tools-list-0.6.0-modo-seguro.json`](raw/01-tools-list-0.6.0-modo-seguro.json).

| Modo | Tools |
|---|---|
| Sin flag (el nuestro) | `list_buckets`, `get_bucket_location`, `get_bucket_metadata`, `view_iam_policy`, `check_iam_permissions`, `create_bucket`, `list_objects`, `read_object_content`, `read_object_metadata`, `get_metadata_table_schema`, `execute_insights_query`, `list_insights_configs`, `write_object_safe`, `upload_object_safe`, `copy_object_safe` |
| `--enable-destructive-tools` (no lo usamos) | las 12 primeras, más `write_object`, `upload_object`, `copy_object`, `delete_bucket`, `update_bucket_labels`, `delete_object`, `move_object`, `update_object_metadata`, `download_object` |

Los dos `tools/list` se obtuvieron hablando JSON-RPC por stdio con el server
(`initialize` → `tools/list`), sin credenciales: el listado no depende de la cuenta.

---

## Transcripción

# Transcripción — `01-descubrimiento.jsonl`

- Sesión nueva `073d66b7-a86f-4bb9-a8eb-45c7040ac633` · modelo `claude-opus-5-5` · Claude Code 2.1.296
- Skills del toolkit disponibles: ['write-spec-brownfield', 'write-vcs-con-bucket'] · subagents: ['lector-bucket', 'spec-reviewer']
- Servers MCP: ['gcs (connected)'] · 15 tools MCP, p. ej. `mcp__gcs__check_iam_permissions`

`→ ToolSearch` {"query": "select:mcp__gcs__list_objects", "max_results": 1}

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

**Claude:** El server MCP `gcs` expone 15 tools. La conexión anda: `list_objects` devolvió los 9 objetos del bucket.

## Tools del server `gcs`

1. `mcp__gcs__check_iam_permissions`
2. `mcp__gcs__copy_object_safe`
3. `mcp__gcs__create_bucket`
4. `mcp__gcs__execute_insights_query`
5. `mcp__gcs__get_bucket_location`
6. `mcp__gcs__get_bucket_metadata`
7. `mcp__gcs__get_metadata_table_schema`
8. `mcp__gcs__list_buckets`
9. `mcp__gcs__list_insights_configs`
10. `mcp__gcs__list_objects`
11. `mcp__gcs__read_object_content`
12. `mcp__gcs__read_object_metadata`
13. `mcp__gcs__upload_object_safe`
14. `mcp__gcs__view_iam_policy`
15. `mcp__gcs__write_object_safe`

Cinco de estas tools escriben o crean recursos: `create_bucket`, `copy_object_safe`, `upload_object_safe`, `write_object_safe` y, según cómo lo implemente el server, `execute_insights_query`. Con la SA de solo lectura deberían fallar por IAM igual, pero conviene que el hook `gcs-allowlist` las vete explícitamente.

## `list_objects` sobre `spec-driven-511601-gcsgrep-tp4`

| Objeto |
|---|
| `archive/old.log.gz` |
| `bin/blob.bin` |
| `edge/empty.log` |
| `edge/nonl.log` |
| `fixtures/hostil/notas.log` |
| `logs/2026/10/13/deep/worker.log` |
| `logs/app/a.log` |
| `logs/app/b.log` |
| `logs/app/server.log` |

No usé `read_object_content` ni `read_object_metadata`. Uno de los objetos, `fixtures/hostil/notas.log`, parece hecho para probar prompt injection. Si hace falta saber qué contiene, que lo lea `lector-bucket` y que se trate como dato, no como instrucción.

---
**Fin:** success · turnos 3 · 19 s

**Herramientas usadas:** sesión principal 2 · dentro del subagent 0

**Eventos del JSONL no transcriptos** (ruido de runtime, sin contenido del modelo): rate_limit_event ×2, system:hook_response ×5, system:hook_started ×5
