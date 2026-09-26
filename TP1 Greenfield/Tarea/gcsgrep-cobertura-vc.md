# gcsgrep — tabla de cobertura de VCs

> Esta tabla se actualiza con la evidencia de cada verificación. Hay dos niveles
> de evidencia: tests unitarios con un cliente falso (sin infraestructura) y
> tests de integración que ejecutan el CLI real contra la API de GCS servida por
> el emulador [Floci](https://floci.io/gcp/). Ninguno de los dos requiere
> credenciales reales ni genera costos.
>
> Corresponde a la spec v1.3 (corrección posterior a la revisión externa
> `correccion-de-specs v1.1`). Los IDs de VC siguen esa versión: la parte de URI
> inválido del antiguo VC-1 pasó a VC-21, el bucket inexistente a VC-22, el
> formato con `-n` del antiguo VC-4 a VC-19, el prefijo sin objetos del antiguo
> VC-7 a VC-30 y la ausencia de archivos locales del antiguo VC-3 a VC-31.

## Resumen

| | |
|---:|---:|
| Requerimientos en la spec | 27 (18 FR, 5 BR, 4 NFR) |
| VCs definidos | 31 |
| VCs con cobertura ejecutable | 27 (VC-1 a VC-12, VC-16 a VC-27, VC-29 a VC-31) |
| VCs pasando | 27 |
| VCs diferidos a Iteración 2 | 4 (VC-13, VC-14, VC-15, VC-28) |
| Requerimientos sin VC | 0 |

## Entorno de verificación

| Elemento | Valor |
|---|---|
| Fecha | 2026-09-26 |
| SO | Windows 11 Pro 10.0.26200 |
| Python | 3.11.9 |
| `google-cloud-storage` | 3.14.1 |
| Emulador | `floci/floci-gcp:latest` (floci-gcp 0.9.0), Docker 29.2.1 |
| Endpoint | `STORAGE_EMULATOR_HOST=http://localhost:4588`, `GOOGLE_CLOUD_PROJECT=floci-local` |
| Cambios en el código para usar el emulador | **Ninguno.** El cliente oficial detecta `STORAGE_EMULATOR_HOST` y usa credenciales anónimas (excepción de BR-2); `gcsgrep` no sabe que hay un emulador. |

Los tests de integración viven en `tests/integration/test_emulator.py`. Crean un
bucket efímero `gcsgrep-it-<uuid>` con 119 objetos, ejecutan `python -m gcsgrep`
como subproceso y borran el bucket al terminar. Se saltean automáticamente si
`STORAGE_EMULATOR_HOST` no está definido.

| Prefijo sembrado | Contenido | Usado por |
|---|---|---|
| `app/` | Texto con y sin match, `.gz`, binario con NUL | VC-4, VC-5, VC-7, VC-11, VC-12, VC-19, VC-20 |
| `prefijo-sin-objetos/` | Nada (el listado vuelve vacío) | VC-30 |
| `other/` | Un objeto fuera de `app/` | VC-1 |
| `broken/` | UTF-8 inválido seguido de un objeto legible | VC-6 |
| `partial/` | Línea con UTF-8 inválido entre dos líneas con match | VC-6 |
| `many/` | 100 objetos | VC-8 |
| `logs/`, `logs-other/` | 3 + 1 objetos con el mismo patrón | VC-2, VC-23 |
| `edge/` | Última línea sin `\n` | VC-17, VC-29 |
| `empty/` | Objeto de 0 bytes | VC-18 |
| `order/` | `b.log` subido antes que `a.log` | VC-26 |
| `bytes/` | Objetos de 10 y 20 bytes | VC-24 |

## Cobertura

| VC | Requerimiento | Ejercitado por | Se observa | Estado |
|---|---|---|---|---|
| VC-1 | FR-1 bucket completo | `test_gcsgrep.py::test_vc1_*`; `test_emulator.py::test_vc1_*` | `gs://B` imprime matches de `app/` y de `other/`; `gs://B/` produce el mismo `stdout` | ✅ |
| VC-2 | FR-2 prefijo literal | `test_gcsgrep.py::test_vc2_*`; `test_emulator.py::test_vc2_*` | `gs://B/logs/` → exactamente `logs/a.log`, `b.log`, `c.log`; `gs://B/logs` → los cuatro, incluido `logs-other/d.log` | ✅ |
| VC-3 | FR-3 streaming | `test_gcsgrep.py::test_vc3_*` | Dos matches en líneas que cruzan el borde de la muestra (8 KiB) y del primer chunk (64 KiB) → exactamente 2 líneas; todas las lecturas son ≤ 64 KiB | ✅ |
| VC-4 | FR-4 formato sin `-n` | `test_gcsgrep.py::test_vc4_*`; `test_emulator.py::test_vc4_*` | `gs://B/app/server.log:connection timeout after 30s` literal | ✅ |
| VC-5 | FR-5 `-i` | `test_gcsgrep.py::test_vc5_*`; `test_emulator.py::test_vc5_*` | Con `-i` aparecen `TIMEOUT`, `Timeout` y `timeout`; sin `-i` solo la última | ✅ |
| VC-6 | FR-6 objeto fallido | `test_gcsgrep.py::test_vc6_*`; `test_emulator.py::test_vc6_*` | `stderr` empieza con `gcsgrep: no se pudo leer gs://B/broken/latin1.log:`; `stdout` es exactamente el match de `broken/ok.log`; exit `2`. `partial/mixed.log` → `stdout` exactamente `mixed.log:1:timeout 1` (no aparecen las líneas 2 ni 3), exit `2`. También con error de permiso al abrir | ✅ |
| VC-7 | FR-7 sin matches | `test_gcsgrep.py::test_vc7_*`; `test_emulator.py::test_vc7_*` | Objetos legibles sin el patrón: exit `1`, `stdout` vacío. Límite alcanzado sin matches → exit `2` (ver VC-11) | ✅ |
| VC-8 | FR-8 progreso | `test_gcsgrep.py::test_vc8_*`; `test_emulator.py::test_vc8_*` | Con 100 objetos, `stderr` es exactamente `gcsgrep: objetos inspeccionados: 100` y ninguna línea de `stdout` empieza con `gcsgrep:`; con 99 objetos no hay línea de progreso | ✅ |
| VC-9 | BR-1 solo lectura | `test_emulator.py::test_vc9_*` | Snapshot (nombre, tamaño, `md5_hash`, `generation`) de los 119 objetos idéntico antes y después de cuatro escaneos, incluidos uno con error y dos cortados por límite | ✅ |
| VC-10 | BR-2 permisos | `test_emulator.py::test_vc10_*` | Sin emulador y con ADC apuntando a un archivo inexistente → exit `2`, `stderr` empieza con `gcsgrep: no se pudieron cargar las credenciales`, `stdout` vacío | ✅ parcial (ver nota) |
| VC-11 | BR-3 límite de objetos | `test_gcsgrep.py::test_vc11_*`; `test_emulator.py::test_vc11_*` | 1.001 objetos sin el patrón con valores por defecto → `máximo 1000 objetos`, exit `2`, el objeto 1.001 no se abre; exactamente 1.000 → sin mensaje de límite; los objetos `.gz` salteados cuentan para el límite | ✅ |
| VC-12 | BR-4 binarios y `.gz` | `test_gcsgrep.py::test_vc12_*`; `test_emulator.py::test_vc12_*` | `.gz` (también `.GZ`) y binario con NUL no aparecen en `stdout` ni en `stderr`; el texto siguiente sí; un NUL después de los primeros 8.192 bytes no hace saltear el objeto | ✅ |
| VC-13 | BR-5 generación | Integración con objeto reemplazado durante el escaneo | — | Iteración 2 |
| VC-14 | NFR-1 memoria | Benchmark con objeto de 128 MiB y `/usr/bin/time -v` | — | Iteración 2 |
| VC-15 | NFR-2 reintentos | Test de stream transitorio (2 y 4 fallos) con reloj de prueba que registra las esperas | — | Iteración 2 |
| VC-16 | NFR-3 scripting | `test_gcsgrep.py::test_vc16_*`; `assert_no_traceback` en todos los casos de error de `test_emulator.py` | En URI inválido, error de listado, objeto ilegible, sin credenciales, límites y valor de límite inválido: `stdout` solo con matches, `stderr` no vacío con prefijo `gcsgrep: `, sin `Traceback` | ✅ |
| VC-17 | FR-3 última línea sin `\n` | `test_gcsgrep.py::test_vc17_*`; `test_emulator.py::test_vc17_*` | `a\nb timeout` → `gs://B/edge/nonl.log:2:b timeout`; con `\r\n` el terminador no aparece en la salida | ✅ |
| VC-18 | FR-3 objeto de 0 bytes | `test_gcsgrep.py::test_vc18_*`; `test_emulator.py::test_vc18_*` | `stdout` y `stderr` vacíos, exit `1`; el objeto se abre (cuenta como inspeccionado) | ✅ |
| VC-19 | FR-9 formato con `-n` | `test_gcsgrep.py::test_vc19_*`; `test_emulator.py::test_vc19_*` | `gs://B/app/server.log:4:connection timeout after 30s` literal | ✅ |
| VC-20 | FR-10 exit `0` | `test_gcsgrep.py::test_vc20_*`; `test_emulator.py::test_vc20_*` | Match sin errores → exit `0` y `stderr` vacío | ✅ |
| VC-21 | FR-11 URI inválido | `test_gcsgrep.py::test_vc21_*`; `test_emulator.py::test_vc21_*` | `B/app/`, `gs://`, `gs:///app`, `gs://a b`, sin credenciales ni emulador → exit `2`, `stdout` vacío, `stderr` empieza con `gcsgrep: ` y no menciona credenciales; en unitarios, además, la fábrica de clientes no se invoca | ✅ |
| VC-22 | FR-12 fallo al enumerar | `test_gcsgrep.py::test_vc22_*`; `test_emulator.py::test_vc22_*` | Bucket inexistente → exit `2`, `stdout` vacío, `stderr` empieza con `gcsgrep: no se pudo enumerar` | ✅ |
| VC-23 | FR-13 `--max-objects` | `test_gcsgrep.py::test_vc23_*`; `test_emulator.py::test_vc23_*` | 3 objetos: `--max-objects 2` → exit `2` y `máximo 2 objetos`; `--max-objects 3` → exit `0` sin mensaje de límite | ✅ |
| VC-24 | FR-14 `--max-bytes` | `test_gcsgrep.py::test_vc24_*`; `test_emulator.py::test_vc24_*` | 10 + 20 bytes: `--max-bytes 29` → match del primero en `stdout`, `máximo 29 bytes`, exit `2`, el segundo no se abre; `--max-bytes 30` → exit `0` con 2 matches | ✅ |
| VC-25 | FR-15 valor de límite inválido | `test_gcsgrep.py::test_vc25_*`; `test_emulator.py::test_vc25_*` | `--max-objects 0`, `--max-objects -5`, `--max-bytes abc` → exit `2`, `stdout` vacío, `debe ser un entero positivo`; no se contacta a GCS | ✅ |
| VC-26 | FR-16 orden | `test_gcsgrep.py::test_vc26_*`; `test_emulator.py::test_vc26_*` | Con `b.log` subido antes que `a.log`: salida `a.log:2`, `b.log:1`, `b.log:3`; dos corridas idénticas byte a byte | ✅ |
| VC-27 | BR-3 límite de bytes por defecto | `test_gcsgrep.py::test_vc27_*` | Objeto que declara 1 GiB + 1 tras uno con match: el match queda en `stdout`, `máximo 1073741824 bytes`, exit `2`, el objeto grande no se abre | ✅ |
| VC-29 | FR-3 patrón vacío | `test_gcsgrep.py::test_vc29_*`; `test_emulator.py::test_vc29_*` | `-n ""` sobre `edge/nonl.log` (`a\nb timeout`) → `nonl.log:1:a` y `nonl.log:2:b timeout`, exit `0` | ✅ |
| VC-30 | FR-17 URI sin objetos | `test_gcsgrep.py::test_vc30_*`; `test_emulator.py::test_vc30_*` | `prefijo-sin-objetos/` → `stdout` y `stderr` vacíos, exit `1` | ✅ |
| VC-31 | FR-18 sin copia local | `test_gcsgrep.py::test_vc3_matches_crossing_chunk_boundaries_without_local_files` | Con `open` y las funciones de `tempfile` reemplazadas por una que hace fallar el test, el objeto de VC-3 se inspecciona completo y produce sus 2 líneas | ✅ |
| VC-28 | NFR-4 rendimiento | `hyperfine --runs 5`: `gcsgrep` contra descarga + `grep -F` | — | Iteración 2 |

**Nota sobre VC-10:** el emulador no aplica IAM, así que la segunda mitad de
VC-10 (identidad sin `storage.objects.get`) no es reproducible localmente y
queda para la corrida contra GCP real (`GCSGREP_INTEGRATION=1`) de la Iteración 2.
Por código, un 403 al abrir un objeto sigue la misma ruta que el error de permiso
verificado en `test_vc6_permission_error_on_open_is_a_failed_object`, y un 403 al
listar sigue la misma ruta que el 404 de VC-22.

**Nota sobre VC-11 y VC-27:** los casos de 1.000/1.001 objetos y de un objeto de
más de 1 GiB se verifican con el cliente falso, porque sembrarlos en el emulador
no agrega evidencia sobre la regla y encarece la suite. El corte por límite
contra la API real se verifica con límites chicos en VC-11, VC-23 y VC-24.

## Comandos de verificación

Sin infraestructura (tests unitarios; los de integración se saltean):

```bash
pytest -q
# 41 passed, 31 skipped
```

Con el emulador Floci:

```bash
docker compose up -d --wait
export STORAGE_EMULATOR_HOST=http://localhost:4588
export GOOGLE_CLOUD_PROJECT=floci-local
pytest -q
# 72 passed in 19.52s (Windows)
```

## Corrida manual documentada

Bucket `gs://logs` sembrado en el emulador con `app/server.log`,
`app/errors.log`, `app/clean.log`, `app/archive.gz`, `app/blob.bin`,
`broken/latin1.log` y `broken/ok.log`. Salida literal observada:

```text
$ gcsgrep timeout gs://logs/app/
gs://logs/app/server.log:connection timeout after 30s
[exit 0]

$ gcsgrep -n timeout gs://logs/app/
gs://logs/app/server.log:4:connection timeout after 30s
[exit 0]

$ gcsgrep -i -n timeout gs://logs/app/
gs://logs/app/errors.log:1:TIMEOUT
gs://logs/app/server.log:2:Request Timeout
gs://logs/app/server.log:4:connection timeout after 30s
[exit 0]

$ gcsgrep nomatch gs://logs/app/
[exit 1]

$ gcsgrep -n timeout gs://logs/broken/
gcsgrep: no se pudo leer gs://logs/broken/latin1.log: 'utf-8' codec can't decode byte 0xe9 in position 3: invalid continuation byte
gs://logs/broken/ok.log:1:timeout here
[exit 2]

$ gcsgrep --max-objects 2 timeout gs://logs/app/
gcsgrep: límite de seguridad alcanzado: máximo 2 objetos
[exit 2]

$ gcsgrep timeout logs/app/
gcsgrep: la ubicación debe comenzar con gs://
[exit 2]

$ gcsgrep timeout gs://no-such-bucket/
gcsgrep: no se pudo enumerar gs://no-such-bucket/: 404 GET http://localhost:4588/storage/v1/b/no-such-bucket/o?projection=noAcl&prefix=&prettyPrint=false: Bucket not found: no-such-bucket
[exit 2]

$ env -u STORAGE_EMULATOR_HOST GOOGLE_APPLICATION_CREDENTIALS=/nope.json gcsgrep timeout gs://logs/app/
gcsgrep: no se pudieron cargar las credenciales de GCP: File C:/Program Files/Git/nope.json was not found.
[exit 2]
```

## Decisión: verificación con emulador de GCS

La Iteración 1 se verifica contra el emulador Floci porque expone la misma API
JSON de GCS y se usa a través del mismo SDK oficial; `gcsgrep` no contiene
código específico de emulador y la suite de integración es idéntica para
cualquier endpoint de GCS. Esto hace la verificación reproducible por cualquier
integrante del equipo, sin cuenta de GCP ni costos.

Con ADC configurado, la misma suite corre contra un proyecto real con
`GCSGREP_INTEGRATION=1 pytest -q tests/integration`.
