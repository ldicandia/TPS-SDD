# Evidencia 07 — Costo de contexto

`/context` capturado el 2026-10-14 con Claude Code 2.1.296 (`claude -p "/context"`,
`MSYS_NO_PATHCONV=1` para que Git Bash no convierta `/context` en una ruta), desde
`TP4 Plugins adn MCP/`, **con** el server (`--mcp-config .mcp.json --strict-mcp-config`)
y **sin** él (`--strict-mcp-config`). Salidas completas en
[`raw/07-context-con-server.txt`](raw/07-context-con-server.txt) y
[`raw/07-context-sin-server.txt`](raw/07-context-sin-server.txt).

## Resumen

| | Tokens |
|---|---|
| **Server `gcs` (15 tools, carga diferida)** | **3,2k** (3.203 sumando la tabla) |
| de eso, las 3 que usa el toolkit (`list_objects` 489, `read_object_content` 154, `read_object_metadata` 153) | 796 |
| de eso, las 12 que el hook veta igual | 2.407 |
| Subagents del toolkit (`lector-bucket` 173, `spec-reviewer` 183) | 356 |
| Skills del toolkit (`write-spec-brownfield` ~230, `write-vcs-con-bucket` ~180) | ~410 |
| `CLAUDE.md` del proyecto | 652 |
| **Total que agrega el toolkit con el server** | **≈ 4,6k** de una ventana de 1M |

La única categoría que cambia entre las dos capturas es `MCP tools (deferred) 3.2k`;
el resto (prompt, tools del sistema, skills y agents de la cuenta) es idéntico. Las tools
del server se cargan en diferido: lo que ocupa siempre es la lista, y cada schema entra
completo cuando el agente lo pide con `ToolSearch` (se ve en las transcripciones 01, 04 y 06).

**Conclusión:** el costo es chico, pero tres cuartos de esos tokens son de tools que el
hook igual veta, y cada sesión con el plugin arranca el server (un `npx`) y dispara el
hook en cada llamada MCP. Conviene habilitar el plugin **solo en el repo de gcsgrep**, no
en todos: fuera de ahí no aporta nada y suma superficie.

## Tabla de tools del server, tal como la imprime `/context`

```text
### MCP Tools

| Tool | Server | Tokens |
|------|--------|--------|
| mcp__gcs__check_iam_permissions | gcs | 165 |
| mcp__gcs__copy_object_safe | gcs | 279 |
| mcp__gcs__create_bucket | gcs | 348 |
| mcp__gcs__execute_insights_query | gcs | 236 |
| mcp__gcs__get_bucket_location | gcs | 123 |
| mcp__gcs__get_bucket_metadata | gcs | 123 |
| mcp__gcs__get_metadata_table_schema | gcs | 273 |
| mcp__gcs__list_buckets | gcs | 111 |
| mcp__gcs__list_insights_configs | gcs | 142 |
| mcp__gcs__list_objects | gcs | 489 |
| mcp__gcs__read_object_content | gcs | 154 |
| mcp__gcs__read_object_metadata | gcs | 153 |
| mcp__gcs__upload_object_safe | gcs | 249 |
| mcp__gcs__view_iam_policy | gcs | 119 |
| mcp__gcs__write_object_safe | gcs | 239 |

```

## Categorías, con y sin server

```text
# con server
| Category | Tokens | Percentage |
|----------|--------|------------|
| System prompt | 2.4k | 0.2% |
| System tools | 4.6k | 0.5% |
| MCP tools (deferred) | 3.2k | 0.3% |
| System tools (deferred) | 14k | 1.4% |
| Custom agents | 3.4k | 0.3% |
| Memory files | 748 | 0.1% |
| Skills | 8.9k | 0.9% |
| Messages | 10 | 0.0% |
| Free space | 947k | 94.7% |
| Autocompact buffer | 33k | 3.3% |

# sin server
| Category | Tokens | Percentage |
|----------|--------|------------|
| System prompt | 2.4k | 0.2% |
| System tools | 4.6k | 0.5% |
| System tools (deferred) | 14k | 1.4% |
| Custom agents | 3.4k | 0.3% |
| Memory files | 748 | 0.1% |
| Skills | 8.9k | 0.9% |
| Messages | 10 | 0.0% |
| Free space | 947k | 94.7% |
| Autocompact buffer | 33k | 3.3% |
```
