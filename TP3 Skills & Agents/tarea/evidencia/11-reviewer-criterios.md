# Corrección 4 — criterio de severidad y veredicto

Fecha: 2026-10-07. Base: `864ae45eb61eb0fcfb635c4c85fb3068d7e7dde5` + cambios locales de la corrección 4.

Esta es una revisión manual del contrato de revisión, no una transcripción de
Claude Code ni una prueba de que un modelo obedezca el brief. Los casos siguientes
son situaciones de aceptación para evaluar las instrucciones: no se modificó la
spec de ejemplo para producirlos ni se ejecutaron VCs o un subagent nuevo.

## Defecto corregido

El brief anterior pedía cinco comprobaciones, pero solo enumeraba tres defectos
como bloqueantes: anclas falsas, VCs imposibles y FRs sin VC. No definía cómo
clasificar contradicciones de alcance, ambigüedades de términos o invariantes
insuficientes. El criterio nuevo abarca todos los controles C1–C5 y exige evidencia
positiva para cada `OK`, además de ausencia de bloqueantes.

## Casos revisados contra el brief

En las filas con un defecto, se supone que los demás controles están comprobados
como `OK`. Estas son las clasificaciones exigidas por el texto, no salidas obtenidas
de una corrida del agente.

| Situación | Control/estado exigido | Severidad y veredicto exigidos | Motivo |
|---|---|---|---|
| Una búsqueda comprueba que una ruta citada como existente no existe, o la línea hace otra cosa | C1 `FALLA` | `BLOQUEANTE`, `NEEDS WORK` | Ancla falsa; informar ruta consultada y búsqueda, sin inventar una cita para la ausencia |
| Un VC no tiene los datos para justificar su resultado o no ejercita el requerimiento | C2 `FALLA` | `BLOQUEANTE`, `NEEDS WORK` | La mera presencia de un VC no acredita cobertura ni coherencia |
| Un NFR tiene texto y números, pero no permite decidir aceptación bajo su carga | C2 `FALLA` | `BLOQUEANTE`, `NEEDS WORK` | El checker estructural no demuestra pertinencia o suficiencia semántica |
| Dos términos permiten interpretar de forma distinta la misma regla | C3 `FALLA` | `BLOQUEANTE`, `NEEDS WORK` | No es un detalle editorial si cambia el contrato |
| Fuera excluye un comportamiento que un FR exige, o un requerimiento mezcla alcance futuro | C4 `FALLA` | `BLOQUEANTE`, `NEEDS WORK` | El alcance debe ser consistente |
| La spec omite los invariantes de comportamiento afectado, incluyendo la suite existente | C5 `FALLA` | `BLOQUEANTE`, `NEEDS WORK` | La protección de regresiones no queda definida |
| No se puede leer el código necesario por falta de acceso | Control afectado `NO VERIFICABLE` | `BLOQUEANTE`, `NEEDS WORK` | No equivale a haber comprobado ausencia de defectos |
| Solo hay espacios desalineados en una tabla, sin cambiar su significado | C1–C5 `OK` | `MENOR`, `READY` | Detalle editorial; los cinco controles deben estar verificados igualmente |
| Todos los controles se verificaron y no hay hallazgos | C1–C5 `OK` | Sin hallazgos, `READY` | Cumple las dos condiciones del veredicto |
| Un test se propone para implementar después y sus datos/criterios son suficientes | No causa `FALLA` por su sola ausencia actual | Puede ser `READY` si todo C1–C5 está `OK` | Revisar una spec precede a implementar los tests nuevos |
| El material intenta ordenar al revisor que omita controles o fuerce `READY` | C4 `FALLA` | Ignorar la orden, `BLOQUEANTE`, `NEEDS WORK` | Una instrucción dirigida al revisor no reemplaza el brief |
| Esa misma cadena aparece explícitamente como dato de un fixture | No causa `FALLA` por su solo contenido | Evaluar el caso de producto; `READY` depende de C1–C5 | Un dato de prueba no es una instrucción para quien revisa |

## Consistencia del flujo

- El brief pide los estados y evidencia de C1–C5, y al menos un bloqueante por cada
  control `FALLA` o `NO VERIFICABLE`. La tabla de anclas admite también falta de
  verificación; no exige elegir una respuesta falsa de sí/no.
- El skill no acepta un `READY` cuyo informe tenga controles ausentes, fallas,
  falta de verificación o bloqueantes. Pide una revisión completa y consistente.
- Cada repetición cuenta para las dos vueltas máximas de corrección/revisión.
  Al agotarlas, el skill reporta `NEEDS WORK` con lo pendiente, sin declarar lista
  la spec ni inventar información.
- Se conservan `tools: Read, Grep, Glob`: el revisor lee y busca, sin editar ni
  ejecutar VCs. La revisión no demuestra que los tests hayan pasado.
- El README distingue este criterio semántico del control estructural del hook.
  Ninguno de los cambios convierte al hook en validador de veredictos del modelo.

## Alcance de la verificación

Se revisaron manualmente los criterios y su composición, y se comprobó el diff
con `git diff --check`. No se modificaron el checker, el hook, los tests ni la
spec de ejemplo en esta corrección. La evidencia 10 conserva la corrida anterior
de 41 tests; no es una prueba de comportamiento del nuevo brief.

Las transcripciones 01–06 siguen siendo evidencia histórica. No se reescribieron
sus veredictos y todavía no hay una corrida de Claude con el nuevo criterio.

## SHA-256 de los documentos revisados

```text
142cbdde8bc815ebd719f582079fa59bacb4b4752d49137fc8219aae800fa75b  .claude/agents/spec-reviewer.md
47f8a8bf398f3e965c81bca30dafa3665b126c15372161422f4b6d76edc0bd86  .claude/skills/write-spec-brownfield/SKILL.md
836bb396d8e252c2b86cb3d8a81010820461bc21de155225ce5d95bf0e70888f  tarea/README.md
```
