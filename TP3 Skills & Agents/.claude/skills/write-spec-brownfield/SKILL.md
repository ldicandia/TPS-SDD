---
name: write-spec-brownfield
description: Usar cuando el usuario pide especificar un cambio, flag o feature sobre código que ya existe en el repo, antes de implementarlo — "especificá este cambio", "escribí la spec para agregar X a Y", "armá la spec antes de tocar código", "quiero sumarle X a <herramienta>, hacé la spec". Produce specs/<slug>.md con alcance dentro/fuera, invariantes con su comando, cada FR con su VC y cada decisión anclada a archivo:línea. No usar para revisar una spec ya escrita (eso es el subagent spec-reviewer), para implementar código, ni para un proyecto sin código previo.
---

# write-spec-brownfield

Especificar un cambio sobre código existente sin que la spec salga con los huecos que
nos marcaron en el TP1 y el TP2: requerimientos sin VC, decisiones fundadas en la
consigna y no en el código, alcance futuro mezclado con el de ahora.

## Pasos

1. **Fijá la base.** Identificá el proyecto que cambia y corré `git rev-parse HEAD`.
   Ese hash va en `**Base:**`. *(Brownfield: la spec habla de una revisión concreta.)*
2. **Leé antes de escribir.** Abrí los archivos que el cambio toca y los tests
   existentes. Anotá `archivo:línea` de cada lugar que vas a citar. Si algo no lo
   encontrás, no lo inventes: ponelo en "Fuera" o preguntá.
3. **Copiá la plantilla.** Copiá [plantilla.md](plantilla.md) a `specs/<slug>.md` dentro
   del proyecto abierto, donde corre el hook (o en la ruta que pida el usuario, siempre
   bajo una carpeta `specs/` del proyecto abierto; las subcarpetas también se validan).
   Las rutas al código que cambia van relativas a ese proyecto o declaradas al
   principio de la spec.
4. **Alcance dentro/fuera.** "Dentro": cada fila nombra el archivo entre backticks y qué
   cambia. "Fuera": cada fila con su porqué. *(Alcance acotado.)*
5. **Invariantes.** Lo que hoy funciona y no se puede romper — como mínimo, que la
   suite existente sigue verde. Cada `INV-N` con su `VC-INV-N` y el comando que lo
   comprueba. *(Seguridad ante regresiones.)*
6. **Requerimientos.** Un `### FR-N` por comportamiento, en Dado/Cuando/Entonces, y
   abajo su `VC-FR-N` con la entrada exacta y la salida/exit code esperados. Los datos
   del VC tienen que alcanzar para producir ese resultado. Completá cada bullet
   Dado/Cuando/Entonces en su propia línea. Cada VC ocupa una línea, con entrada
   o comando no vacío entre backticks antes de `→` y resultado después.
   Cada NFR lleva bullets **Métrica**, **Umbral** y **Carga**: qué se mide,
   límite numérico con unidad/condición y carga numérica con unidades. Una cita
   `archivo:línea` no aporta el número del umbral ni de la carga.
   *(Cobertura de VCs.)*
7. **Decisiones.** Cada `D-N` con la alternativa descartada y un fundamento
   `archivo:línea` del código base que la sostiene. *(Spec anclada al código.)*
8. **Chequeá.** Corré
   `python3 .claude/skills/write-spec-brownfield/scripts/check_spec.py specs/<slug>.md`
   (en Windows, `py -3` en vez de `python3`). Corregí cada línea que reporte y repetí
   hasta exit 0. Pegá en "## Trazabilidad" la tabla que imprime: esa sección es
   obligatoria y el checker la exige. Es una validación estructural: no ejecuta VCs
   ni comprueba la veracidad de los datos, resultados o anclas; el paso 9 revisa su
   coherencia con el código.
9. **Revisión independiente.** Lanzá el subagent `spec-reviewer` con la ruta de la
   spec. Comprobá que el informe incluya C1–C5, sus estados y evidencia. Solo aceptá
   `READY` con los cinco controles `OK` y ningún `BLOQUEANTE`; si falta un control o
   el veredicto contradice el informe, pedí una revisión completa y consistente.
   Con `NEEDS WORK`, corregí los hallazgos `BLOQUEANTE` o completá la información
   `NO VERIFICABLE`; no inventes datos o anclas para obtener `READY`. Volvé al paso 8
   y relanzalo. Máximo dos vueltas de corrección/revisión, incluyendo las motivadas
   por informes incompletos o inconsistentes; si sigue, reportá lo pendiente.
   *(Gate independiente.)*
10. **Terminá.** Listo cuando `check_spec.py` sale 0 y la revisión cumple el criterio
    de `READY` del paso 9. Si se agotan las vueltas sin cumplirlo, informá `NEEDS WORK`
    con los bloqueantes y controles pendientes; no declares lista la spec.
    Respondé con la ruta de la spec, la cantidad de FR/INV/VC y el veredicto. No
    implementes ni commitees: el hook `spec-gate` vuelve a chequear la spec en el commit.

## Plantilla

La plantilla completa está en [plantilla.md](plantilla.md). La forma que impone:

```markdown
### FR-1 · <comportamiento>
- **Dado** …
- **Cuando** …
- **Entonces** …
- **VC-FR-1** · `<comando exacto>` → <salida y exit code>

| D-1 | <elegido> | <descartado> | `<archivo>:<línea>` <qué hace ese código> |
```

Un FR sin su `VC-FR-N` debajo, o una decisión sin `archivo:línea`, no pasa
`check_spec.py` ni el hook del commit.

## Anti-patrones

- **FR sin VC, o VC sin datos.** "Con 3 objetos, termina con 0" sin decir que los
  objetos contienen el patrón (VC-23 del TP1): el resultado esperado es imposible.
- **Decisión fundada en la consigna.** "Usamos libssh porque la consigna prohíbe el
  binario" (decisión 3 del TP2, VE-5 en 0): el fundamento tiene que citar código.
- **Dos palabras para lo mismo.** "trozo" en un FR y "tramo" en un NFR (TP1): definí el
  término una vez en "Términos" y usá solo esa palabra.
- **Alcance futuro adentro.** Plan de iteraciones o "en v2 …" dentro de la spec
  (TP2): lo diferido va en "Fuera" con su porqué, o al plan.
- **NFR sin medida.** "Debe ser rápido" y una cita de código no fijan aceptación:
  completá los tres campos de métrica, umbral y carga.
- **Fuera genérico.** "Otras mejoras" no acota nada: nombrá módulos, flags o SO.
