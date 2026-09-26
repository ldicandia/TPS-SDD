# gcsgrep — spec

> Estado: revisada (v1.3). Esta especificación define el contrato de la v1 y no
> deja preguntas abiertas. Fue construida a partir de
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
  ejecución corta. `stderr` y el exit code alcanzan para diagnosticar.

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
| Ejecución | Una invocación de `gcsgrep`, desde el parseo de argumentos hasta el exit code. |
| URI | Argumento de ubicación con esquema `gs://`: `gs://bucket` o `gs://bucket/prefijo`. |
| URI inválido | Argumento de ubicación que no es un URI: le falta el esquema `gs://` (`logs/app`), le falta el bucket (`gs://`, `gs:///x`) o el nombre del bucket contiene espacios (`gs://a b`). |
| Error de enumeración | GCS no devuelve el listado de objetos del URI: el bucket no existe o la identidad no tiene `storage.objects.list` sobre él. |
| Flag de límite | `--max-objects` o `--max-bytes` (BR-3). |
| Valor de límite inválido | Valor de un flag de límite que no es un entero positivo (`0`, `-5`, `abc`). |
| Prefijo | Todo lo que sigue a `gs://bucket/`, comparado literalmente contra el nombre del objeto. No se le agrega `/`. Si falta, vale `""`. |
| Objeto inspeccionado | Objeto enumerado bajo el prefijo que cuenta para los límites de BR-3, se lea o se saltee. |
| Línea | Secuencia de caracteres terminada en `\n`, en `\r\n` o en el fin del objeto. El terminador no forma parte de la línea. La última línea sin terminador cuenta como línea. Se numeran desde `1` en cada objeto. |
| Match | Línea que contiene el patrón como subcadena literal. El patrón vacío es subcadena de toda línea, así que matchea todas, como en `grep`. |
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

**Dado** un URI `gs://bucket/prefijo`, **cuando** termina la ejecución,
**entonces** solo se inspeccionan los objetos cuyo nombre comienza literalmente
con `prefijo`, sin modificar el bucket.

> **VC-2** — Contra el bucket de prueba del emulador, con objetos `logs/a.log`,
> `logs/b.log`, `logs/c.log` y `logs-other/d.log` que contienen el patrón:
> `gcsgrep P gs://B/logs/` imprime matches solo de los tres primeros, y
> `gcsgrep P gs://B/logs` imprime matches de los cuatro.

### FR-3 — Detectar matches en streaming

**Dado** un objeto de texto UTF-8 que GCS entrega en varios trozos, **cuando** se
lo inspecciona, **entonces** `stdout` recibe exactamente una línea por cada línea
del objeto que es un match, aunque esa línea cruce el borde entre dos trozos.

> **VC-3** — Un objeto entregado por un stream en trozos de 64 KiB, con 2 matches
> en líneas que cruzan el borde entre trozos, produce exactamente 2 líneas en
> `stdout`.
>
> **VC-17** — Un objeto con contenido `a\nb timeout` (la última línea sin `\n`)
> produce con `-n` la salida `gs://B/obj:2:b timeout`.
>
> **VC-29** — Con el objeto `gs://B/edge/nonl.log` de contenido `a\nb timeout`
> (sin `\n` final) y el patrón vacío, `gcsgrep -n "" gs://B/edge/` imprime
> exactamente, en este orden, `gs://B/edge/nonl.log:1:a` y
> `gs://B/edge/nonl.log:2:b timeout`, y termina con `0`.
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

**Dado** un conjunto de objetos donde uno es un objeto fallido, **cuando** termina
la ejecución, **entonces** `stderr` recibe
`gcsgrep: no se pudo leer <URI del objeto>: <detalle>`, se leen los objetos
restantes y el exit code es `2`, aunque haya habido matches.

La falla se ubica en una línea: la primera línea con una secuencia UTF-8
inválida, o la línea que se estaba recibiendo cuando se agotaron los reintentos
(NFR-2). Los matches de las líneas anteriores a esa línea se imprimen y quedan en
`stdout`. De esa línea en adelante, el objeto no produce ninguna línea en
`stdout`. El exit code `2` indica que la salida de ese objeto es parcial.

> **VC-6** — Con `broken/latin1.log` (UTF-8 inválido) seguido de `broken/ok.log`
> (contiene `timeout`), `gcsgrep timeout gs://B/broken/` deja en `stdout`
> exactamente el match de `ok.log`, en `stderr` una línea que empieza con
> `gcsgrep: no se pudo leer gs://B/broken/latin1.log:`, y termina con exit `2`.
> Con `partial/mixed.log` de contenido `timeout 1\ncaf\xe9 timeout 2\ntimeout 3\n`
> (la segunda línea tiene el byte inválido `0xE9`), `gcsgrep -n timeout
> gs://B/partial/` imprime exactamente `gs://B/partial/mixed.log:1:timeout 1`,
> `stderr` empieza con `gcsgrep: no se pudo leer gs://B/partial/mixed.log:` y
> el exit code es `2`.

### FR-7 — Informar ausencia de matches

**Dado** objetos legibles que no contienen el patrón, sin alcanzar un límite,
**cuando** termina la ejecución, **entonces** `stdout` queda vacío y el exit code
es `1`.

> **VC-7** — `gcsgrep no-such-text gs://B/app/` (objetos legibles sin el patrón)
> deja `stdout` vacío y devuelve `1`. Si la ejecución alcanza un límite sin haber
> tenido matches, el exit code es `2` (BR-3, VC-11), no `1`.

### FR-8 — Informar progreso

**Dado** una ejecución, **cuando** el número de objetos inspeccionados llega a un
múltiplo de 100, **entonces** `stderr` recibe la línea
`gcsgrep: objetos inspeccionados: <N>`.

> **VC-8** — Con 100 objetos bajo el prefijo, `stderr` contiene exactamente una
> línea `gcsgrep: objetos inspeccionados: 100` y `stdout` no contiene ninguna línea
> que empiece con `gcsgrep:`. Con 99 objetos, `stderr` no contiene esa línea.

### FR-9 — Formato de salida con `-n`

**Dado** un match, **cuando** se usa `-n`, **entonces** `stdout` recibe la línea
`<URI del objeto>:<número de línea>:<texto de la línea>`.

> **VC-19** — Para un match en la línea 4 de `gs://B/app/server.log`,
> `gcsgrep -n timeout gs://B/app/` imprime exactamente
> `gs://B/app/server.log:4:connection timeout after 30s`.

### FR-10 — Exit code con matches

**Dado** una ejecución que termina sin objetos fallidos y sin alcanzar un límite,
**cuando** hubo al menos un match, **entonces** el exit code es `0`.

> **VC-20** — `gcsgrep timeout gs://B/app/` sobre objetos legibles con al menos un
> match devuelve `0` y `stderr` no contiene líneas de error.

### FR-11 — Rechazar un URI inválido

**Dado** un URI inválido, **cuando** se ejecuta el comando, **entonces**
`stderr` recibe `gcsgrep: <motivo>`, `stdout` queda vacío y el exit code es `2`,
sin cargar credenciales ni contactar a GCS.

> **VC-21** — Sin credenciales (`GOOGLE_APPLICATION_CREDENTIALS` apuntando a un
> archivo inexistente) y sin emulador, `gcsgrep x logs/app`, `gcsgrep x gs://`,
> `gcsgrep x gs:///x` y `gcsgrep x "gs://a b"` terminan con `2`, `stdout` vacío,
> `stderr` empieza con `gcsgrep: ` y no contiene `credenciales`: el URI se
> rechaza antes de cargar credenciales.

### FR-12 — Fallo al enumerar

**Dado** un URI que produce un error de enumeración, **cuando** se ejecuta el
comando, **entonces** `stderr` recibe
`gcsgrep: no se pudo enumerar gs://<bucket>/<prefijo>: <detalle>` y el exit code
es `2`.

> **VC-22** — Contra el emulador, `gcsgrep x gs://bucket-inexistente/` termina con
> `2`, `stdout` vacío y `stderr` empieza con `gcsgrep: no se pudo enumerar`.

### FR-13 — Ajustar el límite de objetos

**Dado** un entero positivo `N`, **cuando** se usa `--max-objects N`,
**entonces** el límite de objetos inspeccionados de BR-3 pasa a ser `N` en lugar
de `1000`.

> **VC-23** — Con 3 objetos bajo el prefijo, `--max-objects 2` termina con `2` y
> `stderr` contiene `gcsgrep: límite de seguridad alcanzado: máximo 2 objetos`;
> `--max-objects 3` termina con `0` y sin ese mensaje.

### FR-14 — Ajustar el límite de bytes

**Dado** un entero positivo `N` (en bytes), **cuando** se usa `--max-bytes N`,
**entonces** el límite de bytes declarados de BR-3 pasa a ser `N` en lugar de
`1073741824` (1 GiB).

> **VC-24** — Con objetos que declaran 10 y 20 bytes y contienen el patrón,
> `--max-bytes 29` imprime solo el match del primero, `stderr` contiene
> `gcsgrep: límite de seguridad alcanzado: máximo 29 bytes` y termina con `2`;
> `--max-bytes 30` imprime los dos matches y termina con `0`.

### FR-15 — Rechazar un valor de límite inválido

**Dado** un flag de límite con un valor de límite inválido, **cuando** se
ejecuta el comando, **entonces** `stdout` queda vacío, `stderr` contiene
`debe ser un entero positivo` y el exit code es `2`, sin contactar a GCS.

> **VC-25** — `gcsgrep --max-objects 0 x gs://B` y `gcsgrep --max-bytes abc x gs://B`
> terminan con `2`, `stdout` vacío y `stderr` contiene `debe ser un entero positivo`.

### FR-16 — Orden de la salida

**Dado** una ejecución con matches en varios objetos, **cuando** se imprimen los
resultados, **entonces** los objetos aparecen en el orden en que GCS los enumera
(lexicográfico por nombre) y, dentro de cada objeto, las líneas aparecen en orden
creciente.

> **VC-26** — Con matches en `app/b.log` (líneas 1 y 3) y `app/a.log` (línea 2),
> la salida con `-n` es, en este orden: `a.log:2`, `b.log:1`, `b.log:3`. Dos
> ejecuciones sobre el mismo bucket producen la misma salida byte a byte.

### FR-17 — URI sin objetos

**Dado** un URI válido cuyo listado no devuelve ningún objeto, **cuando** termina
la ejecución, **entonces** `stdout` y `stderr` quedan vacíos y el exit code es
`1`.

> **VC-30** — `gcsgrep timeout gs://B/prefijo-sin-objetos/` deja `stdout` y
> `stderr` vacíos y devuelve `1`.

### FR-18 — Sin copia local

**Dado** un objeto bajo el URI, **cuando** se lo inspecciona, **entonces** no se
crea ni se escribe ningún archivo en el sistema de archivos local.

> **VC-31** — Con toda apertura de archivos locales y toda creación de archivos
> temporales bloqueadas (cualquier intento hace fallar la ejecución), el objeto
> de VC-3 se inspecciona completo y produce sus 2 líneas en `stdout`.

## Reglas de negocio

### BR-1 — Solo lectura

La herramienta nunca crea, modifica, copia, mueve, borra ni cambia permisos de
objetos o buckets. Solo usa operaciones de listado y lectura.

*Fundamento:* el objetivo es buscar contenido, no convertir el CLI en un gestor
de GCS.

*Excepciones:* ninguna. La preparación y limpieza del bucket de prueba la hacen
los tests, no `gcsgrep`.

> **VC-9** — Tras todas las ejecuciones de la suite de integración, los
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

> **VC-11** — Con 1.001 objetos sin el patrón bajo el prefijo y valores por
> defecto, la ejecución termina con `2` (no `1`, aunque no haya matches) y el
> mensaje de límite de objetos. Con exactamente
> 1.000 objetos no aparece el mensaje de límite.
>
> **VC-27** — Si un objeto que declara más de 1 GiB sigue a otro con match, el
> match del primero queda en `stdout`, el objeto grande no se lee, `stderr`
> contiene el mensaje de límite de bytes y el exit code es `2`.

### BR-4 — Objetos no textuales

Se saltean sin error los objetos cuyo nombre termina en `.gz` (sin distinguir
mayúsculas) y los objetos cuyos primeros 8.192 bytes contienen un byte NUL
(`0x00`). Un objeto que no se saltea y contiene UTF-8 inválido es un objeto
fallido (FR-6). Saltar un objeto no produce salida y no cancela la ejecución.

*Fundamento:* evita imprimir basura binaria y mantiene el alcance de la v1
acotado a texto sin compresión. `Content-Type` no se usa porque sus metadatos
pueden ser incorrectos.

*Excepciones:* un byte NUL después de los primeros 8.192 bytes no hace saltear el
objeto. Si ese objeto es UTF-8 válido, se lee como texto. Trade-off aceptado:
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
> leerla, `stderr` contiene una línea que empieza con
> `gcsgrep: no se pudo leer gs://B/<nombre del objeto>:`, el objeto siguiente
> produce su match en `stdout` y el exit code es `2`.

## Requerimientos no funcionales

### NFR-1 — Memoria

**Condición de carga:** un único objeto de 128 MiB compuesto por líneas de hasta
1 KiB. **Métrica:** RSS pico del proceso (`Maximum resident set size` de
`/usr/bin/time -v`) menos el RSS pico de una ejecución igual sobre un objeto de
0 bytes. **Umbral:** menor a 64 MiB.

*Excepción:* una sola línea más larga que el umbral se retiene completa en
memoria, porque la unidad de match es la línea.

> **VC-14** — Bajo la condición de carga de NFR-1, contra el emulador, la
> diferencia de RSS pico medida con `/usr/bin/time -v` es menor a 64 MiB.

### NFR-2 — Reintentos de red

Un error transitorio de lectura (timeout, conexión cortada, HTTP 429 o 5xx) se
reintenta hasta 3 veces, es decir, hasta 4 intentos por tramo. Antes del segundo,
tercer y cuarto intento se espera 1 s, 2 s y 4 s respectivamente (backoff
exponencial sin aleatoriedad). El reintento vuelve a pedir el tramo en curso desde
el mismo offset, así que no se reimprimen líneas ya emitidas. Al agotar los
reintentos, el objeto es un objeto fallido, se aplica FR-6 y el exit code final es
`2`.

> **VC-15** — Con un objeto de 3 matches, cada uno en un tramo distinto, un
> stream de prueba que falla con un timeout al pedir el tramo del segundo match,
> y un reloj de prueba que registra cada espera:
> (a) si falla dos veces y luego responde, `stdout` tiene exactamente 3 líneas,
> sin repetidas, las esperas registradas son `[1 s, 2 s]`, `stderr` no tiene
> error para ese objeto y el exit code es `0`; (b) si falla cuatro veces, las
> esperas son `[1 s, 2 s, 4 s]`, `stdout` tiene solo el primer match de ese
> objeto, `stderr` recibe una línea que empieza con
> `gcsgrep: no se pudo leer <URI del objeto>:`, el objeto siguiente produce su
> match y el exit code es `2`.

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
reemplaza: descargar el objeto completo a un archivo local y luego correr
`grep -F patrón` sobre ese archivo. **Umbral:** a lo sumo 1,5 veces el tiempo de
la alternativa.

> **VC-28** — Bajo la condición de carga de NFR-4, se mide el tiempo de pared con
> `hyperfine --runs 5`. La alternativa corre como un único comando de shell: un
> script que descarga el objeto con el cliente oficial de GCS
> (`blob.download_to_filename`), seguido de `grep -F`. La mediana de `gcsgrep` no
> supera 1,5 veces la mediana de la alternativa.

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
| FR-3 | VC-3, VC-17, VC-18, VC-29 |
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
| FR-17 | VC-30 |
| FR-18 | VC-31 |
| BR-1 | VC-9 |
| BR-2 | VC-10 |
| BR-3 | VC-11, VC-27 |
| BR-4 | VC-12 |
| BR-5 | VC-13 |
| NFR-1 | VC-14 |
| NFR-2 | VC-15 |
| NFR-3 | VC-16 |
| NFR-4 | VC-28 |

**27 requerimientos, 31 VCs, 0 huérfanos.**

## Preguntas abiertas

Ninguna. Las funcionalidades diferidas están en `gcsgrep-plan.md`.
