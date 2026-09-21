# gcsgrep — spec

> Estado: revisada. Esta especificación define el contrato de la v1 y no deja
> preguntas abiertas. La implementación se divide en iteraciones en
> [`gcsgrep-plan.md`](./gcsgrep-plan.md).

## Propósito

Permitir que una persona busque texto dentro del contenido de objetos de Google
Cloud Storage sin descargarlos previamente a disco.

## Alcance

### Dentro de la v1

- CLI ejecutable desde una terminal.
- Ubicaciones con formato `gs://bucket` o `gs://bucket/prefijo`.
- Autenticación mediante Application Default Credentials.
- Búsqueda literal, sensible a mayúsculas por defecto.
- Flag `-i` para ignorar mayúsculas y minúsculas.
- Flag `-n` para mostrar el número de línea.
- Lectura secuencial y por streaming.
- Objetos de texto UTF-8.
- Exit codes compatibles con `grep`.
- Límites de seguridad para objetos y bytes leídos.

### Fuera de la v1

- Expresiones regulares.
- S3, Azure Blob u otros proveedores.
- Escritura, copia, movimiento, borrado o cambio de permisos en GCS.
- Archivos `.gz` y otros formatos comprimidos.
- Salida JSON, colores, `-l`, `-c` y `--include`.
- Concurrencia configurable.
- Snapshot global del bucket.

## Actores

| Actor | Interacción |
|---|---|
| Persona usuaria | Ejecuta el CLI y lee los resultados. |
| Script | Ejecuta el CLI y decide según el exit code. |
| Google Cloud Storage | Enumera y entrega objetos; puede devolver errores de red o permisos. |

## Requerimientos funcionales

### FR-1 — Aceptar una ubicación de GCS

**Dado** un URI con formato `gs://bucket` o `gs://bucket/prefijo`, **cuando** la
persona ejecuta `gcsgrep "patrón" URI`, **entonces** la herramienta valida la
ubicación, identifica el bucket y usa el resto como prefijo de nombres de objetos.

> **VC-1** — Un URI válido permite iniciar el escaneo; un URI sin esquema `gs://`,
> sin bucket o con formato inválido termina con código `2` y un mensaje por
> `stderr`.

### FR-2 — Enumerar objetos bajo el prefijo

**Dado** un bucket accesible, **cuando** se ejecuta una búsqueda sobre un URI,
**entonces** la herramienta enumera los objetos cuyo nombre comienza con el
prefijo indicado, sin modificar el bucket.

> **VC-2** — Con tres objetos bajo el prefijo y uno fuera de él, el escaneo visita
> exactamente los tres objetos incluidos y no realiza operaciones de escritura.

### FR-3 — Buscar coincidencias en streaming

**Dado** un objeto de texto UTF-8, **cuando** se lo procesa, **entonces** la
herramienta lee su contenido de forma incremental, sin descargar el objeto
completo a un archivo local, y detecta las líneas que contienen el patrón literal.

> **VC-3** — Un objeto con coincidencias produce una salida por cada línea
> coincidente y el test usa un stream que entrega datos incrementalmente.

### FR-4 — Informar objeto y línea

**Dado** un match, **cuando** no se usa `-n`, **entonces** la salida contiene el
URI del objeto y el texto de la línea; cuando se usa `-n`, también contiene el
número de línea.

> **VC-4** — Para un match en la línea 3, `gcsgrep -n "timeout" gs://logs/`
> produce una línea con el formato `gs://logs/objeto:3:...`.

### FR-5 — Búsqueda sin distinguir mayúsculas

**Dado** un patrón y un objeto con una variante de mayúsculas, **cuando** se usa
`-i`, **entonces** la comparación se realiza sin distinguir mayúsculas ni
minúsculas.

> **VC-5** — El patrón `timeout` encuentra `TIMEOUT`, `Timeout` y `timeout` con
> `-i`, pero no encuentra las dos primeras variantes sin ese flag.

### FR-6 — Continuar ante errores de objetos

**Dado** un conjunto de objetos donde uno no puede leerse, **cuando** se ejecuta
una búsqueda, **entonces** la herramienta informa el error por `stderr`, continúa
con los demás objetos y devuelve código `2` al finalizar.

> **VC-6** — Un objeto que falla no impide encontrar un match en el objeto
> siguiente; `stdout` contiene el match, `stderr` contiene el error y el exit code
> es `2`.

### FR-7 — Reportar ausencia de coincidencias

**Dado** un conjunto de objetos procesables sin matches, **cuando** termina la
búsqueda, **entonces** la herramienta no imprime resultados en `stdout` y sale
con código `1`.

> **VC-7** — Una búsqueda sin coincidencias deja `stdout` vacío y devuelve `1`.

### FR-8 — Informar progreso

**Dado** un escaneo de muchos objetos, **cuando** se alcanza cada intervalo de
progreso de 100 objetos, **entonces** la herramienta informa por `stderr` cuántos
objetos procesó hasta ese momento.

> **VC-8** — Al procesar 100 objetos, `stderr` contiene un aviso de progreso y
> `stdout` no se contamina con ese aviso.

## Reglas de negocio

### BR-1 — Solo lectura

La herramienta nunca crea, modifica, copia, mueve, borra ni cambia permisos de
objetos o buckets. Solo usa operaciones de listado y lectura.

*Fundamento:* el objetivo es buscar contenido y no convertir el CLI en un gestor
de GCS.

> **VC-9** — Un escaneo exitoso deja inalterados los nombres, tamaños, contenidos
> y metadatos de los objetos de prueba.

### BR-2 — No ampliar permisos

La herramienta usa únicamente las credenciales disponibles para quien la ejecuta.
No acepta ni almacena credenciales en la línea de comandos.

*Fundamento:* evita que el CLI se convierta en un mecanismo para eludir las
políticas de acceso de GCP.

> **VC-10** — Sin credenciales válidas o sin permiso de lectura, el comando falla
> con código `2`, no imprime contenido protegido y no realiza escrituras.

### BR-3 — Guardrail de costo

Por defecto, una ejecución puede inspeccionar como máximo 1.000 objetos o 1 GiB
total de contenido, lo que ocurra primero. Al alcanzar el límite, la ejecución se
detiene, informa el motivo por `stderr` y devuelve código `2`.

*Fundamento:* leer objetos de GCS puede generar costos y un prefijo amplio puede
ser accidental.

> **VC-11** — Una ejecución que alcanza cualquiera de los límites deja de leer
> objetos adicionales, informa el límite y termina con código `2`.

### BR-4 — Objetos no textuales

Los objetos cuyo nombre termina en `.gz` o cuyo contenido inicial contiene un byte
NUL se saltean. Un objeto UTF-8 inválido se informa como error de lectura. Saltar
un objeto no textual no cancela la búsqueda.

*Fundamento:* evita imprimir basura binaria y mantiene el alcance de la v1
acotado a texto sin compresión.

> **VC-12** — Un objeto `.gz` y uno binario no producen matches ni basura en
> `stdout`; el objeto de texto siguiente sí se procesa.

### BR-5 — Generación del objeto

Cuando GCS informa una generación al enumerar un objeto, la lectura intenta usar
esa generación. No se garantiza una snapshot global del bucket: objetos creados
después del listado pueden no ser incluidos.

> **VC-13** — Si la generación enumerada deja de estar disponible, se informa el
> error, se continúa con los demás objetos y la ejecución termina con código `2`.

## Requerimientos no funcionales

### NFR-1 — Memoria

La implementación debe procesar el contenido incrementalmente y no acumular más
de 64 MiB de contenido de un objeto en memoria durante una búsqueda.

> **VC-14** — Un objeto de al menos 128 MiB se procesa sin crear un buffer que
> contenga el objeto completo y el pico de memoria adicional medido es menor a
> 64 MiB.

### NFR-2 — Reintentos de red

Los errores transitorios de lectura deben reintentarse hasta 3 veces usando el
comportamiento de reintentos de la librería oficial de GCS. Después de agotar los
reintentos, el objeto se considera fallido y se continúa.

> **VC-15** — Un stream que falla dos veces y luego responde correctamente permite
> completar la lectura; uno que falla cuatro veces se informa como error y no
> detiene los objetos siguientes.

### NFR-3 — Scripting

Los resultados van a `stdout`, los errores y el progreso a `stderr`, y ningún caso
de error imprime un stack trace al usuario.

> **VC-16** — En cada caso de error cubierto, `stdout` contiene únicamente los
> resultados parciales permitidos, `stderr` no está vacío y no contiene un
> traceback de implementación.

## Tabla de trazabilidad

| Requerimiento | VC |
|---|---|
| FR-1 | VC-1 |
| FR-2 | VC-2 |
| FR-3 | VC-3 |
| FR-4 | VC-4 |
| FR-5 | VC-5 |
| FR-6 | VC-6 |
| FR-7 | VC-7 |
| FR-8 | VC-8 |
| BR-1 | VC-9 |
| BR-2 | VC-10 |
| BR-3 | VC-11 |
| BR-4 | VC-12 |
| BR-5 | VC-13 |
| NFR-1 | VC-14 |
| NFR-2 | VC-15 |
| NFR-3 | VC-16 |

**16 requerimientos, 16 VCs, 0 huérfanos.**

## Preguntas abiertas

Ninguna. Las decisiones pendientes están documentadas como alcance diferido en
`gcsgrep-plan.md`.
