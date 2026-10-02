# Tarea Lección 3 — Un toolkit SDD

**En equipo de trabajo.** Se entrega antes de la Lección 4 · [cómo se entrega](../../entrega.md)

## Qué hay que hacer

Andá más allá de un solo skill. Encodeá la disciplina SDD de las Lecciones 1 y 2 en un
**toolkit** chico y funcional que el agente cargue solo.

| Pieza | Qué es | Ejemplo |
|---|---|---|
| 📘 **Un skill** | Un paso del pipeline que hoy corrés a mano | Un `write-spec` brownfield que siempre exige alcance dentro/fuera + invariantes |
| 👥 **Un subagent** | Un ayudante enfocado, con brief propio | Un `explorar` solo-lectura, o un `review-spec` independiente |
| 🪝 **Un hook** | Un guardrail que **garantiza** una práctica | Bloquear un commit si la suite de tests existente está roja |

**Cada pieza tiene que encodear un concepto de las Lecciones 1–2** — cobertura de VCs,
alcance acotado, seguridad ante regresiones o higiene de contexto. El toolkit es el
entregable; el punto es que la disciplina SDD ahora corra sin que la retipeen.

## Cómo encararlo

### 1 · Skill — encodeá un flujo

Agarrá un paso del pipeline que ya repitieron. `description` **en forma de trigger**,
pasos numerados, una plantilla copiable y anti-patrones. Mapeá cada parte a un concepto
SDD.

```yaml
description: Usar cuando el usuario pide especificar un cambio a código existente —
  exige alcance dentro/fuera + invariantes.
```

### 2 · Subagent — delegá para enfocar

Escribí su brief: **qué puede hacer** (¿solo lectura?), **qué devuelve** (¿notas? ¿un
veredicto?) y **con qué formato**. Mostrá que mantiene limpio el contexto principal.

> Solo explorar, sin editar. Devolvé módulos, interfaces y riesgos como notas.

### 3 · Hook — garantizá un guardrail

Elegí un evento y un chequeo. **Demostrá que dispara y que puede bloquear.**

> `pre-commit`: corré la suite existente; exit distinto de cero ⇒ bloqueá el commit.

### 4 · (Opcional) Una rule

Fijá una restricción permanente en `CLAUDE.md` o `AGENTS.md` — por ejemplo, que cada
commit referencie su spec e iteración.

### 5 · Probá que cada uno funciona

Disparen el skill, corran el subagent, **hagan que el hook bloquee algo**. Capturen
evidencia de los tres.

## Qué se entrega

| Artefacto | Qué tiene que contener |
|---|---|
| **El toolkit** | Un skill + un subagent + un hook, en el repo del equipo |
| **README** | Qué concepto SDD de L1–L2 encodea cada pieza |
| **Evidencia** | Transcripciones de las tres piezas **ejecutándose**, y del hook bloqueando |

## Lo que más se falla

**Artefactos que se ven bien y nunca se ejercitaron.** Un hook que existe, tiene buena
sintaxis y jamás vetó nada **no está terminado**. El hook es la única pieza que
garantiza: el resto persuade.

Mantené cada pieza chica y real — un skill que entra en una pantalla, un subagent con
un brief de un párrafo, un hook de unas pocas líneas.

## Antes de entregar

Mirá [`../ejemplo-guiado/README.md`](../ejemplo-guiado/README.md): un toolkit para
ADRs — dos skills, dos subagents y tres hooks que **corren de verdad** — con el
recorrido para leerlos. Es otra práctica a propósito: muestra la forma de cada pieza,
no la respuesta.
