# taskcli — plan de iteraciones

> Salida del paso **Planificar**, a partir de [`taskcli-spec.md`](./taskcli-spec.md).
>
> Cada iteración es un contrato chico y verificable: termina con código andando y
> chequeos pasando, antes de que empiece la siguiente. Ahí es donde se contiene el
> drift.

## Cómo está ordenado

Por **dependencia**, no por entusiasmo. La Iteración 1 es lo mínimo que se puede
ejercitar de punta a punta; cada una siguiente agrega una capa que necesita la
anterior.

| Iteración | Entrega | Cubre |
|---|---|---|
| 1 | Agregar y listar, con persistencia | FR-1, FR-2, FR-6, FR-7, BR-1, BR-3 |
| 2 | Completar tareas y manejo de IDs inválidos | FR-4, FR-5 |
| 3 | Duplicados y robustez del store | FR-3, FR-8, BR-2, BR-4 |
| 4 | Rendimiento y contrato de scripting | NFR-1, NFR-2, NFR-3 |

---

## Iteración 1 — Agregar y listar

**Objetivo:** que exista un camino completo de punta a punta, aunque sea angosto.
Alguien tiene que poder agregar una tarea y verla.

**Alcance**

- Los tres módulos (`cli`, `core`, `store`) con sus límites definidos.
- Subcomandos `add` y `list`.
- Creación automática del store en el primer uso.
- Validación de longitud del título.
- Asignación de IDs incrementales que no se reusan.

**Fuera de alcance de esta iteración:** `done`, detección de duplicados, manejo de
store corrupto, cualquier medición de rendimiento.

**Criterios de éxito**

- [ ] VC-1 pasa — agregar sobre un store vacío
- [ ] VC-2 pasa — listar en orden por ID
- [ ] VC-6 pasa — listar un store vacío sale con código `0`
- [ ] VC-7 pasa — el store se crea solo en el primer uso
- [ ] VC-9 pasa — límites de longitud del título
- [ ] VC-11 pasa — los IDs no se reusan

**Demostrable así:**

```bash
rm -rf ~/.taskcli
taskcli list                    # "no hay tareas", exit 0
taskcli add "comprar leche"     # imprime 1, exit 0
taskcli add "llamar al banco"   # imprime 2, exit 0
taskcli list                    # dos líneas, en orden
taskcli add ""                  # error a stderr, exit 1
```

---

## Iteración 2 — Completar tareas

**Objetivo:** cerrar el ciclo de vida de una tarea. Hasta acá se pueden crear pero
no terminar.

**Alcance**

- Subcomando `done <id>`.
- Estado de la tarea persistido y reflejado en `list`.
- Rechazo de IDs inexistentes y de IDs que no son enteros.

**Criterios de éxito**

- [ ] VC-4 pasa — completar una tarea pendiente
- [ ] VC-5 pasa — ID inexistente sale con código `1` y no toca el store
- [ ] VC-2 sigue pasando — `list` ahora distingue completadas de pendientes

**Nota de regresión:** VC-2 se escribió en la Iteración 1 contra una lista donde
todo estaba pendiente. Esta iteración cambia lo que `list` imprime, así que hay que
volver a verificarlo, no darlo por hecho.

---

## Iteración 3 — Duplicados y robustez

**Objetivo:** las reglas de negocio que protegen la integridad del store.

**Alcance**

- Rechazo de títulos duplicados entre pendientes, con la excepción de las
  completadas.
- Detección de store corrupto sin sobrescribirlo.
- Escritura atómica, para garantizar que ninguna falla deje el store a medias.

**Criterios de éxito**

- [ ] VC-3 pasa — duplicado rechazado, store sin cambios
- [ ] VC-8 pasa — store corrupto, código `2`, archivo intacto
- [ ] VC-10 pasa — se puede reagregar un título ya completado
- [ ] VC-12 pasa — el hash del store es idéntico tras cada caso de falla

**Nota de implementación:** VC-12 es el que fuerza la escritura atómica (escribir a
un archivo temporal y renombrar). Si se escribe directo sobre el destino, una falla
a mitad de camino deja un store roto y VC-12 no pasa.

---

## Iteración 4 — Rendimiento y contrato de scripting

**Objetivo:** los NFRs, que hasta acá no se midieron nunca.

**Alcance**

- Un generador de store de 10.000 tareas para poder medir.
- Medición de latencia de `list`.
- Auditoría de que todos los errores van a stderr y ninguno imprime stack trace.

**Criterios de éxito**

- [ ] VC-13 pasa — mediana de `list` bajo 100 ms con 10.000 tareas
- [ ] VC-14 pasa — los tres comandos funcionan con 10.000 tareas
- [ ] VC-15 pasa — stdout limpio en errores, sin stack traces
- [ ] **Todos los VCs de las iteraciones 1 a 3 siguen pasando**

**Si VC-13 no pasa:** el candidato más probable es que `list` deserialice el JSON
completo para imprimirlo. La corrección va acá, dentro de esta iteración, contra
el umbral ya escrito — no se ajusta el umbral para que pase.

---

## Lo que quedó afuera del plan entero

Esto no es "todavía no lo hicimos": es alcance rechazado, y vive acá para que no
vuelva a aparecer en cada conversación.

| Idea | Decisión |
|---|---|
| Editar el título de una tarea | Descartado en v1 |
| Borrar tareas | Descartado en v1 — `done` cubre el caso real |
| Prioridades y fechas de vencimiento | Descartado en v1 |
| Múltiples listas / proyectos | Descartado en v1 |
| Salida con colores | Descartado; choca con NFR-3 |
| Acceso concurrente seguro | Riesgo conocido, aceptado (ver base context) |

## Qué sigue

Tras la Iteración 4, la verificación completa está en
[`taskcli-cobertura-vc.md`](./taskcli-cobertura-vc.md).
