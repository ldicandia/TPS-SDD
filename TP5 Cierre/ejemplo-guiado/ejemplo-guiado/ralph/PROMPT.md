# PROMPT — una vuelta de Ralph sobre taskcli

Estás construyendo `taskcli` desde cero. Cada vez que te llaman es **una vuelta**: un
contexto nuevo, sin memoria de las anteriores. Lo que sabés del proyecto está en disco.

## Antes de tocar nada, leé (en este orden)

1. `specs/taskcli-spec.md` — la spec. Es la fuente de verdad: FR, BR, NFR y sus VC.
2. `fix_plan.md` — lo que falta, en orden. Es el estado del proyecto entre vueltas.
3. `AGENT.md` — cómo se corre y se prueba, y lo que aprendieron las vueltas anteriores.

## Qué hacer en esta vuelta

1. Tomá **el primer ítem sin marcar** de `fix_plan.md`. Uno solo.
2. Antes de implementarlo, buscá en el código si ya existe. No asumas que no está.
3. Escribí primero el test del VC que cubre ese ítem, en `tests/`, con el número del VC
   en el nombre (`test_vc_01_…`). Después el código.
4. Corré la suite completa: `python3 -m pytest -q`. Tiene que quedar verde.
5. Marcá el ítem como hecho en `fix_plan.md` (`- [x]`). Si descubriste algo que falta,
   agregalo al final como ítem nuevo, citando el FR o VC.
6. Si aprendiste algo sobre cómo construir o probar, anotalo en `AGENT.md`, en una línea.
7. Hacé un commit: `git add -A && git commit -m "<VC-n>: <qué hiciste>"`.

## Reglas que no se negocian

- **Nunca borres, saltees ni debilites un test** para que la suite pase. Si un test está
  mal según la spec, frená y escribilo en `fix_plan.md` como "duda para un humano".
- **Nada de placeholders.** Ni `pass`, ni `TODO`, ni implementaciones a medias que hagan
  pasar el test sin cumplir el FR.
- **Fuera de alcance es fuera de alcance.** Si la spec dice "Fuera", no lo construyas.
- Solo la biblioteca estándar de Python, más `pytest` para los tests.

## Cuándo terminar

Si todos los ítems de `fix_plan.md` están marcados y la suite está verde, escribí
exactamente esta línea como última salida y no hagas nada más:

RALPH_DONE
