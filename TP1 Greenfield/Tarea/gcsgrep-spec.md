# gcsgrep — spec

> Estado: revisada (v1.1). Corrige los hallazgos del reporte de revisión externa
> `correccion-de-specs v1.1` sobre el hash `a9c77bd`. Esta especificación define
> el contrato de la v1 y no deja preguntas abiertas. Fue construida a partir de
> [`gcsgrep-base-context.md`](./gcsgrep-base-context.md). La implementación se
> divide en iteraciones en [`gcsgrep-plan.md`](./gcsgrep-plan.md).

## Propósito

Permitir que una persona busque texto dentro del contenido de objetos de Google
Cloud Storage sin descargarlos previamente a disco.

## Alcance

### Dentro de la v1

- CLI ejecutable desde una terminal, con la forma
  `gcsgrep [-i] [-n] [--max-objects N] [--max-bytes N] PATRÓN URI`.
- URIs con formato `gs://bucket` o `gs://bucket/prefijo`.
- Autenticación mediante Application Default Credentials.
- Búsqueda literal, sensible a mayúsculas por defecto.
- Flag `-i` para ignorar mayúsculas y minúsculas.
- Flag `-n` para mostrar el número de línea.
- Flag `--max-objects N` para ajustar el límite de objetos inspeccionados.
- Flag `--max-bytes N` para ajustar el límite de bytes declarados.
- Lectura secuencial (un objeto a la vez) y por streaming.
- Objetos de texto UTF-8.
- Exit codes `0`, `1` y `2` con la convención de `grep`.
- Límites de seguridad para objetos y bytes inspeccionados.

### Fuera de la v1

- Expresiones regulares (`-E`).
- S3, Azure Blob u otros proveedores.
- Escritura, copia, movimiento, borrado o cambio de permisos en GCS.
- Archivos `.gz` y otros formatos comprimidos.
- Salida JSON, colores, `-l`, `-c`, `--include`, `-v` y `-r`.
  `-r` no hace falta porque el prefijo ya define el alcance recursivo.
- Concurrencia configurable.
- Snapshot global del bucket.
- Modo sin límites de costo.
- Interfaz web, API de red o librería importable. *Motivo:* el usuario objetivo
  trabaja en la terminal y ya usa `grep`. Un CLI con exit codes cubre el uso
  interactivo y el de scripts sin sumar una superficie pública que haya que
  mantener.
- Observabilidad más allá de lo que se imprime por `stderr` (progreso y errores):
  no hay logs estructurados, métricas ni trazas. *Motivo:* es una herramienta de
  corrida corta. `stderr` y el exit code alcanzan para diagnosticar.

## Actores

| Actor | Interacción |
|---|---|
| Persona usuaria | Ejecuta el CLI y lee los resultados. |
| Script | Ejecuta el CLI y decide según el exit code. |
| Google Cloud Storage | Enumera y entrega objetos; puede devolver errores de red o permisos. |

## Terminología

Estos términos se usan con un único significado en todo el documento.

| Término | Definición |
|---|---|
| URI | Argumento de ubicación con esquema `gs://`: `gs://bucket` o `gs://bucket/prefijo`. |
| Prefijo | Todo lo que sigue a `gs://bucket/`, comparado literalmente contra el nombre del objeto. No se le agrega `/`. Si falta, vale `""`. |
| Objeto inspeccionado | Objeto enumerado bajo el prefijo que cuenta para los límites de BR-3, se lea o se saltee. |
| Línea | Secuencia de caracteres terminada en `\n`, en `\r\n` o en el fin del objeto. El terminador no forma parte de la línea. La última línea sin terminador cuenta como línea. Se numeran desde `1` en cada objeto. |
| Match | Línea que contiene el patrón como subcadena literal. |
| Objeto fallido | Objeto que no pudo leerse completo (UTF-8 inválido, permiso denegado, generación no disponible o reintentos agotados). |

## Requerimientos funcionales

### FR-1 — Buscar en un bucket completo

**Dado** un bucket accesible con objetos bajo distintos prefijos, **cuando** la
persona ejecuta `gcsgrep PATRÓN gs://bucket`, **entonces** `stdout` contiene los
matches de los objetos de todos los prefijos del bucket.

> **VC-1** — Contra el bucket de prueba del emulador, `gcsgrep timeout gs://B`
> imprime matches de objetos bajo `app/` y bajo `other/`. `gs://B/` produce la
> misma salida.

### FR-2 — Buscar bajo un prefijo

**Dado** un URI `gs://bucket/prefijo`, **cuando** se ejecuta una búsqueda,
**entonces** solo se inspeccionan los objetos cuyo nombre comienza literalmente
con `prefijo`, sin modificar el bucket.

> **VC-2** — Contra el bucket de prueba del emulador, con objetos `logs/a.log`,
> `logs/b.log`, `logs/c.log` y `logs-other/d.log` que contienen el patrón:
> `gcsgrep P gs://B/logs/` imprime matches solo de los tres primeros, y
> `gcsgrep P gs://B/logs` imprime matches de los cuatro.

### FR-3 — Detectar matches en streaming

**Dado** un objeto de texto UTF-8, **cuando** se lo procesa, **entonces** la
herramienta lee su contenido de forma incremental, sin escribirlo en un archivo
local, y emite una línea de salida por cada match.

> **VC-3** — Un objeto entregado por un stream en trozos de 64 KiB, con 2 matches
> en líneas que cruzan el borde entre trozos, produce exactamente 2 líneas en
> `stdout`, y no se crea ningún archivo temporal.
>
> **VC-17** — Un objeto con contenido `a\nb timeout` (la última línea sin `\n`)
> produce con `-n` la salida `gs://B/obj:2:b timeout`.
>
> **VC-18** — Un objeto de 0 bytes no produce salida en `stdout` ni en `stderr` y
> cuenta como objeto inspeccionado. Si es el único objeto, el exit code es `1`.

### FR-4 — Formato de salida sin `-n`

**Dado** un match, **cuando** no se usa `-n`, **entonces** `stdout` recibe la
línea `<URI del objeto>:<texto de la línea>`, donde el URI del objeto es
`gs://<bucket>/<nombre del objeto>` y el separador es un único `:`.

> **VC-4** — Para el objeto `gs://B/app/server.log` con la línea
> `connection timeout after 30s`, `gcsgrep timeout gs://B/app/` imprime
> exactamente `gs://B/app/server.log:connection timeout after 30s`.

### FR-5 — Búsqueda sin distinguir mayúsculas

**Dado** un patrón y un objeto con una variante de mayúsculas, **cuando** se usa
`-i`, **entonces** la comparación se realiza sin distinguir mayúsculas ni
minúsculas.

> **VC-5** — El patrón `timeout` encuentra `TIMEOUT`, `Timeout` y `timeout` con
> `-i`, pero no encuentra las dos primeras variantes sin ese flag.

### FR-6 — Continuar ante un objeto fallido

**Dado** un conjunto de objetos donde uno es un objeto fallido, **cuando** se
ejecuta una búsqueda, **entonces** `stderr` recibe
`gcsgrep: no se pudo leer <URI del objeto>: <detalle>`, se procesan los objetos
restantes y el exit code es `2`, aunque haya habido matches.

> **VC-6** — Con `broken/latin1.log` (UTF-8 inválido) seguido de `broken/ok.log`
> (contiene `timeout`), `gcsgrep timeout gs://B/broken/` deja en `stdout` el match
> de `ok.log`, en `stderr` una línea que empieza con
> `gcsgrep: no se pudo leer gs://B/broken/latin1.log:`, y termina con exit `2`.

### FR-7 — Informar ausencia de matches

**Dado** un conjunto de objetos sin objetos fallidos y sin matches, **cuando**
termina la búsqueda, **entonces** `stdout` queda vacío y el exit code es `1`.

> **VC-7** — Una búsqueda sin matches deja `stdout` vacío y devuelve `1`.

### FR-8 — Informar progreso

**Dado** un escaneo, **cuando** el número de objetos inspeccionados llega a un
múltiplo de 100, **entonces** `stderr` recibe la línea
`gcsgrep: objetos procesados: <N>`.

> **VC-8** — Con 100 objetos bajo el prefijo, `stderr` contiene exactamente una
> línea `gcsgrep: objetos procesados: 100` y `stdout` no contiene ninguna línea
> que empiece con `gcsgrep:`. Con 99 objetos, `stderr` no contiene esa línea.

### FR-9 — Formato de salida con `-n`

**Dado** un match, **cuando** se usa `-n`, **entonces** `stdout` recibe la línea
`<URI del objeto>:<número de línea>:<texto de la línea>`.

> **VC-19** — Para un match en la línea 4 de `gs://B/app/server.log`,
> `gcsgrep -n timeout gs://B/app/` imprime exactamente
> `gs://B/app/server.log:4:connection timeout after 30s`.

### FR-10 — Exit code con matches

**Dado** un escaneo que termina sin objetos fallidos y sin alcanzar un límite,
**cuando** hubo al menos un match, **entonces** el exit code es `0`.

> **VC-20** — `gcsgrep timeout gs://B/app/` sobre objetos legibles con al menos un
> match devuelve `0` y `stderr` no contiene líneas de error.

### FR-11 — Rechazar un URI inválido

**Dado** un URI sin esquema `gs://`, sin bucket (`gs://`, `gs:///x`) o con
espacios en el nombre del bucket, **cuando** se ejecuta el comando, **entonces**
`stderr` recibe `gcsgrep: <motivo>`, `stdout` queda vacío y el exit code es `2`,
sin cargar credenciales ni contactar a GCS.

> **VC-21** — `gcsgrep x logs/app`, `gcsgrep x gs://` y `gcsgrep x "gs://a b"`
> terminan con `2`, `stderr` empieza con `gcsgrep: ` y la fábrica de clientes de
> GCS no se invoca.

### FR-12 — Fallo al enumerar

**Dado** un URI cuyo bucket no existe o no se puede listar, **cuando** se
ejecuta la búsqueda, **entonces** `stderr` recibe
`gcsgrep: no se pudo enumerar gs://<bucket>/<prefijo>: <detalle>` y el exit code
es `2`.

> **VC-22** — Contra el emulador, `gcsgrep x gs://bucket-inexistente/` termina con
> `2`, `stdout` vacío y `stderr` empieza con `gcsgrep: no se pudo enumerar`.

### FR-13 — Ajustar el límite de objetos

**Dado** un entero positivo `N`, **cuando** se usa `--max-objects N`,
**entonces** el límite de objetos inspeccionados de BR-3 pasa a ser `N` en lugar
de `1000`.

> **VC-23** — Con 3 objetos bajo el prefijo, `--max-objects 2` termina con `2` y
> el motivo del límite, y `--max-objects 3` no alcanza el límite.

### FR-14 — Ajustar el límite de bytes

**Dado** un entero positivo `N` (en bytes), **cuando** se usa `--max-bytes N`,
**entonces** el límite de bytes declarados de BR-3 pasa a ser `N` en lugar de
`1073741824` (1 GiB).

> **VC-24** — Con objetos que declaran 10 y 20 bytes, `--max-bytes 29` termina
> con `2` y el motivo del límite antes de leer el segundo objeto, y
> `--max-bytes 30` no alcanza el límite.

### FR-15 — Rechazar un valor de límite inválido

**Dado** un valor que no es un entero positivo (`0`, `-5`, `abc`), **cuando** se
pasa a `--max-objects` o a `--max-bytes`, **entonces** el comando termina con
exit `2` y un mensaje de uso por `stderr`, sin contactar a GCS.

> **VC-25** — `gcsgrep --max-objects 0 x gs://B` y `gcsgrep --max-bytes abc x gs://B`
> terminan con `2`, `stdout` vacío y `stderr` contiene `debe ser un entero positivo`.

### FR-16 — Orden de la salida

**Dado** un escaneo con matches en varios objetos, **cuando** se imprimen los
resultados, **entonces** los objetos aparecen en el orden en que GCS los enumera
(lexicográfico por nombre) y, dentro de cada objeto, las líneas aparecen en orden
creciente.

> **VC-26** — Con matches en `app/b.log` (líneas 1 y 3) y `app/a.log` (línea 2),
> la salida con `-n` es, en este orden: `a.log:2`, `b.log:1`, `b.log:3`. Dos
> corridas sobre el mismo bucket producen la misma salida byte a byte.

## Reglas de negocio

### BR-1 — Solo lectura

La herramienta nunca crea, modifica, copia, mueve, borra ni cambia permisos de
objetos o buckets. Solo usa operaciones de listado y lectura.

*Fundamento:* el objetivo es buscar contenido, no convertir el CLI en un gestor
de GCS.

*Excepciones:* ninguna. La preparación y limpieza del bucket de prueba la hacen
los tests, no `gcsgrep`.

> **VC-9** — Tras correr todos los escaneos de la suite de integración, los
> nombres, tamaños, hashes MD5, generaciones y metadatos de los objetos de prueba
> son idénticos a los registrados antes.

### BR-2 — No ampliar permisos

La herramienta usa únicamente las Application Default Credentials de quien la
ejecuta. No acepta ni almacena credenciales en la línea de comandos. Los permisos
IAM mínimos son `storage.objects.list` sobre el bucket y `storage.objects.get`
sobre los objetos (incluidos en `roles/storage.objectViewer`).

- Sin credenciales válidas: `stderr` recibe
  `gcsgrep: no se pudieron cargar las credenciales de GCP: <detalle>`, `stdout`
  queda vacío y el exit code es `2`.
- Sin `storage.objects.list`: se comporta como FR-12.
- Sin `storage.objects.get` sobre un objeto: ese objeto es un objeto fallido
  (FR-6).

*Fundamento:* evita que el CLI se convierta en un mecanismo para eludir las
políticas de acceso de GCP.

*Excepciones:* si la variable `STORAGE_EMULATOR_HOST` está definida, el cliente
oficial se conecta al emulador sin credenciales. Se usa solo para la verificación
de integración y no otorga acceso a GCS real.

> **VC-10** — Sin ADC (`GOOGLE_APPLICATION_CREDENTIALS` apuntando a un archivo
> inexistente y sin emulador), `gcsgrep x gs://B` termina con `2`, `stdout` vacío y
> `stderr` empieza con `gcsgrep: no se pudieron cargar las credenciales`. Con una
> identidad sin `storage.objects.get` (solo en GCP real), el objeto se informa
> como fallido, no se imprime su contenido y el exit code es `2`.

### BR-3 — Guardrail de costo

Por defecto, una ejecución inspecciona como máximo 1.000 objetos y 1 GiB
(1.073.741.824 bytes) de tamaño declarado en el listado, sumado sobre los objetos
inspeccionados. Los valores se ajustan con `--max-objects` (FR-13) y
`--max-bytes` (FR-14).

- El límite de objetos se alcanza al enumerar el objeto número `N + 1`. Un prefijo
  con exactamente `N` objetos no alcanza el límite.
- El límite de bytes se alcanza cuando el tamaño declarado del siguiente objeto
  haría que la suma supere `N`. Ese objeto no se lee.

Al alcanzar un límite, no se lee ningún objeto más, `stderr` recibe
`gcsgrep: límite de seguridad alcanzado: máximo <N> objetos` (o `... <N> bytes`),
los matches ya impresos quedan en `stdout` y el exit code es `2`.

*Fundamento:* leer objetos de GCS puede generar costos y un prefijo amplio puede
ser accidental.

*Excepciones:* los objetos salteados por BR-4 cuentan igual para ambos límites,
porque el límite se evalúa sobre el listado, antes de leerlos. No existe un modo
ilimitado.

> **VC-11** — Con 1.001 objetos bajo el prefijo y valores por defecto, la
> ejecución termina con `2` y el mensaje de límite de objetos. Con exactamente
> 1.000 objetos no aparece el mensaje de límite.
>
> **VC-27** — Si un objeto que declara más de 1 GiB sigue a otro con match, el
> match del primero queda en `stdout`, el objeto grande no se lee, `stderr`
> contiene el mensaje de límite de bytes y el exit code es `2`.

### BR-4 — Objetos no textuales

Se saltean sin error los objetos cuyo nombre termina en `.gz` (sin distinguir
mayúsculas) y los objetos cuyos primeros 8.192 bytes contienen un byte NUL
(`0x00`). Un objeto que no se saltea y contiene UTF-8 inválido es un objeto
fallido (FR-6). Saltar un objeto no produce salida y no cancela la búsqueda.

*Fundamento:* evita imprimir basura binaria y mantiene el alcance de la v1
acotado a texto sin compresión. `Content-Type` no se usa porque sus metadatos
pueden ser incorrectos.

*Excepciones:* un byte NUL después de los primeros 8.192 bytes no hace saltear el
objeto. Si ese objeto es UTF-8 válido, se procesa como texto. Trade-off aceptado:
un texto codificado en UTF-16 contiene bytes NUL y se saltea como binario.

> **VC-12** — Un objeto `.gz` y uno con un byte NUL en los primeros bytes, ambos
> con el patrón, no producen líneas en `stdout` ni en `stderr`. El objeto de
> texto siguiente sí produce su match.

### BR-5 — Generación del objeto

Cuando GCS informa una generación al enumerar un objeto, la lectura pide esa
generación. No se garantiza una snapshot global del bucket: los objetos creados
después del listado pueden no incluirse.

*Fundamento:* GCS permite identificar versiones individuales, pero congelar todo
el bucket excede el alcance de la v1.

*Excepciones:* si el listado no informa generación, se lee la versión vigente al
momento de la lectura.

> **VC-13** — Si la generación enumerada deja de estar disponible antes de
> leerla, el objeto es un objeto fallido (FR-6): se informa por `stderr`, se
> continúa con los demás objetos y el exit code es `2`.

## Requerimientos no funcionales

### NFR-1 — Memoria

**Condición de carga:** un único objeto de 128 MiB compuesto por líneas de hasta
1 KiB. **Métrica:** RSS pico del proceso (`Maximum resident set size` de
`/usr/bin/time -v`) menos el RSS pico de la misma corrida sobre un objeto de
0 bytes. **Umbral:** menor a 64 MiB.

*Excepción:* una sola línea más larga que el umbral se retiene completa en
memoria, porque la unidad de match es la línea.

> **VC-14** — Bajo la condición de carga de NFR-1, contra el emulador, la
> diferencia de RSS pico medida con `/usr/bin/time -v` es menor a 64 MiB.

### NFR-2 — Reintentos de red

Un error transitorio de lectura (timeout, conexión cortada, HTTP 429 o 5xx) se
reintenta hasta 3 veces, es decir, hasta 4 intentos por tramo, con backoff
exponencial: 1 s, 2 s y 4 s, el comportamiento por defecto de la librería oficial
de GCS. El reintento vuelve a pedir el tramo en curso desde el mismo offset, así
que no se reimprimen líneas ya emitidas. Al agotar los reintentos, el objeto es un
objeto fallido (FR-6): sus líneas ya impresas quedan en `stdout`, se continúa con
el resto y el exit code final es `2`.

> **VC-15** — Un stream que falla dos veces y luego responde permite leer el
> objeto completo: cada match aparece una sola vez, `stderr` no tiene error para
> ese objeto y el exit code es `0`. Un stream que falla cuatro veces produce en
> `stderr` `gcsgrep: no se pudo leer <URI>: ...`, el objeto siguiente se procesa y
> el exit code es `2`.

### NFR-3 — Scripting

Los resultados van a `stdout`. Los errores, los límites y el progreso van a
`stderr` con el prefijo `gcsgrep: `. Ningún caso de error imprime un stack trace.

> **VC-16** — En cada caso de error cubierto (VC-6, VC-10, VC-11, VC-21, VC-22,
> VC-25), `stdout` contiene solo matches con el formato de FR-4 o FR-9, `stderr`
> no está vacío y no contiene `Traceback`.

### NFR-4 — Rendimiento

**Condición de carga:** un único objeto de 128 MiB con líneas de hasta 1 KiB y
sin matches, servido por el emulador local, en la misma máquina para ambas
mediciones. **Métrica:** tiempo de pared de
`gcsgrep patrón gs://B/obj` frente al de la alternativa que la herramienta
reemplaza: descargar el objeto a disco con el cliente oficial
(`blob.download_to_filename`) y luego correr `grep -F patrón`. **Umbral:** a lo
sumo 1,5 veces el tiempo de la alternativa.

> **VC-28** — Bajo la condición de carga de NFR-4, la mediana de 5 corridas de
> `gcsgrep` no supera 1,5 veces la mediana de 5 corridas de descarga más
> `grep -F`.

## Verificación de integración

Los VCs marcados "contra el emulador" o "contra el bucket de prueba" se ejecutan
de punta a punta con el CLI real (`python -m gcsgrep`) sobre un bucket sembrado en
el emulador Floci (`STORAGE_EMULATOR_HOST`), sin inyectar dobles. La misma suite
corre contra GCP real con `GCSGREP_INTEGRATION=1`. El caso IAM de VC-10 solo es
reproducible en GCP real.

## Tabla de trazabilidad

| Requerimiento | VC |
|---|---|
| FR-1 | VC-1 |
| FR-2 | VC-2 |
| FR-3 | VC-3, VC-17, VC-18 |
| FR-4 | VC-4 |
| FR-5 | VC-5 |
| FR-6 | VC-6 |
| FR-7 | VC-7 |
| FR-8 | VC-8 |
| FR-9 | VC-19 |
| FR-10 | VC-20 |
| FR-11 | VC-21 |
| FR-12 | VC-22 |
| FR-13 | VC-23 |
| FR-14 | VC-24 |
| FR-15 | VC-25 |
| FR-16 | VC-26 |
| BR-1 | VC-9 |
| BR-2 | VC-10 |
| BR-3 | VC-11, VC-27 |
| BR-4 | VC-12 |
| BR-5 | VC-13 |
| NFR-1 | VC-14 |
| NFR-2 | VC-15 |
| NFR-3 | VC-16 |
| NFR-4 | VC-28 |

**25 requerimientos, 28 VCs, 0 huérfanos.**

## Cambios respecto de la versión anterior

| Antes | Ahora | Motivo (hallazgo) |
|---|---|---|
| FR-1 (URI válido o inválido) | FR-1 (bucket), FR-2 (prefijo), FR-11 (URI inválido) | Atomicidad (2.3), Entonces observable (3.5), error solo en el VC (2.7) |
| VC-1, parte inválida | VC-21 | Se movió con FR-11 |
| FR-4 (con y sin `-n`) | FR-4 (sin `-n`), FR-9 (con `-n`) | Atomicidad (2.3), formato literal (2.8 p7) |
| Exit `0` solo en el alcance | FR-10 | 2.8 p8 |
| BR-3 sin forma de ajustar | BR-3 + FR-13, FR-14, FR-15 | 2.8 p6, 5.6 |
| — | FR-12, FR-16 | Error de listado; orden de salida (2.8 p9) |
| NFR-1 sin condición de carga | NFR-1 con carga, métrica RSS y herramienta | 4.1, 4.3 |
| — | NFR-4 | 4.1 |
| BRs sin Excepciones; BR-5 sin Fundamento | Agregados | 2.9 |

## Preguntas abiertas

Ninguna. Las funcionalidades diferidas están en `gcsgrep-plan.md`.
