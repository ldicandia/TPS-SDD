# taskcli — spec

> **Estado: revisada.** Pasó el gate de `review-spec` sin preguntas abiertas.
> Construida a partir de [`taskcli-base-context.md`](./taskcli-base-context.md).
>
> Regla estructural: **cada FR y cada BR tiene un VC.** Si una línea no se puede
> verificar, no está especificada.

## Propósito

Permitir que una persona anote, consulte y complete tareas desde la terminal, sin
cambiar de contexto y sin depender de ningún servicio externo.

## Alcance

### Dentro

- Tres subcomandos: `add`, `list`, `done`.
- Persistencia local en un único archivo JSON.
- Validación de input y exit codes aptos para scripting.

### Fuera

Cada uno de estos es una decisión tomada, no un olvido:

- Editar, borrar, priorizar, etiquetar o poner fechas a una tarea.
- Múltiples listas o proyectos.
- Sincronización, red, cuentas de usuario.
- **Acceso concurrente.** Dos invocaciones simultáneas pueden pisarse la escritura.
  Aceptado para la v1 (ver el riesgo conocido en el base context).
- Interfaz interactiva (TUI) o colores en la salida.

## Actores

| Actor | Descripción |
|---|---|
| **Persona usuaria** | Ejecuta comandos en una shell y lee la salida en pantalla |
| **Script** | Ejecuta comandos y decide en base al exit code, no al texto de salida |
| **Sistema de archivos** | Guarda el store; puede fallar por permisos o espacio |

---

## Requerimientos funcionales

### FR-1 · Agregar una tarea

**Dado** un store con cualquier contenido (incluso vacío o inexistente),
**Cuando** la persona ejecuta `taskcli add "<título>"` con un título válido,
**Entonces** el sistema persiste una tarea nueva con un ID entero único, estado
`pendiente`, imprime el ID asignado por stdout, y sale con código `0`.

> **VC-1** — Sobre un store vacío, `taskcli add "comprar leche"` sale con código
> `0`, imprime un ID, y `tasks.json` contiene exactamente una tarea con título
> `"comprar leche"` y estado `pendiente`.

### FR-2 · Listar tareas

**Dado** un store con tareas pendientes y completadas,
**Cuando** la persona ejecuta `taskcli list`,
**Entonces** el sistema imprime una línea por tarea con su ID, su estado y su
título, ordenadas por ID ascendente, y sale con código `0`.

> **VC-2** — Con tres tareas cargadas (IDs 1, 2, 3) y la 2 completada, `taskcli
> list` sale con código `0` e imprime tres líneas en orden 1, 2, 3, donde la línea
> de la 2 se distingue de las otras dos por su marca de estado.

### FR-3 · Rechazar tareas duplicadas

**Dado** que ya existe una tarea **pendiente** con el título `"comprar leche"`,
**Cuando** la persona ejecuta `taskcli add "comprar leche"`,
**Entonces** el sistema la rechaza con un mensaje por stderr, sale con código `1`,
y el store queda **sin cambios**.

> **VC-3** — Agregar un duplicado sale con código `1`, escribe `duplicate` en
> stderr, y la cantidad de tareas almacenadas antes y después es idéntica.

### FR-4 · Completar una tarea

**Dado** una tarea pendiente con ID `N`,
**Cuando** la persona ejecuta `taskcli done N`,
**Entonces** el sistema marca esa tarea como completada, lo persiste, y sale con
código `0`.

> **VC-4** — Sobre una tarea pendiente con ID 1, `taskcli done 1` sale con código
> `0` y, tras la ejecución, `tasks.json` registra esa tarea con estado
> `completada`.

### FR-5 · Rechazar un ID inexistente

**Dado** un store que no contiene ninguna tarea con ID `N`,
**Cuando** la persona ejecuta `taskcli done N`,
**Entonces** el sistema informa el error por stderr, sale con código `1`, y el
store queda sin cambios.

> **VC-5** — Sobre un store con la única tarea de ID 1, `taskcli done 99` sale con
> código `1`, escribe `not found` en stderr, y el contenido de `tasks.json` es
> byte a byte idéntico al de antes.

### FR-6 · Listar un store vacío

**Dado** un store sin ninguna tarea,
**Cuando** la persona ejecuta `taskcli list`,
**Entonces** el sistema imprime un mensaje indicando que no hay tareas y sale con
código **`0`** — la ausencia de tareas no es un error.

> **VC-6** — Sobre un store vacío, `taskcli list` sale con código `0` y su stdout
> contiene un mensaje de lista vacía, no una lista de cero líneas mudas.

### FR-7 · Crear el store en el primer uso

**Dado** que `~/.taskcli/tasks.json` no existe,
**Cuando** la persona ejecuta cualquier subcomando,
**Entonces** el sistema crea el directorio y el archivo con un store vacío válido
antes de operar, sin requerir un comando de inicialización.

> **VC-7** — Con `~/.taskcli/` borrado, `taskcli list` sale con código `0`, crea
> `~/.taskcli/tasks.json`, y el archivo creado es JSON válido que representa un
> store vacío.

### FR-8 · Rechazar un store corrupto sin destruirlo

**Dado** que `tasks.json` existe pero no es JSON válido,
**Cuando** la persona ejecuta cualquier subcomando,
**Entonces** el sistema informa el error por stderr, sale con código `2`, y **no
sobrescribe el archivo**.

> **VC-8** — Con un `tasks.json` que contiene `{not json`, `taskcli list` sale con
> código `2` y el archivo conserva su contenido original exacto.

---

## Reglas de negocio

### BR-1 · Longitud del título

El título de una tarea tiene entre 1 y 200 caracteres, sin contar espacios al
principio ni al final.

*Fundamento:* un título vacío no identifica nada, y uno muy largo rompe la lectura
de la lista en una terminal de 80 columnas.
*Excepciones:* ninguna.

> **VC-9** — `taskcli add ""` y `taskcli add "   "` salen con código `1` sin
> modificar el store; un título de 200 caracteres se acepta con código `0`; uno de
> 201 sale con código `1`.

### BR-2 · Unicidad entre pendientes

Dos tareas **pendientes** no pueden compartir el mismo título. La comparación es
exacta, después de recortar espacios de los extremos.

*Fundamento:* repetir un título pendiente casi siempre significa que la persona
olvidó que ya lo había anotado.
*Excepción decidida:* **las tareas completadas no participan.** Se puede volver a
agregar un título que ya fue completado.

> **VC-10** — Con `"comprar leche"` completada, `taskcli add "comprar leche"` sale
> con código `0` y el store pasa a tener dos tareas con ese título: una completada
> y una pendiente.

### BR-3 · Los IDs no se reusan

Un ID asignado nunca se vuelve a asignar, aunque su tarea deje de existir.

*Fundamento:* un ID que cambia de significado hace que un comando copiado del
historial de la shell opere sobre la tarea equivocada.
*Excepciones:* ninguna.

> **VC-11** — Tras crear tres tareas y eliminar el archivo de la tercera del store
> a mano, la siguiente tarea creada recibe el ID `4`, no el `3`.

### BR-4 · Toda falla deja el store intacto

Si una operación falla por cualquier motivo, el store queda exactamente como estaba.
No existe la escritura parcial.

*Fundamento:* la herramienta se usa dentro de scripts; un store a medio escribir es
peor que una operación que no ocurrió.
*Excepciones:* ninguna.

> **VC-12** — Para cada caso de falla cubierto (VC-3, VC-5, VC-8, VC-9), el hash
> del archivo del store antes y después de la ejecución es idéntico.

---

## Requerimientos no funcionales

### NFR-1 · Latencia de arranque

`taskcli list` completa en **menos de 100 ms** con un store de hasta **10.000
tareas**, en un disco local SSD.

> **VC-13** — Con un store generado de 10.000 tareas, 10 ejecuciones consecutivas
> de `taskcli list` tienen una mediana de tiempo de pared menor a 100 ms.

### NFR-2 · Cota de tamaño del store

El sistema opera correctamente con un store de hasta **10.000 tareas**. Por encima
de eso el comportamiento no está especificado.

> **VC-14** — Con un store de 10.000 tareas, `add`, `list` y `done` completan sin
> error y respetan sus VCs respectivos.

### NFR-3 · Salida apta para scripting

Todo mensaje de error va a **stderr**; stdout contiene únicamente la salida útil.
Ningún caso de error imprime un stack trace.

> **VC-15** — Para cada caso de falla cubierto, stdout está vacío, stderr no lo
> está, y stderr no contiene la palabra `Traceback` ni el nombre de un archivo
> fuente de la implementación.

---

## Tabla de trazabilidad

| Requerimiento | VC | Camino |
|---|---|---|
| FR-1 | VC-1 | feliz |
| FR-2 | VC-2 | feliz |
| FR-3 | VC-3 | falla |
| FR-4 | VC-4 | feliz |
| FR-5 | VC-5 | falla |
| FR-6 | VC-6 | borde (vacío) |
| FR-7 | VC-7 | borde (primer uso) |
| FR-8 | VC-8 | falla |
| BR-1 | VC-9 | borde (límites) |
| BR-2 | VC-10 | feliz |
| BR-3 | VC-11 | borde |
| BR-4 | VC-12 | invariante |
| NFR-1 | VC-13 | medición |
| NFR-2 | VC-14 | carga |
| NFR-3 | VC-15 | invariante |

**15 requerimientos, 15 VCs, 0 huérfanos.** Esa es la propiedad que hace que la
spec sea un contrato y no una lista de deseos.

## Preguntas abiertas

Ninguna. La spec pasó el gate de revisión.

## Qué sigue

El plan de iteraciones está en [`taskcli-plan.md`](./taskcli-plan.md).
