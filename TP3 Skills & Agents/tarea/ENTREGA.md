# Entrega TP3 — Toolkit SDD

El [`entrega.md`](../../entrega.md) de la raíz, que linkea el enunciado, es el índice
del TP1 y no cubre este trabajo. Este archivo es el índice del TP3.

## Integrantes

| Nombre |
|---|
| Lucas Di Candia |
| Timoteo Feeney |
| Matias Sapino |

## Las tres piezas

Todo vive en [`TP3 Skills & Agents/.claude/`](../.claude/). El detalle de qué concepto
de las Lecciones 1–2 encodea cada una está en el [README](README.md).

| Pieza | Archivo | Concepto L1–L2 |
|---|---|---|
| 📘 Skill `write-spec-brownfield` | [`.claude/skills/write-spec-brownfield/`](../.claude/skills/write-spec-brownfield/) | Cobertura de VCs y alcance acotado |
| 👥 Subagent `spec-reviewer` | [`.claude/agents/spec-reviewer.md`](../.claude/agents/spec-reviewer.md) | Gate independiente e higiene de contexto |
| 🪝 Hook `spec-gate` | [`.claude/hooks/spec-gate.sh`](../.claude/hooks/spec-gate.sh) + [`commit_command.py`](../.claude/hooks/commit_command.py) | Cobertura de VCs, garantizada en el commit |
| 📝 Rule (opcional) | [`CLAUDE.md`](../CLAUDE.md) | Restricciones siempre activas del proyecto |

## Evidencia

Doce artefactos en [`evidencia/`](evidencia/), indexados en el
[README](README.md#evidencia). Los tres que piden la consigna:

- **El skill dispara solo:** [`01`](evidencia/01-skill-y-subagent.md) y
  [`02`](evidencia/02-trigger-positivo.md), con [`03`](evidencia/03-trigger-negativo-revisar.md)
  y [`04`](evidencia/04-trigger-negativo-pregunta.md) como casos que **no** tienen que disparar.
- **El subagent corre:** [`01`](evidencia/01-skill-y-subagent.md) — tres revisiones, con
  la tabla C1–C5, en su propia ventana de contexto.
- **El hook bloquea:** [`05`](evidencia/05-hook-bloquea.md) dentro de una sesión real, y
  [`06`](evidencia/06-hook-corrige-y-pasa.md) con el agente corrigiendo desde el stderr
  hasta que el commit pasa.

## Cómo verificar

Desde `TP3 Skills & Agents/`, sin instalar nada (solo `bash`, `git` y Python ≥ 3.8):

```bash
python3 -m unittest discover -s tarea/tests -v   # 54 tests
python3 .claude/skills/write-spec-brownfield/scripts/check_spec.py tarea/evidencia/specs/gcsgrep-count.md
```

El procedimiento completo, incluido cómo disparar el hook a mano, está en
[README.md § Reproducir](README.md#reproducir).

## Estado

- Las tres piezas corren y están ejercitadas dentro de Claude Code (2.1.292 y 2.1.294).
- La corrección 5 cerró cinco huecos del gate y del checker; se verificó en Linux
  ([`evidencia/12`](evidencia/12-correccion5-linux.txt)) y todavía no tiene corrida
  nativa en Windows.
- Límites declarados —qué **no** garantiza el hook— en
  [README.md § Límites conocidos](README.md#qué-bloquea-el-hook-exactamente).
