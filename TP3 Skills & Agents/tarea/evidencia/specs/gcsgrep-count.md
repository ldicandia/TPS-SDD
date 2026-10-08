# Spec — flag `-c` / `--count` en `gcsgrep`

**Base:** `TP1 Greenfield/Tarea` @ `cffc0d7a6f856fa0f89881279f66766d2b48a819` · **Fecha:** 2026-10-08

Todas las rutas de esta spec son relativas a `TP1 Greenfield/Tarea/` y todos los
comandos se corren desde esa carpeta. Los VC escritos como `run([...], [...])`
usan el helper `run` y la clase `FakeBlob` de `tests/test_gcsgrep.py:25-77`
(cliente falso, bucket `B`); el resultado es la tupla `(exit code, stdout, stderr)`.

## Propósito

Quien busca un texto en un bucket puede saber cuántas líneas coinciden en cada objeto
sin tener que leer ni contar las líneas impresas.

## Términos

| Término | Significa |
|---|---|
| objeto | Un blob listado bajo la ubicación `gs://bucket/prefijo`, identificado en la salida por su URI `gs://<bucket>/<nombre>`. |
| línea coincidente | Una línea de un objeto que contiene el patrón literal (con `-i`, sin distinguir mayúsculas). Una línea con varias apariciones del patrón es una sola línea coincidente. |
| conteo | La cantidad de líneas coincidentes de un objeto. |
| modo conteo | Ejecución de `gcsgrep` con `-c` o `--count`. |
| objeto fallido | Objeto cuya lectura o decodificación UTF-8 falla y se reporta en stderr con `gcsgrep: no se pudo leer …`. |

## Alcance

### Dentro

| Archivo / módulo | Qué cambia |
|---|---|
| `src/gcsgrep/cli.py` | `build_parser` agrega `-c/--count` (`store_true`). En modo conteo, `main` acumula el conteo por objeto en lugar de imprimir cada línea coincidente, descarta el conteo de un objeto fallido e imprime `<uri>:<conteo>` por objeto cuando `scan` vuelve o lanza `CostLimitReached` / `GcsGrepError` (D-3). |
| `tests/test_gcsgrep.py` | Se agregan 14 tests unitarios, uno por cada VC de FR-1 a FR-14, sin modificar ni borrar los 41 existentes. |
| `README.md` | La sección "Uso" documenta `-c` / `--count` y su formato de salida (FR-15). |

### Fuera

| Qué queda afuera | Por qué |
|---|---|
| `src/gcsgrep/gcs.py` y `src/gcsgrep/matcher.py` | `scan` ya entrega cada línea coincidente con la URI del objeto (`gcs.py:154-155`); contar se resuelve en el callback de la CLI sin cambiar la API de escaneo. |
| Imprimir `<uri>:0` para objetos sin coincidencias | Ver D-1: no hay señal de "objeto terminado" en `scan`, y hoy un objeto sin coincidencias no produce salida. |
| Total agregado de todos los objetos | No fue pedido: el pedido es un conteo por objeto. |
| Contar apariciones del patrón en vez de líneas | `-c` cuenta líneas coincidentes (D-5); contar apariciones sería otro flag. |
| Otros flags tipo grep (`-l`, `-m/--max-count`, `-o`, `-v`) | No forman parte de este cambio. |
| Tests nuevos en `tests/integration/test_emulator.py` | Requieren emulador o GCP (`tests/integration/test_emulator.py:29`); el comportamiento nuevo vive en `cli.py` y se cubre con el cliente falso. Los tests de integración existentes sí deben seguir pasando (INV-2). |

## Invariantes

### INV-1 · La suite existente sigue verde

Sin emulador, la suite completa pasa: 41 tests unitarios existentes + 14 nuevos, y los 31 de integración se saltean igual que en la base.

- **VC-INV-1** · `py -3 -m pytest -q` → `55 passed, 31 skipped`, 0 failed, exit 0

### INV-2 · Los tests existentes no se modifican

El cambio solo agrega líneas a `tests/test_gcsgrep.py` y no toca `tests/integration/test_emulator.py`.

- **VC-INV-2** · `git diff cffc0d7 -- tests/ | grep -v "^---" | grep -c "^-"` → `0` (ninguna línea existente borrada ni modificada)

### INV-3 · La suite de integración existente sigue verde contra el emulador

Los tests de `tests/integration/test_emulator.py` ejecutan el CLI real (`python -m gcsgrep`, `tests/integration/test_emulator.py:132`), que este cambio toca.

- **VC-INV-3** · `docker compose up -d --wait` y luego `STORAGE_EMULATOR_HOST=http://localhost:4588 GOOGLE_CLOUD_PROJECT=floci-local py -3 -m pytest -q tests/integration` → `31 passed`, 0 failed, 0 skipped, exit 0

### INV-4 · Sin `-c` la salida no cambia

Sin `-c`, cada línea coincidente se imprime como `gs://B/a.log:timeout 1`, o `gs://B/a.log:2:timeout 1` con `-n` (`cli.py:63-67`).

- **VC-INV-4** · `run(["-n", "timeout", "gs://B/"], [FakeBlob("a.log", b"x\ntimeout 1\ntimeout 2\n")])` → `(0, "gs://B/a.log:2:timeout 1\ngs://B/a.log:3:timeout 2\n", "")`

### INV-5 · Sin `-c` los exit codes conservan su significado

0 = hubo al menos una línea coincidente, 1 = ninguna, 2 = error o límite (`cli.py:87-96`). Con `-c` los mismos códigos se exigen en FR-1, FR-4, FR-8, FR-9, FR-12, FR-13 y FR-14.

- **VC-INV-5** · `py -3 -m pytest -q tests/test_gcsgrep.py -k "vc7 or vc20 or vc21 or vc22 or vc11"` → `10 passed`, 0 failed, exit 0

## Requerimientos

### FR-1 · `-c` imprime un conteo por objeto en lugar de las líneas

- **Dado** el bucket `B` con `a.log` = `timeout 1\nok\ntimeout 2\n` y `b.log` = `timeout\n`, listados en ese orden
- **Cuando** se ejecuta `gcsgrep -c timeout gs://B/`
- **Entonces** stdout tiene una línea `<uri>:<conteo>` por objeto, en el orden del listado, ninguna línea de texto del objeto, stderr vacío y exit code 0
- **VC-FR-1** · `run(["-c", "timeout", "gs://B/"], [FakeBlob("a.log", b"timeout 1\nok\ntimeout 2\n"), FakeBlob("b.log", b"timeout\n")])` → `(0, "gs://B/a.log:2\ngs://B/b.log:1\n", "")`

### FR-2 · `--count` es sinónimo de `-c`

- **Dado** el mismo bucket que FR-1
- **Cuando** se ejecuta `gcsgrep --count timeout gs://B/`
- **Entonces** la salida y el exit code son idénticos a los de `-c`
- **VC-FR-2** · `run(["--count", "timeout", "gs://B/"], [FakeBlob("a.log", b"timeout 1\nok\ntimeout 2\n"), FakeBlob("b.log", b"timeout\n")])` → `(0, "gs://B/a.log:2\ngs://B/b.log:1\n", "")`

### FR-3 · Un objeto sin líneas coincidentes no imprime conteo

- **Dado** el bucket `B` con `a.log` = `nada\n` y `b.log` = `timeout\n`
- **Cuando** se ejecuta `gcsgrep -c timeout gs://B/`
- **Entonces** stdout solo tiene la línea de `b.log` y el exit code es 0
- **VC-FR-3** · `run(["-c", "timeout", "gs://B/"], [FakeBlob("a.log", b"nada\n"), FakeBlob("b.log", b"timeout\n")])` → `(0, "gs://B/b.log:1\n", "")`

### FR-4 · Sin líneas coincidentes en ningún objeto, stdout vacío y exit 1

- **Dado** el bucket `B` con `a.log` = `nada\n`
- **Cuando** se ejecuta `gcsgrep -c timeout gs://B/`
- **Entonces** stdout y stderr quedan vacíos y el exit code es 1
- **VC-FR-4** · `run(["-c", "timeout", "gs://B/"], [FakeBlob("a.log", b"nada\n")])` → `(1, "", "")`

### FR-5 · Se cuentan líneas, no apariciones

- **Dado** el bucket `B` con `a.log` = `timeout timeout timeout\n`
- **Cuando** se ejecuta `gcsgrep -c timeout gs://B/`
- **Entonces** el conteo de `a.log` es 1
- **VC-FR-5** · `run(["-c", "timeout", "gs://B/"], [FakeBlob("a.log", b"timeout timeout timeout\n")])` → `(0, "gs://B/a.log:1\n", "")`

### FR-6 · `-i` aplica al conteo

- **Dado** el bucket `B` con `a.log` = `TIMEOUT\nTimeout\ntimeout\nok\n`
- **Cuando** se ejecuta `gcsgrep -c -i timeout gs://B/`
- **Entonces** el conteo de `a.log` es 3
- **VC-FR-6** · `run(["-c", "-i", "timeout", "gs://B/"], [FakeBlob("a.log", b"TIMEOUT\nTimeout\ntimeout\nok\n")])` → `(0, "gs://B/a.log:3\n", "")`

### FR-7 · `-n` no altera la salida del modo conteo

- **Dado** el bucket `B` con `a.log` = `x\ntimeout\n`
- **Cuando** se ejecuta `gcsgrep -c -n timeout gs://B/`
- **Entonces** la salida es la misma que sin `-n`, sin número de línea y sin error
- **VC-FR-7** · `run(["-c", "-n", "timeout", "gs://B/"], [FakeBlob("a.log", b"x\ntimeout\n")])` → `(0, "gs://B/a.log:1\n", "")`

### FR-8 · Un objeto fallido no imprime conteo y el escaneo sigue

- **Dado** el bucket `B` con `mixed.log` = `timeout 1\ncaf\xe9 timeout 2\n` (la segunda línea no es UTF-8 válido) y `ok.log` = `timeout\n`
- **Cuando** se ejecuta `gcsgrep -c timeout gs://B/`
- **Entonces** stdout solo tiene el conteo de `ok.log`, stderr empieza con `gcsgrep: no se pudo leer gs://B/mixed.log:` y el exit code es 2
- **VC-FR-8** · `run(["-c", "timeout", "gs://B/"], [FakeBlob("mixed.log", b"timeout 1\ncaf\xe9 timeout 2\n"), FakeBlob("ok.log", b"timeout\n")])` → exit code `2`, stdout `"gs://B/ok.log:1\n"`, stderr empieza con `"gcsgrep: no se pudo leer gs://B/mixed.log:"`

### FR-9 · Al alcanzar un límite se imprimen los conteos de los objetos ya escaneados

- **Dado** el bucket `B` con `a.log` = `timeout\n` y `big.log` = `timeout\n` con tamaño declarado `1024**3 + 1` bytes
- **Cuando** se ejecuta `gcsgrep -c timeout gs://B/` con el límite de bytes por defecto
- **Entonces** stdout tiene el conteo de `a.log`, `big.log` no se abre, stderr informa el límite y el exit code es 2
- **VC-FR-9** · `big = FakeBlob("big.log", b"timeout\n", size=1024**3 + 1); run(["-c", "timeout", "gs://B/"], [FakeBlob("a.log", b"timeout\n"), big])` → exit code `2`, stdout `"gs://B/a.log:1\n"`, stderr contiene `"gcsgrep: límite de seguridad alcanzado: máximo 1073741824 bytes"` y `big.opened is False`

### FR-10 · Los objetos `.gz` y binarios se saltean también en modo conteo

- **Dado** el bucket `B` con `a.gz` = `timeout\n`, `b.bin` = `\x00timeout\n` y `c.log` = `timeout\n`
- **Cuando** se ejecuta `gcsgrep -c timeout gs://B/`
- **Entonces** solo `c.log` tiene conteo
- **VC-FR-10** · `run(["-c", "timeout", "gs://B/"], [FakeBlob("a.gz", b"timeout\n"), FakeBlob("b.bin", b"\x00timeout\n"), FakeBlob("c.log", b"timeout\n")])` → `(0, "gs://B/c.log:1\n", "")`

### FR-11 · La ayuda documenta el flag

- **Dado** el paquete instalado o `src` en el `PYTHONPATH`
- **Cuando** se ejecuta `gcsgrep --help`
- **Entonces** la ayuda lista `-c, --count` y el exit code es 0
- **VC-FR-11** · `main(["--help"])` con `capsys` de pytest → lanza `SystemExit` con `code == 0` y `capsys.readouterr().out` contiene `-c, --count`

### FR-12 · Si el listado falla a mitad del escaneo se imprimen los conteos ya acumulados

- **Dado** un cliente cuyo `list_blobs` entrega `FakeBlob("a.log", b"timeout\n")` y después lanza `RuntimeError("page 2")`
- **Cuando** se ejecuta `gcsgrep -c timeout gs://B/`
- **Entonces** stdout tiene el conteo de `a.log`, stderr informa el fallo de enumeración y el exit code es 2
- **VC-FR-12** · `main(["-c", "timeout", "gs://B/"], client_factory=<cliente cuyo list_blobs es un generador que hace yield FakeBlob("a.log", b"timeout\n") y luego raise RuntimeError("page 2")>, stdout=..., stderr=...)` → exit code `2`, stdout `"gs://B/a.log:1\n"`, stderr `"gcsgrep: no se pudo enumerar gs://B/: page 2\n"`

### FR-13 · Con `-c`, un URI inválido termina con 2 antes de escanear

- **Dado** la ubicación `logs/app`, sin el esquema `gs://`
- **Cuando** se ejecuta `gcsgrep -c timeout logs/app`
- **Entonces** stdout queda vacío, stderr informa el URI inválido y el exit code es 2
- **VC-FR-13** · `run(["-c", "timeout", "logs/app"])` → `(2, "", "gcsgrep: la ubicación debe comenzar con gs://\n")`

### FR-14 · Con `-c`, un fallo de listado antes del primer objeto termina con 2 y stdout vacío

- **Dado** un bucket cuyo listado falla de entrada con `RuntimeError("404")`
- **Cuando** se ejecuta `gcsgrep -c timeout gs://logs/app/`
- **Entonces** stdout queda vacío, stderr informa el fallo y el exit code es 2
- **VC-FR-14** · `run(["-c", "timeout", "gs://logs/app/"], list_error=RuntimeError("404"))` → `(2, "", "gcsgrep: no se pudo enumerar gs://logs/app/: 404\n")`

### FR-15 · El README documenta el modo conteo

- **Dado** `README.md` con la sección "## Uso" (`README.md:35`)
- **Cuando** se lee esa sección
- **Entonces** la línea de uso incluye `[-c]`, el texto nombra la forma larga `--count` y hay un ejemplo con salida `gs://logs/app/server.log:3`
- **VC-FR-15** · `grep -qF 'gcsgrep [-i] [-n] [-c] "patrón literal" gs://bucket/prefijo/' README.md && grep -qF -- '--count' README.md && grep -qF 'gs://logs/app/server.log:3' README.md` → exit 0

## Decisiones

| ID | Decisión | Alternativa descartada | Fundamento en el código base |
|---|---|---|---|
| D-1 | Solo se imprime conteo para objetos con al menos una línea coincidente. | Imprimir `<uri>:0` para cada objeto inspeccionado, como `grep -c` con varios archivos. | `src/gcsgrep/gcs.py:105-107` solo invoca `on_match` por línea coincidente y `scan` no tiene callback de objeto terminado; además un objeto vacío o sin coincidencias hoy no produce salida (`tests/test_gcsgrep.py:196-203`). |
| D-2 | El conteo se implementa en `cli.py`, dentro del callback `emit_match`, sin cambiar la firma de `scan`. | Agregar un parámetro `count` a `scan` / `_scan_blob`. | `src/gcsgrep/gcs.py:151-154` arma la URI completa del objeto y se la pasa a `on_match` en cada línea coincidente, que es la clave del conteo; `src/gcsgrep/cli.py:63-67` es el único lugar que imprime a stdout, así que decide qué se imprime. |
| D-3 | Los conteos se acumulan en un diccionario con orden de inserción y se imprimen en el orden del listado cuando `scan` vuelve, y también antes del mensaje de error cuando `scan` lanza `CostLimitReached` o `GcsGrepError` (FR-9, FR-12). | Imprimir cada conteo apenas se ve el primer match del objeto siguiente; o descartar los conteos si `scan` lanza. | `src/gcsgrep/gcs.py:137` recorre los objetos en el orden del listado, uno por vez, y `tests/test_gcsgrep.py:432` exige que la salida siga ese orden; en modo normal las líneas de los objetos ya escaneados quedan en stdout aunque después `scan` lance (`tests/test_gcsgrep.py:484-493`, `src/gcsgrep/cli.py:87-92`), y el modo conteo conserva esa información. |
| D-4 | Un objeto fallido no imprime conteo, aunque haya tenido líneas coincidentes antes del error. | Imprimir el conteo parcial, como el modo normal imprime las líneas previas al error. | `src/gcsgrep/gcs.py:165-170` llama a `on_error` con la misma URI que usó `on_match` (`gcs.py:152`) después de emitir las líneas previas (`gcs.py:79-80` y `gcs.py:105-107`); la CLI puede descartar esa entrada, y un número parcial no se distingue de uno completo, a diferencia de las líneas parciales del modo normal. |
| D-5 | Se cuentan líneas coincidentes, no apariciones del patrón. | Contar todas las apariciones dentro de cada línea. | `src/gcsgrep/matcher.py:4-10` produce un único `(número, línea)` por línea que contiene el patrón, sin posición ni cantidad de apariciones. |
| D-6 | `-n` junto a `-c` se acepta y no cambia la salida. | Rechazar la combinación con exit 2 (grupo mutuamente excluyente de argparse). | `src/gcsgrep/cli.py:28` define `-n` como `store_true` independiente y `src/gcsgrep/gcs.py:107` solo usa el número de línea como argumento de `on_match`, que en modo conteo se ignora. |
| D-7 | Formato `<uri>:<conteo>`. | Formatos como `<conteo> <uri>` o una tabla. | `src/gcsgrep/cli.py:67` ya usa `<uri>:<texto>` con `:` como separador, así que el modo conteo conserva la misma forma de línea. |
| D-8 | Los exit codes no cambian: 0 si algún objeto tuvo conteo, 1 si ninguno, 2 si hubo objeto fallido, límite, URI inválido o fallo de listado. | Exit 0 siempre que el escaneo termine sin error, aunque no haya coincidencias. | `src/gcsgrep/cli.py:87-96` deriva el exit code de `result.matched` y `result.had_errors`, que `scan` calcula igual con o sin `-c` (`gcs.py:164-166`). |

## Trazabilidad

| Requerimiento | VC |
|---|---|
| INV-1 | VC-INV-1 |
| INV-2 | VC-INV-2 |
| INV-3 | VC-INV-3 |
| INV-4 | VC-INV-4 |
| INV-5 | VC-INV-5 |
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
| FR-12 | VC-FR-12 |
| FR-13 | VC-FR-13 |
| FR-14 | VC-FR-14 |
| FR-15 | VC-FR-15 |
