# Entrega TP4 — `gcsgrep` contra un bucket real, por MCP

## Integrantes

| Nombre |
|---|
| Lucas Di Candia |
| Timoteo Feeney |
| Matias Sapino |

## Artefactos

Todo vive en `TP4 Plugins adn MCP/`. Qué hace cada pieza, cómo se instala y la nota de
seguridad: [`README.md`](README.md).

| Pieza del enunciado | Archivo |
|---|---|
| 🔌 Conectar: config MCP con versión fijada | [`.mcp.json`](../.mcp.json) · [`bucket/crear-bucket.sh`](../bucket/crear-bucket.sh) |
| 🎼 Orquestar: skill con procedencia | [`.claude/skills/write-vcs-con-bucket/SKILL.md`](../.claude/skills/write-vcs-con-bucket/SKILL.md) · salida: [`specs/`](../specs/) |
| 🧱 Defender: subagent lector | [`.claude/agents/lector-bucket.md`](../.claude/agents/lector-bucket.md) |
| 🧱 Defender: hook allowlist | [`.claude/hooks/gcs-allowlist.sh`](../.claude/hooks/gcs-allowlist.sh) · [`gcs_allowlist.py`](../.claude/hooks/gcs_allowlist.py) · [`.claude/settings.json`](../.claude/settings.json) · tests: [`tests/test_gcs_allowlist.py`](tests/test_gcs_allowlist.py) |
| 🧱 Defender: fixture hostil | [`bucket/objetos/fixtures/hostil/notas.log`](../bucket/objetos/fixtures/hostil/notas.log) |
| 📦 Empaquetar: plugin | [`plugin/gcsgrep-sdd/`](../plugin/gcsgrep-sdd/) (armado y commiteado) |
| 🛡️ Nota de seguridad | [`README.md` § Nota de seguridad](README.md#nota-de-seguridad) |
| Evidencia 01–07 | [`evidencia/`](evidencia/) (tabla en el README) |

## Datos de la corrida

- Proyecto de prueba: `spec-driven-511601`. Bucket: `gs://spec-driven-511601-gcsgrep-tp4`.
- Service account: `gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com`,
  `roles/storage.objectViewer` sobre el bucket.
- Server: `@google-cloud/storage-mcp@0.6.0`, sin `--enable-destructive-tools`.
- Claude Code 2.1.296, Windows 11, Node 24, Python 3.14.

## Cómo verificar

Sin GCP, desde `TP4 Plugins adn MCP/`:

```bash
py -3 -m unittest discover -s Tarea/tests -v      # 12 tests del hook
claude plugin validate plugin/gcsgrep-sdd          # ✔ Validation passed
```

Con GCP: los pasos de instalación del [README](README.md#instalación) y las sesiones de
[`evidencia/`](evidencia/), que dicen con qué comando se corrió cada una.
