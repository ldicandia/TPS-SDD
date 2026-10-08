# Spec — flag `-c` / `--count` en `gcsgrep`

**Base:** `TPS-SDD` @ `b28ad1f38606bfdaf7e9059c92411c97eaf99e77` · **Fecha:** 2026-10-06

El proyecto que cambia es `gcsgrep`, en `TP1 Greenfield/Tarea/` del repo `TPS-SDD`.
Todas las rutas de esta spec (`src/…`, `tests/…`, `README.md`) son relativas a esa
carpeta, y los comandos de los VC se corren desde ahí.

Los VC de comportamiento usan el mismo arnés que la suite existente: `run(argv, blobs)`
de `tests/test_gcsgrep.py:71-77`, con `FakeBlob(nombre, contenido)` y el bucket `B`.
"Objeto `x` = `contenido`" quiere decir `FakeBlob("x", b"contenido")`.

## Propósito

Quien busca un patrón en un bucket puede saber cuántas líneas coinciden en cada objeto
sin recibir las líneas.

## Términos

| Término | Significa |
|---|---|
| línea coincidente | Línea de un objeto que contiene el patrón (sin distinguir mayúsculas si va `-i`), con la misma regla de `find_matches` (`src/gcsgrep/matcher.py:4-10`). Una línea que contiene el patrón tres veces es una sola línea coincidente. |
| conteo | Cantidad de líneas coincidentes de un objeto, contadas de la primera a la última línea. |
| modo conteo | Ejecución de `gcsgrep` con `-c` o `--count`. |
| objeto completo | Objeto cuya lectura terminó sin excepción. No es objeto completo uno que falló al abrirse o a mitad de lectura (`src/gcsgrep/gcs.py:165-170`). |

## Alcance

### Dentro

| Archivo / módulo | Qué cambia |
|---|---|
| `src/gcsgrep/cli.py` | `build_parser` agrega `-c`/`--count` (`store_true`, ayuda "muestra la cantidad de líneas que coinciden por objeto"). En modo conteo, `main` no imprime líneas y en su lugar imprime `gs://bucket/objeto:N` por cada objeto completo con conteo ≥ 1. |
| `src/gcsgrep/gcs.py` | `_scan_blob` devuelve el conteo (entero) en lugar de `bool`, y 0 cuando saltea el objeto (`.gz` o binario); `scan` acepta un callback opcional `on_count(uri, conteo)` que llama una vez por objeto completo con conteo ≥ 1, después de terminar ese objeto. `result.matched` pasa a `True` cuando el conteo es ≥ 1. |
| `tests/test_gcsgrep.py` | Un test por cada VC-FR y VC-NFR de esta spec, con el arnés `run`/`FakeBlob` existente, nombrados `test_count_fr<N>_…` / `test_count_nfr1_…` para que no los seleccionen los filtros `-k "vcN"` de los invariantes. |
| `README.md` | La línea de uso pasa a `gcsgrep [-i] [-n] [-c] …` y se documenta el formato `gs://bucket/objeto:N`. |

### Fuera

| Qué queda afuera | Por qué |
|---|---|
| Contar ocurrencias en lugar de líneas | El pedido es "cuántas líneas coinciden"; además el matcher solo decide por línea (`src/gcsgrep/matcher.py:9`). |
| Imprimir objetos con conteo 0 (`gs://B/x:0`) | Ver D-2: rompería "sin coincidencias → stdout vacío" y con el límite por defecto podrían ser 1.000 líneas de ceros. |
| Una línea de total sumando los objetos | No se pidió; se obtiene con `awk -F: '{s+=$NF} END {print s}'` sobre la salida. |
| Otros flags de grep (`-l`, `-o`, `-v`, `-m`) | Cada uno cambia otra semántica de salida; no forman parte de este cambio. |
| Tests específicos de progreso y `--max-bytes` en modo conteo | Esas rutas viven en `scan` antes y después de cada objeto (`src/gcsgrep/gcs.py:145-148`, `src/gcsgrep/gcs.py:172-174`) y no dependen de cómo se emite la salida; el cambio no las toca y FR-6 ya ejercita el corte por límite en modo conteo. |
| `src/gcsgrep/matcher.py` | El conteo reutiliza `find_matches` tal cual (D-5); no hace falta tocarlo. |
| Tests de integración `tests/integration/test_emulator.py` | Requieren emulador o GCP real y se saltean sin ellos (`tests/integration/test_emulator.py:29-31`); los VC de esta spec son deterministas con el cliente falso. Los existentes no se modifican. |
| La spec original `gcsgrep-spec.md` del TP1 | Esta spec es el delta sobre la base; la original no se reescribe. |

## Invariantes

### INV-1 · La suite unitaria existente sigue verde

Los tests de `tests/test_gcsgrep.py` en la base pasan sin modificarlos.

- **VC-INV-1** · `python -m pytest -q tests/test_gcsgrep.py` → ningún `failed`, exit 0; los tests preexistentes no cambian de nombre ni de aserciones.

### INV-2 · Sin `-c`, la salida es idéntica a la de la base

Sin modo conteo se imprime `uri:texto` o `uri:N:texto` con `-n`, en orden de listado y de línea (`src/gcsgrep/cli.py:63-67`).

- **VC-INV-2** · `python -m pytest -q tests/test_gcsgrep.py -k "vc4 or vc19 or vc26 or vc5 or vc29"` → todos pasan, exit 0.

### INV-3 · Exit codes, errores, progreso y límites no cambian sin `-c`

0 con coincidencias, 1 sin coincidencias, 2 con error o límite (`src/gcsgrep/cli.py:87-96`); el aviso de progreso cada 100 objetos y los límites `--max-objects`/`--max-bytes` funcionan igual.

- **VC-INV-3** · `python -m pytest -q tests/test_gcsgrep.py -k "vc6 or vc7 or vc30 or vc8 or vc11 or vc12 or vc16 or vc20 or vc21 or vc22 or vc23 or vc24 or vc25 or vc27"` → todos pasan, exit 0.

## Requerimientos

### FR-1 · `-c` imprime el conteo de cada objeto en lugar de las líneas

- **Dado** el objeto `app/a.log` = `timeout timeout\nok\ntimeout\n` y el objeto `app/b.log` = `connection timeout\n`, listados en ese orden
- **Cuando** se ejecuta `gcsgrep -c timeout gs://B/app/`
- **Entonces** stdout tiene una línea `gs://B/app/<objeto>:<conteo>` por objeto, en orden de listado, sin ninguna línea del contenido; la primera línea de `a.log` cuenta una sola vez; exit 0
- **VC-FR-1** · `run(["-c", "timeout", "gs://B/app/"], [FakeBlob("app/a.log", b"timeout timeout\nok\ntimeout\n"), FakeBlob("app/b.log", b"connection timeout\n")])` → stdout `gs://B/app/a.log:2\ngs://B/app/b.log:1\n`, stderr vacío, exit 0

### FR-2 · `--count` es equivalente a `-c`

- **Dado** los mismos dos objetos de FR-1
- **Cuando** se ejecuta `gcsgrep --count timeout gs://B/app/`
- **Entonces** la salida, el stderr y el exit code son idénticos a los de `-c`
- **VC-FR-2** · `run(["--count", "timeout", "gs://B/app/"], [FakeBlob("app/a.log", b"timeout timeout\nok\ntimeout\n"), FakeBlob("app/b.log", b"connection timeout\n")])` → stdout `gs://B/app/a.log:2\ngs://B/app/b.log:1\n`, stderr vacío, exit 0; y `main(["--help"])` dentro de `pytest.raises(SystemExit)` (como `tests/test_gcsgrep.py:421-422`) → código 0 y `capsys.readouterr().out` contiene `-c, --count`

### FR-3 · Los objetos con conteo 0 no se imprimen

- **Dado** el objeto `app/a.log` = `healthy\n` y el objeto `app/b.log` = `timeout\n`
- **Cuando** se ejecuta `gcsgrep -c timeout gs://B/app/`, y aparte `gcsgrep -c timeout gs://B/ok/` con solo el objeto `ok/c.log` = `healthy\n`
- **Entonces** en el primer caso solo aparece `b.log` y el exit es 0; en el segundo stdout queda vacío y el exit es 1, como sin `-c`
- **VC-FR-3** · `run(["-c", "timeout", "gs://B/app/"], [FakeBlob("app/a.log", b"healthy\n"), FakeBlob("app/b.log", b"timeout\n")])` → stdout `gs://B/app/b.log:1\n`, exit 0; `run(["-c", "timeout", "gs://B/ok/"], [FakeBlob("ok/c.log", b"healthy\n")])` → stdout `""`, stderr `""`, exit 1

### FR-4 · `-c` respeta `-i` e ignora `-n`

- **Dado** el objeto `app.log` = `TIMEOUT\nTimeout\ntimeout\n`
- **Cuando** se ejecuta `gcsgrep -c -i timeout gs://B/`, `gcsgrep -c timeout gs://B/` y `gcsgrep -c -n -i timeout gs://B/`
- **Entonces** con `-i` cuenta las tres variantes, sin `-i` cuenta solo la exacta, y agregar `-n` no cambia la salida de modo conteo
- **VC-FR-4** · con `[FakeBlob("app.log", b"TIMEOUT\nTimeout\ntimeout\n")]`: `run(["-c", "-i", "timeout", "gs://B/"], …)` → `gs://B/app.log:3\n`, exit 0; `run(["-c", "timeout", "gs://B/"], …)` → `gs://B/app.log:1\n`, exit 0; `run(["-c", "-n", "-i", "timeout", "gs://B/"], …)` → `gs://B/app.log:3\n`, exit 0

### FR-5 · Un objeto que falla no imprime conteo y la búsqueda sigue

- **Dado** el objeto `partial/mixed.log` = `timeout 1\ncaf\xe9 timeout 2\ntimeout 3\n` (la segunda línea no es UTF-8) y el objeto `partial/ok.log` = `timeout\n`
- **Cuando** se ejecuta `gcsgrep -c timeout gs://B/partial/`
- **Entonces** `mixed.log` no aparece en stdout (no es objeto completo, aunque su primera línea coincida), el error va a stderr con el formato de la base, `ok.log` sí se imprime y el exit es 2
- **VC-FR-5** · `run(["-c", "timeout", "gs://B/partial/"], [FakeBlob("partial/mixed.log", b"timeout 1\ncaf\xe9 timeout 2\ntimeout 3\n"), FakeBlob("partial/ok.log", b"timeout\n")])` → stdout `gs://B/partial/ok.log:1\n`, stderr empieza con `gcsgrep: no se pudo leer gs://B/partial/mixed.log:`, exit 2

### FR-6 · Al alcanzar un límite se conservan los conteos ya impresos

- **Dado** los objetos `a.log` = `timeout\n` y `b.log` = `timeout\n`
- **Cuando** se ejecuta `gcsgrep -c --max-objects 1 timeout gs://B/`
- **Entonces** el conteo de `a.log` se imprime, `b.log` no se abre, stderr informa el límite y el exit es 2
- **VC-FR-6** · `run(["-c", "--max-objects", "1", "timeout", "gs://B/"], [FakeBlob("a.log", b"timeout\n"), FakeBlob("b.log", b"timeout\n")])` → stdout `gs://B/a.log:1\n`, stderr contiene `gcsgrep: límite de seguridad alcanzado: máximo 1 objetos`, `b.log` con `opened is False`, exit 2

### FR-7 · Los objetos salteados no imprimen conteo

- **Dado** el objeto `bin.dat` = `timeout\x00x`, el objeto `c.GZ` = `timeout` y el objeto `app.log` = `timeout\n`
- **Cuando** se ejecuta `gcsgrep -c timeout gs://B/`
- **Entonces** solo aparece `app.log`; los binarios y `.gz` se saltean como en la base (`src/gcsgrep/gcs.py:94-101`), sin stderr
- **VC-FR-7** · `run(["-c", "timeout", "gs://B/"], [FakeBlob("bin.dat", b"timeout\x00x"), FakeBlob("c.GZ", b"timeout"), FakeBlob("app.log", b"timeout\n")])` → stdout `gs://B/app.log:1\n`, stderr `""`, exit 0

### FR-8 · El conteo incluye la última línea sin terminador

- **Dado** el objeto `edge/nonl.log` = `a\nb timeout` (sin `\n` final)
- **Cuando** se ejecuta `gcsgrep -c "" gs://B/edge/` (patrón vacío: coincide con cada línea)
- **Entonces** el conteo es 2
- **VC-FR-8** · `run(["-c", "", "gs://B/edge/"], [FakeBlob("edge/nonl.log", b"a\nb timeout")])` → stdout `gs://B/edge/nonl.log:2\n`, exit 0

### NFR-1 · El modo conteo lee por streaming, igual que la base

- **Métrica** Tamaños solicitados al stream (`blob.stream.read_sizes`), cantidad de lecturas y archivos locales creados; se registran las lecturas y se parchean `open`/`tempfile` para fallar si se intenta crear un archivo.
- **Umbral** Cada lectura solicita como máximo 65.536 bytes (`CHUNK_SIZE`), se realizan al menos 3 lecturas y se crean 0 archivos locales.
- **Carga** Modo conteo sobre 1 objeto de más de 73.728 bytes (`SAMPLE_SIZE + CHUNK_SIZE`), con 3 líneas, 2 coincidentes y la segunda cruzando ese límite, como en el VC siguiente.

- **VC-NFR-1** · test análogo a `test_vc3_matches_crossing_chunk_boundaries_without_local_files` (`tests/test_gcsgrep.py:136-163`) con el mismo contenido de 3 líneas (2 coincidentes, la segunda cruzando `SAMPLE_SIZE + CHUNK_SIZE`), `open`/`tempfile` parcheados para fallar, ejecutando `run(["-c", "timeout", "gs://logs/"], [blob])` → stdout `gs://logs/big.log:2\n`, `len(blob.stream.read_sizes) > 2`, cada tamaño en `(0, 65536]`, exit 0

## Decisiones

| ID | Decisión | Alternativa descartada | Fundamento en el código base |
|---|---|---|---|
| D-1 | Formato `gs://bucket/objeto:N`, una línea por objeto | `N gs://…` o columnas separadas por tab | `src/gcsgrep/cli.py:65` la salida existente ya es `uri:` + dato con `:` como separador; un script que corta por `:` sigue funcionando |
| D-2 | No imprimir objetos con conteo 0 | Imprimir `uri:0` como `grep -c` con varios archivos | `src/gcsgrep/cli.py:96` y `tests/test_gcsgrep.py:291-295` fijan que sin coincidencias stdout queda vacío con exit 1; y `src/gcsgrep/cli.py:32` admite 1.000 objetos por defecto, que serían 1.000 líneas de ceros |
| D-3 | Con `-c`, `-n` se acepta y se ignora | Rechazar `-c -n` como flags incompatibles (exit 2 de argparse) | `src/gcsgrep/gcs.py:107` el número de línea solo existe por cada línea emitida; en modo conteo no hay línea a la cual ponérselo, y rechazarlo rompería alias tipo `gcsgrep -n` |
| D-4 | `scan` avisa el conteo con un callback `on_count` al terminar cada objeto completo | Contar en `cli.py` agrupando las llamadas a `on_match` por URI | `src/gcsgrep/gcs.py:165-170` el error de un objeto se detecta después de haber emitido sus líneas previas (`src/gcsgrep/gcs.py:68-69`); las líneas se emiten a medida que se leen (`src/gcsgrep/gcs.py:105-107`), así que desde `cli.py` no se distingue un objeto completo de uno que falló, y se imprimiría un conteo parcial |
| D-5 | El conteo reutiliza `find_matches` y cuenta lo que produce | Una función nueva con `str.count` | `src/gcsgrep/matcher.py:9` decide por línea con `needle in haystack`; reutilizarlo garantiza que `-c` cuente exactamente las líneas que sin `-c` se imprimen, incluida la regla de `-i` (`src/gcsgrep/matcher.py:6-8`) |
| D-6 | Un objeto que falla no imprime conteo | Imprimir el conteo parcial de las líneas leídas antes del error | `tests/test_gcsgrep.py:265-272` muestra que la base emite líneas previas al error; un conteo parcial en stdout sería indistinguible de uno completo, mientras que el error ya queda en stderr (`src/gcsgrep/cli.py:69-70`) y el exit 2 (`src/gcsgrep/cli.py:94-95`) |
| D-7 | El conteo de cada objeto se imprime apenas termina ese objeto | Acumular los conteos e imprimirlos al final de la búsqueda | `src/gcsgrep/gcs.py:139-148` el límite corta antes de abrir el objeto siguiente, y `tests/test_gcsgrep.py:484-493` exige conservar lo ya emitido; imprimir al final perdería los conteos si se levanta `CostLimitReached` |

## Trazabilidad

Salida de `check_spec.py`: OK — 12 requerimientos, 12 VCs.

| Requerimiento | VC |
|---|---|
| INV-1 | VC-INV-1 |
| INV-2 | VC-INV-2 |
| INV-3 | VC-INV-3 |
| FR-1 | VC-FR-1 |
| FR-2 | VC-FR-2 |
| FR-3 | VC-FR-3 |
| FR-4 | VC-FR-4 |
| FR-5 | VC-FR-5 |
| FR-6 | VC-FR-6 |
| FR-7 | VC-FR-7 |
| FR-8 | VC-FR-8 |
| NFR-1 | VC-NFR-1 |
