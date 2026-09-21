# gcsgrep — tabla de cobertura de VCs

> Esta tabla se actualiza con la evidencia de cada verificación. Hay dos niveles
> de evidencia: tests unitarios con un cliente falso (sin infraestructura) y
> tests de integración que ejecutan el CLI real contra la API de GCS servida por
> el emulador [Floci](https://floci.io/gcp/). Ninguno de los dos requiere
> credenciales reales ni genera costos.

## Resumen

| | |
|---:|---:|
| Requerimientos en la spec | 16 |
| VCs definidos | 16 |
| VCs con cobertura ejecutable | 13 (VC-1 a VC-12 y VC-16) |
| VCs pasando | 13 |
| VCs diferidos a Iteración 2 | 3 (VC-13, VC-14, VC-15) |
| Requerimientos sin VC | 0 |

## Entorno de verificación

| Elemento | Valor |
|---|---|
| Fecha | 2026-09-21 |
| SO | Windows 11 Pro 10.0.26200 |
| Python | 3.11.9 |
| `google-cloud-storage` | 3.14.1 |
| Emulador | `floci/floci-gcp:latest` (floci-gcp 0.9.0), Docker 29.2.1 |
| Endpoint | `STORAGE_EMULATOR_HOST=http://localhost:4588`, `GOOGLE_CLOUD_PROJECT=floci-local` |
| Cambios en el código para usar el emulador | **Ninguno.** El cliente oficial detecta `STORAGE_EMULATOR_HOST` y usa credenciales anónimas; `gcsgrep` no sabe que hay un emulador. |

Los tests de integración viven en `tests/integration/test_emulator.py`. Crean un
bucket efímero `gcsgrep-it-<uuid>` con 108 objetos (texto con y sin match,
`.gz`, binario con NUL, UTF-8 inválido, un objeto fuera del prefijo y 100
objetos para el aviso de progreso), ejecutan `python -m gcsgrep` como
subproceso y borran el bucket al terminar. Se saltean automáticamente si
`STORAGE_EMULATOR_HOST` no está definido.

## Cobertura

| VC | Requerimiento | Ejercitado por | Se observa | Estado |
|---|---|---|---|---|
| VC-1 | FR-1 URI válida/inválida | `test_gcsgrep.py::test_parse_gs_uri*`; `test_emulator.py::test_vc1_*` | `logs/app/` → exit `2`, stderr `la ubicación debe comenzar con gs://`; bucket inexistente → exit `2`, `no se pudo enumerar`; stdout vacío en ambos | ✅ |
| VC-2 | FR-2 prefijo | `test_gcsgrep.py::test_scan_finds_literal_matches_and_line_numbers`; `test_emulator.py::test_vc2_*` | Con `gs://B/app/` solo aparece `app/server.log`; `other/notes.txt` (fuera del prefijo) no se visita; con `gs://B/` sí aparece | ✅ |
| VC-3 | FR-3 streaming | `test_gcsgrep.py::test_scan_finds_literal_matches_and_line_numbers`; `test_emulator.py::test_vc4_*` | El scanner consume un `BlobReader` del cliente oficial en chunks de 64 KiB; no se escribe ningún archivo local | ✅ |
| VC-4 | FR-4 objeto y línea | `test_gcsgrep.py::test_cli_formats_match_and_returns_zero`; `test_emulator.py::test_vc4_*` | `-n` → `gs://B/app/server.log:4:connection timeout after 30s`; sin `-n` → `gs://B/app/server.log:connection timeout after 30s` | ✅ |
| VC-5 | FR-5 `-i` | `test_gcsgrep.py::test_scan_ignore_case_and_skip_binary_and_gzip`; `test_emulator.py::test_vc5_*` | Con `-i` aparecen `TIMEOUT`, `Request Timeout` y `timeout`; sin `-i` solo la última | ✅ |
| VC-6 | FR-6 error parcial | `test_gcsgrep.py::test_scan_continues_after_object_error`; `test_emulator.py::test_vc6_*` | `broken/latin1.log` (UTF-8 inválido) → stderr `no se pudo leer ...`; `broken/ok.log` igual se procesa y su match va a stdout; exit `2` | ✅ |
| VC-7 | FR-7 sin matches | `test_gcsgrep.py::test_cli_exit_code_one_when_no_match`; `test_emulator.py::test_vc7_*` | Exit `1` y stdout vacío | ✅ |
| VC-8 | FR-8 progreso | `test_gcsgrep.py::test_scan_reports_progress_every_hundred_objects`; `test_emulator.py::test_vc8_*` | Con 100 objetos reales, stderr contiene `objetos procesados: 100` y stdout tiene exactamente 100 matches sin el aviso | ✅ |
| VC-9 | BR-1 solo lectura | `test_emulator.py::test_vc9_bucket_is_unchanged_after_scans` | Snapshot (nombre, tamaño, `md5_hash`, `generation`) de los 108 objetos idéntico antes y después de tres escaneos, incluyendo uno con error y uno cortado por límite | ✅ |
| VC-10 | BR-2 permisos | `test_emulator.py::test_vc10_without_credentials_fails_with_two` | Sin emulador y con ADC apuntando a un archivo inexistente → exit `2`, stderr `no se pudieron cargar las credenciales de GCP`, stdout vacío | ✅ (ver nota) |
| VC-11 | BR-3 límites | `test_gcsgrep.py::test_cli_returns_two_when_object_limit_is_reached`; `test_emulator.py::test_vc11_*` | `--max-objects 2` → `límite de seguridad alcanzado: máximo 2 objetos`, exit `2`; `--max-bytes 10` → `máximo 10 bytes`, exit `2` | ✅ |
| VC-12 | BR-4 binarios y `.gz` | `test_gcsgrep.py::test_scan_ignore_case_and_skip_binary_and_gzip`; `test_emulator.py::test_vc12_*` | `app/archive.gz` y `app/blob.bin` (contienen `timeout`) no aparecen en stdout ni producen bytes NUL; `app/server.log` sí se procesa | ✅ |
| VC-13 | BR-5 generación | Integración con objeto reemplazado durante el escaneo | — | Iteración 2 |
| VC-14 | NFR-1 memoria | Benchmark con objeto de 128 MiB | — | Iteración 2 |
| VC-15 | NFR-2 reintentos | Test de stream transitorio | — | Iteración 2 |
| VC-16 | NFR-3 scripting | `assert_no_traceback` en todos los casos de error de `test_emulator.py` | En URI inválida, bucket inexistente, objeto ilegible, sin credenciales y límites: matches solo en stdout, mensaje en stderr, sin `Traceback` | ✅ |

**Nota sobre VC-10:** el emulador no aplica IAM, así que el caso "credenciales
válidas pero sin permiso de lectura sobre el bucket" no es reproducible
localmente. Ese camino queda cubierto por el manejo genérico de errores de
enumeración (`no se pudo enumerar`, exit `2`) y se verifica contra GCP real
cuando haya un proyecto disponible.

## Comandos de verificación

Sin infraestructura (tests unitarios; los de integración se saltean):

```bash
pytest -q
# 10 passed, 15 skipped
```

Con el emulador Floci:

```bash
docker run -d --name floci-gcp -p 4588:4588 floci/floci-gcp:latest
export STORAGE_EMULATOR_HOST=http://localhost:4588
export GOOGLE_CLOUD_PROJECT=floci-local
pytest -q
# 25 passed in 12.63s
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

## Pendiente contra GCP real

La misma suite `tests/integration` corre sin cambios contra un proyecto real:
basta con no definir `STORAGE_EMULATOR_HOST`, tener ADC configurado
(`gcloud auth application-default login`) y forzar la ejecución con
`GCSGREP_INTEGRATION=1`. Queda pendiente ejecutarla una vez contra un bucket
real para completar la nota de VC-10 (permiso de lectura denegado por IAM).
