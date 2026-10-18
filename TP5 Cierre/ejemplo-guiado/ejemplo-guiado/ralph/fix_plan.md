# fix_plan — taskcli

El estado del proyecto entre vueltas. Una vuelta toma **el primer ítem sin marcar**.
Ordenado por el plan de iteraciones de la Lección 1 (`taskcli-plan.md`).

## Iteración 1 — Agregar y listar

- [ ] Estructura del paquete (`taskcli/cli.py`, `core.py`, `store.py`, `__main__.py`) y `tests/` con pytest
- [ ] VC-7 — el store se crea solo en el primer uso
- [ ] VC-1 — agregar sobre un store vacío
- [ ] VC-9 — límites de longitud del título
- [ ] VC-11 — los IDs no se reusan
- [ ] VC-2 — listar en orden por ID
- [ ] VC-6 — listar un store vacío sale con código 0

## Iteración 2 — Completar tareas

- [ ] VC-4 — completar una tarea pendiente
- [ ] VC-5 — ID inexistente sale con código 1 y no toca el store

## Iteración 3 — Duplicados y robustez

- [ ] VC-3 — duplicado rechazado, store sin cambios
- [ ] VC-8 — store corrupto, código 2, archivo intacto
- [ ] VC-10 — se puede reagregar un título ya completado
- [ ] VC-12 — el hash del store es idéntico tras cada caso de falla

## Iteración 4 — Rendimiento y contrato de scripting

- [ ] VC-13 — mediana de `list` bajo 100 ms con 10.000 tareas
- [ ] VC-14 — los tres comandos funcionan con 10.000 tareas
- [ ] VC-15 — stdout limpio en errores, sin stack traces
