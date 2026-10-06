# Spec — flag `-c` / `--count` en `gcsgrep`

**Base:** `TP1 Greenfield/Tarea` (gcsgrep) @ `e912d5753f3dc7af52d01fb7b6a35f5bc5c530f9` · **Fecha:** 2026-10-06

Todas las rutas son relativas a `TP1 Greenfield/Tarea/`. Todos los comandos se corren desde ese directorio.

## Propósito

Quien busca un texto en un prefijo de un bucket puede saber cuántas líneas lo contienen en cada objeto sin recibir las líneas.

## Términos

| Término | Significa |
|---|---|
| línea coincidente | Línea de un objeto que contiene el patrón según `find_matches` (`src/gcsgrep/matcher.py:4-10`), con `-i` comparando en `casefold`. Una línea cuenta una sola vez aunque contenga el patrón varias veces. |
| conteo | Cantidad de líneas coincidentes de un objeto. |
| modo conteo | Ejecución con `-c` o `--count`. |
| modo línea | Ejecución sin `-c` ni `--count` (el comportamiento actual). |
| objeto salteado | Objeto `.gz` o con byte NUL en la muestra inicial; hoy no se lee (`src/gcsgrep/gcs.py:94-101`). |
| objeto fallido | Objeto cuya apertura o lectura lanza excepción; hoy se reporta en stderr y se sigue (`src/gcsgrep/gcs.py:165-170`). |
| línea de conteo | Línea de stdout con formato `<uri del objeto>:<conteo>`, p. ej. `gs://B/app/a.log:3`. |
| `run(...)` | Helper de `tests/test_gcsgrep.py:71-77`: corre `main` con un `FakeClient` y devuelve `(exit code, stdout, stderr)`. |

## Alcance

### Dentro

| Archivo / módulo | Qué cambia |
|---|---|
| `src/gcsgrep/cli.py` | `build_parser` agrega `-c` / `--count` (`store_true`). En modo conteo `main` no imprime líneas coincidentes y sí imprime una línea de conteo por objeto con conteo ≥ 1. |
| `src/gcsgrep/gcs.py` | `_scan_blob` devuelve el conteo (`int`) en vez de `bool`. `scan` acepta un callback opcional `on_count(uri, conteo)` que se llama cuando un objeto termina de leerse sin excepción y su conteo es ≥ 1. `result.matched` sigue siendo `True` si algún conteo fue ≥ 1. |
| `tests/test_gcsgrep.py` | Tests nuevos con prefijo `test_cflag_` (ningún test existente contiene `cflag`), uno por VC-FR e INV nuevo de esta spec. Los tests existentes no se modifican. |
| `README.md` | La línea de uso pasa a `gcsgrep [-i] [-n] [-c] "patrón literal" gs://bucket/prefijo/` y se agrega un ejemplo de salida en modo conteo. |

### Fuera

| Qué queda afuera | Por qué |
|---|---|
| Imprimir `<uri>:0` para objetos sin líneas coincidentes | Rompería la regla de stdout vacío sin coincidencias (ver D-2). |
| Total agregado de todos los objetos (una línea `total:N`) | No fue pedido; se obtiene sumando la salida con `awk -F: '{s+=$NF} END {print s}'`. |
| Contar ocurrencias del patrón en vez de líneas (estilo `grep -o \| wc -l`) | El matcher produce una tupla por línea (`src/gcsgrep/matcher.py:9-10`); contar ocurrencias es otro requerimiento. |
| Flags `-l` / `--files-with-matches` y `-v` / `--invert-match` | Son comportamientos distintos que no pidió el cambio. |
| Cambios en `src/gcsgrep/matcher.py` | El conteo se calcula sobre lo que `find_matches` ya devuelve; el criterio de coincidencia no cambia. |
| Tests de integración en `tests/integration/test_emulator.py` | Requieren `STORAGE_EMULATOR_HOST` o GCP real (`tests/integration/test_emulator.py:29-32`); el cambio es de formateo y orquestación en `cli.py`/`gcs.py`, que los tests con `FakeClient` cubren. |
| Leer `.gz` u objetos binarios en modo conteo | Siguen salteados igual que en modo línea (FR-6). |

## Invariantes

### INV-1 · La suite existente sigue verde

Los 41 tests que hoy pasan siguen pasando sin modificarse, y los 31 de integración siguen salteándose sin emulador.

- **VC-INV-1** · `py -3 -m pytest -q tests/test_gcsgrep.py -k "not cflag"` → `41 passed` (más `N deselected` cuando existan los tests nuevos), exit 0
- **VC-INV-1.2** · `py -3 -m pytest -q tests/integration` sin `STORAGE_EMULATOR_HOST` ni `GCSGREP_INTEGRATION` → `31 skipped`, exit 0

### INV-2 · Sin `-c` la salida es idéntica a la actual

En modo línea, stdout, stderr y exit code son los mismos que en la base (formatos de `src/gcsgrep/cli.py:63-67`).

- **VC-INV-2** · `py -3 -m pytest -q tests/test_gcsgrep.py -k "(vc4 or vc19 or vc26 or vc6 or vc27) and not cflag"` → `7 passed`, exit 0

### INV-3 · `scan` sigue aceptando las llamadas actuales

`scan` se puede llamar sin `on_count`, como lo hace `tests/test_gcsgrep.py:153-159`, y su `on_match` sigue recibiendo cada línea coincidente.

- **VC-INV-3** · `py -3 -m pytest -q tests/test_gcsgrep.py::test_vc3_matches_crossing_chunk_boundaries_without_local_files` → `1 passed`, exit 0

### INV-4 · El progreso en stderr no cambia en modo conteo

Cada 100 objetos inspeccionados se imprime `gcsgrep: objetos inspeccionados: N` en stderr (`src/gcsgrep/cli.py:72-73`), también con `-c`.

- **VC-INV-4** · `run(["-c", "timeout", "gs://logs/"], [FakeBlob(f"object-{i:03d}.log", b"healthy\n") for i in range(100)])` → `(1, "", "gcsgrep: objetos inspeccionados: 100\n")`

## Requerimientos

### FR-1 · `-c` imprime una línea de conteo por objeto en lugar de las líneas coincidentes

- **Dado** el objeto `app/a.log` con contenido `b"timeout 1\nok\ntimeout 2\ntimeout 3\n"` (3 líneas coincidentes) y `app/b.log` con `b"timeout\n"` (1)
- **Cuando** se corre `gcsgrep -c timeout gs://B/app/`
- **Entonces** stdout tiene exactamente una línea de conteo por objeto, ninguna línea coincidente, stderr vacío y exit 0
- **VC-FR-1** · `run(["-c", "timeout", "gs://B/app/"], [FakeBlob("app/a.log", b"timeout 1\nok\ntimeout 2\ntimeout 3\n"), FakeBlob("app/b.log", b"timeout\n")])` → `(0, "gs://B/app/a.log:3\ngs://B/app/b.log:1\n", "")`

### FR-2 · `--count` es equivalente a `-c`

- **Dado** los mismos dos objetos de FR-1
- **Cuando** se corre `gcsgrep --count timeout gs://B/app/`
- **Entonces** stdout, stderr y exit code son idénticos a los de `-c`
- **VC-FR-2** · `run(["--count", "timeout", "gs://B/app/"], [FakeBlob("app/a.log", b"timeout 1\nok\ntimeout 2\ntimeout 3\n"), FakeBlob("app/b.log", b"timeout\n")])` → `(0, "gs://B/app/a.log:3\ngs://B/app/b.log:1\n", "")`

### FR-3 · Objetos sin líneas coincidentes no se imprimen

- **Dado** `a.log` con `b"timeout\n"` y `clean.log` con `b"healthy\n"`; y por separado un único objeto `only.log` con `b"healthy\n"`
- **Cuando** se corre `gcsgrep -c timeout gs://B/` sobre cada conjunto
- **Entonces** con el primer conjunto `clean.log` no aparece en stdout y el exit es 0; con el segundo stdout queda vacío y el exit es 1
- **VC-FR-3** · `run(["-c", "timeout", "gs://B/"], [FakeBlob("a.log", b"timeout\n"), FakeBlob("clean.log", b"healthy\n")])` → `(0, "gs://B/a.log:1\n", "")`; `run(["-c", "timeout", "gs://B/"], [FakeBlob("only.log", b"healthy\n")])` → `(1, "", "")`

### FR-4 · Una línea con varias apariciones del patrón cuenta una vez

- **Dado** `dup.log` con `b"timeout timeout\nx\ntimeout\n"` (2 líneas coincidentes, 3 apariciones)
- **Cuando** se corre `gcsgrep -c timeout gs://B/`
- **Entonces** el conteo es 2
- **VC-FR-4** · `run(["-c", "timeout", "gs://B/"], [FakeBlob("dup.log", b"timeout timeout\nx\ntimeout\n")])` → `(0, "gs://B/dup.log:2\n", "")`

### FR-5 · `-i` y `-n` se combinan con `-c`

- **Dado** `app.log` con `b"TIMEOUT\nTimeout\ntimeout\n"`
- **Cuando** se corre `gcsgrep -c -i timeout gs://logs/`, `gcsgrep -c timeout gs://logs/` y `gcsgrep -c -n -i timeout gs://logs/`
- **Entonces** con `-i` el conteo es 3, sin `-i` es 1, y `-n` no cambia la línea de conteo
- **VC-FR-5** · `run(["-c", "-i", "timeout", "gs://logs/"], [FakeBlob("app.log", b"TIMEOUT\nTimeout\ntimeout\n")])` → `(0, "gs://logs/app.log:3\n", "")`; sin `-i` → `(0, "gs://logs/app.log:1\n", "")`; con `["-c", "-n", "-i", ...]` → `(0, "gs://logs/app.log:3\n", "")`

### FR-6 · Objetos salteados no producen línea de conteo

- **Dado** `binary.dat` con `b"timeout\x00not text"`, `compressed.GZ` con `b"timeout"` y `app.log` con `b"timeout\n"`
- **Cuando** se corre `gcsgrep -c timeout gs://logs/`
- **Entonces** solo `app.log` aparece en stdout, stderr vacío y exit 0
- **VC-FR-6** · `run(["-c", "timeout", "gs://logs/"], [FakeBlob("binary.dat", b"timeout\x00not text"), FakeBlob("compressed.GZ", b"timeout"), FakeBlob("app.log", b"timeout\n")])` → `(0, "gs://logs/app.log:1\n", "")`

### FR-7 · Un objeto fallido no imprime conteo, se reporta y el escaneo sigue

- **Dado** `partial/mixed.log` con `b"timeout 1\ncaf\xe9 timeout 2\ntimeout 3\n"` (la línea 2 no es UTF-8 válido) y `partial/ok.log` con `b"timeout\n"`
- **Cuando** se corre `gcsgrep -c timeout gs://B/partial/`
- **Entonces** `mixed.log` no tiene línea de conteo (ni parcial), stderr empieza con `gcsgrep: no se pudo leer gs://B/partial/mixed.log:`, `ok.log` se cuenta y el exit es 2
- **VC-FR-7** · `run(["-c", "timeout", "gs://B/partial/"], [FakeBlob("partial/mixed.log", b"timeout 1\ncaf\xe9 timeout 2\ntimeout 3\n"), FakeBlob("partial/ok.log", b"timeout\n")])` → exit `2`, stdout `"gs://B/partial/ok.log:1\n"`, stderr empieza con `"gcsgrep: no se pudo leer gs://B/partial/mixed.log:"` y no contiene `"Traceback"`

### FR-8 · Al alcanzar un límite se conservan los conteos ya impresos

- **Dado** `ten.log` con `b"timeout!!\n"` (10 bytes) y `twenty.log` con `b"timeout 01234567890\n"` (20 bytes)
- **Cuando** se corre `gcsgrep -c --max-bytes 29 timeout gs://B/`
- **Entonces** stdout tiene el conteo de `ten.log`, stderr tiene el mensaje de límite, `twenty.log` no se abre y el exit es 2
- **VC-FR-8** · `blobs = [FakeBlob("ten.log", b"timeout!!\n"), FakeBlob("twenty.log", b"timeout 01234567890\n")]; run(["-c", "--max-bytes", "29", "timeout", "gs://B/"], blobs)` → exit `2`, stdout `"gs://B/ten.log:1\n"`, stderr contiene `"gcsgrep: límite de seguridad alcanzado: máximo 29 bytes"`, `blobs[1].opened is False`

### FR-9 · Las líneas de conteo siguen el orden del listado

- **Dado** `app/b.log` con `b"mark\nmark\n"` listado antes que `app/a.log` con `b"mark\n"`
- **Cuando** se corre `gcsgrep -c mark gs://B/app/`
- **Entonces** `b.log` sale antes que `a.log` (orden del listado, no alfabético)
- **VC-FR-9** · `run(["-c", "mark", "gs://B/app/"], [FakeBlob("app/b.log", b"mark\nmark\n"), FakeBlob("app/a.log", b"mark\n")])` → `(0, "gs://B/app/b.log:2\ngs://B/app/a.log:1\n", "")`

### FR-10 · Patrón vacío cuenta todas las líneas, incluida la última sin terminador

- **Dado** `edge/nonl.log` con `b"a\nb timeout"` (2 líneas, la última sin `\n`)
- **Cuando** se corre `gcsgrep -c "" gs://B/edge/`
- **Entonces** el conteo es 2
- **VC-FR-10** · `run(["-c", "", "gs://B/edge/"], [FakeBlob("edge/nonl.log", b"a\nb timeout")])` → `(0, "gs://B/edge/nonl.log:2\n", "")`

### FR-11 · La ayuda y el README documentan el flag

- **Dado** el proyecto instalado con el cambio
- **Cuando** se pide la ayuda del CLI y se lee la sección "Uso" de `README.md`
- **Entonces** la ayuda lista `-c, --count` y el README muestra la línea de uso con `[-c]`
- **VC-FR-11** · `py -3 -m gcsgrep --help` → stdout contiene `-c, --count`, exit 0; `grep -F 'gcsgrep [-i] [-n] [-c] "patrón literal" gs://bucket/prefijo/' README.md` → 1 coincidencia, exit 0

## Decisiones

| ID | Decisión | Alternativa descartada | Fundamento en el código base |
|---|---|---|---|
| D-1 | Línea de conteo `<uri>:<conteo>` | `<uri> <conteo>` o tabla con encabezado | `src/gcsgrep/cli.py:65-67` ya separa la URI del resto con `:`; mantener el separador permite `cut -d: -f…`/`awk -F:` igual que en modo línea. |
| D-2 | Omitir objetos con conteo 0 | Imprimir `<uri>:0` como GNU `grep -c` | `tests/test_gcsgrep.py:291-295` fija stdout vacío y exit 1 sin coincidencias, y `src/gcsgrep/cli.py:30-33` permite hasta 1000 objetos por defecto: imprimir ceros llenaría stdout de ruido. |
| D-3 | Un objeto fallido no imprime conteo | Imprimir el conteo parcial de las líneas leídas antes del error | `src/gcsgrep/gcs.py:165-170` ya reporta el objeto fallido en stderr y marca `had_errors`; en modo línea cada línea impresa es verdadera por sí sola (`tests/test_gcsgrep.py:265-272`), pero un conteo parcial no se distingue en stdout de uno completo. |
| D-4 | `-n` se ignora en modo conteo | Rechazar `-c -n` con error de argparse | `src/gcsgrep/cli.py:28` define `-n` como `store_true` independiente y `src/gcsgrep/cli.py:63-67` solo lo usa para formatear líneas coincidentes; no hay línea a la que ponerle número. |
| D-5 | `_scan_blob` devuelve el conteo y `scan` expone `on_count` opcional | Contar en `cli.py` agrupando las llamadas a `on_match` por URI | `src/gcsgrep/gcs.py:103-108` ya recorre las coincidencias de un objeto completo en un solo lugar, y `src/gcsgrep/gcs.py:157-170` distingue fin normal de excepción por objeto; desde `cli.py` no se ve cuándo termina ni si falló un objeto. Los callbacks opcionales con default siguen el patrón de `src/gcsgrep/gcs.py:122-131`. |
| D-6 | Contar líneas coincidentes, no apariciones | Contar cada aparición del patrón | `src/gcsgrep/matcher.py:9-10` emite una tupla por línea con `needle in haystack`, sin posición ni cantidad de apariciones. |
| D-7 | `-c` / `--count` como `store_true` con forma corta y larga | Solo `--count` | `src/gcsgrep/cli.py:27-28` define `-i/--ignore-case` y `-n/--line-number` con ambas formas. |
| D-8 | Exit codes sin cambios (0 algún conteo ≥ 1, 1 ninguno, 2 error o límite) | Exit 0 siempre que no haya error | `src/gcsgrep/cli.py:94-96` decide el exit por `had_errors` y `matched`; con D-5 `matched` sigue siendo "algún conteo ≥ 1". |

## Trazabilidad

Salida de `check_spec.py`: OK — 15 requerimientos, 16 VCs.

| Requerimiento | VC |
|---|---|
| INV-1 | VC-INV-1 |
| INV-1 | VC-INV-1.2 |
| INV-2 | VC-INV-2 |
| INV-3 | VC-INV-3 |
| INV-4 | VC-INV-4 |
| FR-1 | VC-FR-1 |
| FR-2 | VC-FR-2 |
| FR-3 | VC-FR-3 |
| FR-4 | VC-FR-4 |
| FR-5 | VC-FR-5 |
| FR-6 | VC-FR-6 |
| FR-7 | VC-FR-7 |
| FR-8 | VC-FR-8 |
| FR-9 | VC-FR-9 |
| FR-10 | VC-FR-10 |
| FR-11 | VC-FR-11 |
