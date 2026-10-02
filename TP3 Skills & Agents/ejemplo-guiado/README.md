# Ejemplo guiado — Lección 3 · Un toolkit para ADRs

**El caso:** `turnos-api`, una API ficticia de turnos médicos que registra sus
decisiones de arquitectura en **ADRs** (Architecture Decision Records). El toolkit
encodea esa práctica para que el agente la cargue solo: dos skills, dos subagents,
tres hooks y dos archivos de rules.

Esto **corre de verdad**. No es pseudocódigo de slide: podés instalarlo hoy y verlo
dispararse y bloquear.

**No es la respuesta de la tarea.** La tarea pide encodear *tu* flujo SDD de las
Lecciones 1 y 2. Esto encodea otra práctica, a propósito: venís a ver **qué forma
tiene cada pieza**, no a copiarla.

## Qué hay acá

| Carpeta | Qué es | El concepto de la clase |
|---|---|---|
| [`skills/`](./skills/) | `write-adr` y `supersede-adr` | Un flujo que se carga **cuando la situación aparece** |
| [`subagents/`](./subagents/) | `adr-explorer` (solo lectura) y `adr-reviewer` (revisor independiente) | Firewall de contexto e independencia |
| [`hooks/`](./hooks/) | 3 hooks, 2 de ellos **bloquean** | Determinismo: garantizar, no persuadir |
| [`CLAUDE.md.ejemplo`](./CLAUDE.md.ejemplo) · [`AGENTS.md.ejemplo`](./AGENTS.md.ejemplo) | Rules siempre activas | Lo que vale en *toda* sesión |
| [`docs/adr/`](./docs/adr/) | Dos ADRs y su índice | La salida del toolkit |

## Qué es un ADR, en dos líneas

Un archivo corto y numerado que dice **qué se decidió, qué se descartó y por qué**.
Una vez aceptado no se edita: si la decisión cambia, se escribe otro que lo
reemplaza. Mirá [`docs/adr/0001-postgres-para-los-turnos.md`](./docs/adr/0001-postgres-para-los-turnos.md).

## El recorrido guiado

### Paso 1 · La `description` es el trigger, no el título

Abrí los dos `SKILL.md` y leé **solo** el front-matter:

> *"Usar cuando la persona toma o acaba de tomar una decisión de arquitectura…"*
> *"Usar cuando una decisión que ya tiene un ADR aceptado cambia o se revierte…"*

Cada una nombra **la situación que lo invoca**, con el fraseo real ("elegimos X
sobre Y", "ya no usamos X"). Y las dos se distinguen entre sí: una frase que dispara
`write-adr` no debería disparar `supersede-adr`. Si las dos disparan con lo mismo,
una de las descriptions está mal.

### Paso 2 · Lo determinístico va en un script

`write-adr` no le pide al modelo que cuente archivos para saber el próximo número:
corre [`scripts/next-adr-number.sh`](./skills/write-adr/scripts/next-adr-number.sh).
El script no ocupa ventana hasta que corre, y da siempre el mismo resultado. Si un
paso de tu skill se puede chequear con código, que lo haga un script.

### Paso 3 · Por qué un hook y no una rule

`CLAUDE.md.ejemplo` dice que un ADR aceptado no se edita. Eso persuade.
[`hooks/adr-immutable.sh`](./hooks/adr-immutable.sh) lo garantiza: bloquea cualquier
edición de un ADR aceptado, salvo cambiar su línea `Estado:`.

> **Skill, rule y subagent persuaden. El hook garantiza.**

Fijate qué protegen los dos hooks que bloquean: **invariantes de este proyecto** ("un
ADR aceptado no cambia", "una dependencia nueva tiene su ADR"). Esa es la forma que
conviene llevarse: un hook que hace cumplir algo que *tu* proyecto decidió.

### Paso 4 · El brief del subagent, y lo que el brief no garantiza

Abrí [`subagents/adr-explorer.md`](./subagents/adr-explorer.md). Buscá tres cosas:
qué **puede** hacer, qué **devuelve** y con qué **formato**. Después mirá el
front-matter: `tools: Read, Grep, Glob`. El brief *pide* solo lectura; `tools` lo
*garantiza*. El [README de subagents](./subagents/README.md) explica el trade-off.

## Hacelo vos

Hasta que no ves un hook bloqueándote, no entendés la diferencia con una rule.

```
1. En un repo cualquiera: copiá skills/ a .claude/skills/, subagents/*.md a
   .claude/agents/ y docs/adr/ a docs/adr/.
2. Instalá los hooks siguiendo hooks/README.md. Necesitás jq.
3. Sin nombrar el skill: "elegimos httpx sobre requests, dejemos registrado por
   qué". ¿Cargó write-adr? ¿Lanzó adr-explorer antes de escribir?
4. Pedile: "actualizá el ADR-0001, ahora usamos también Redis". El hook tiene
   que bloquear la edición, y el agente tiene que ir a supersede-adr.
5. Pedile que sume una dependencia y commitee. El hook tiene que vetar el commit.
6. Guardá las transcripciones.
```

**Señal de que te salió:** el hook te bloqueó, y el agente usó el mensaje de stderr
para corregir el camino en vez de reintentar.

**Señal de que no:** tuviste que nombrar el skill para que se cargue. Arreglá la
`description`, no los pasos.

## Cómo se traslada a la tarea

| En este ejemplo | La pregunta para tu toolkit |
|---|---|
| `write-adr` encodea cómo se registra una decisión acá | ¿Qué paso de tu flujo SDD repetiste a mano en L1–L2, y qué decisiones propias tiene? |
| `adr-explorer` busca decisiones previas en su propia ventana | ¿Qué trabajo ruidoso de tu flujo conviene aislar? |
| `adr-immutable` protege un invariante del proyecto | ¿Qué práctica SDD — o qué invariante de tus specs — tiene que valer pase lo que pase? |

## El error más común

Un toolkit que se ve impecable y nunca se ejercitó. Un hook con buena sintaxis que
jamás vetó nada **no está terminado** — y así se corrige en la tarea. La evidencia de
que algo corrió vale más que su prolijidad.
