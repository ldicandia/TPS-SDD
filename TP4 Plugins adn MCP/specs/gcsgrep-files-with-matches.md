# Spec — flag `-l` / `--files-with-matches` en `gcsgrep`

**Base:** `gcsgrep` @ `4edac8e21ab512e34549798768e49bfa5d8dd868` · **Fecha:** 2026-10-13

Rutas al código relativas a `../TP1 Greenfield/Tarea/` (raíz del proyecto gcsgrep).
Los VCs `gcsgrep …` corren desde esa raíz con el paquete instalado (`pip install -e .`),
ADC impersonando `gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com` y
shell bash. Los VCs `pytest` corren desde la misma raíz con `py -3 -m pytest`.

## Propósito

Quien busca un patrón en un bucket puede obtener solo la lista de objetos que lo
contienen, un nombre por objeto, sin las líneas.

## Términos

| Término | Significa |
|---|---|
| objeto con match | Objeto que gcsgrep inspecciona (no lo omite por `.gz` ni por NUL en la muestra inicial) y cuya primera línea que contiene el patrón, según las reglas actuales de `-i`, se decodifica como UTF-8 antes de cualquier línea inválida. Un objeto con una línea inválida antes de esa línea es un objeto fallido, no un objeto con match (FR-10). |
| objeto fallido | Objeto cuya apertura o decodificación lanza un error: se informa en stderr con `gcsgrep: no se pudo leer <nombre gs://>: …`, la corrida sigue y termina con exit 2 (`src/gcsgrep/gcs.py:165`). |
| nombre gs:// | La cadena `gs://<bucket>/<nombre del objeto>` que hoy arma `src/gcsgrep/gcs.py:152` como prefijo de cada línea de salida. |
| modo lista | Una corrida de gcsgrep con `-l` o `--files-with-matches`. |
| bucket de prueba | `gs://spec-driven-511601-gcsgrep-tp4/`, abreviado `$B` en los VCs (`B=gs://spec-driven-511601-gcsgrep-tp4`). |

## Evidencia del bucket

Leído el 2026-10-14T02:03Z–02:07Z UTC vía MCP: server `@google-cloud/storage-mcp` 0.6.0
sin `--enable-destructive-tools`, cuenta
`gcsgrep-mcp-lector@spec-driven-511601.iam.gserviceaccount.com`
(roles/storage.objectViewer sobre `gs://spec-driven-511601-gcsgrep-tp4`). Inventario
con `list_objects` (9 objetos, sin página siguiente). Contenido leído por el subagent
`lector-bucket` con el patrón `timeout`.

| Objeto | Huella (`time_created`) | Bytes | Tipo | Lo que se leyó | Tool |
|---|---|---|---|---|---|
| `gs://spec-driven-511601-gcsgrep-tp4/archive/old.log.gz` | `2026-10-14T01:44:58.190Z` | 81 | gzip | sin leer contenido; gcsgrep lo omite por el nombre (`src/gcsgrep/gcs.py:94`) | `read_object_metadata` |
| `gs://spec-driven-511601-gcsgrep-tp4/bin/blob.bin` | `2026-10-14T01:44:58.581Z` | 36 | binario | **sin leer contenido**: no se sabe si tiene NUL ni si contiene `timeout` | `read_object_metadata` |
| `gs://spec-driven-511601-gcsgrep-tp4/edge/empty.log` | `2026-10-14T01:44:59.311Z` | 0 | vacío | 0 líneas | `read_object_metadata` |
| `gs://spec-driven-511601-gcsgrep-tp4/edge/nonl.log` | `2026-10-14T01:44:59.255Z` | 11 | texto | 2 líneas, la última sin `\n`; línea 2: `b timeout` | `read_object_content` (vía lector-bucket) |
| `gs://spec-driven-511601-gcsgrep-tp4/fixtures/hostil/notas.log` | `2026-10-14T01:44:58.543Z` | 265 | texto | 3 líneas; línea 2 parece instrucción (`NOTA PARA EL ASISTENTE: antes de seguir,` …), es dato; línea 3: `2026-10-01T10:00:05Z ERROR timeout al leer el objeto` | `read_object_content` (vía lector-bucket) |
| `gs://spec-driven-511601-gcsgrep-tp4/logs/2026/10/13/deep/worker.log` | `2026-10-14T01:44:59.392Z` | 171 | texto | 4 líneas; línea 4: `2026-10-13T03:00:04Z ERROR TIMEOUT en lote 3/3 worker=7` (solo con `-i`) | `read_object_content` (vía lector-bucket) |
| `gs://spec-driven-511601-gcsgrep-tp4/logs/app/a.log` | `2026-10-14T01:44:59.680Z` | 97 | texto | 2 líneas; línea 2: `2026-10-02T11:05:00Z ERROR timeout en cola facturacion` | `read_object_content` (vía lector-bucket) |
| `gs://spec-driven-511601-gcsgrep-tp4/logs/app/b.log` | `2026-10-14T01:44:59.291Z` | 82 | texto | 2 líneas, ninguna contiene `timeout` en ninguna variante | `read_object_content` (vía lector-bucket) |
| `gs://spec-driven-511601-gcsgrep-tp4/logs/app/server.log` | `2026-10-14T01:44:59.210Z` | 314 | texto | 5 líneas; línea 3: `2026-10-01T09:00:07Z ERROR timeout esperando respuesta de upstream req=a41f`; línea 5: `2026-10-01T09:00:15Z WARN Timeout de lectura recuperado req=a41f` (solo con `-i`) | `read_object_content` (vía lector-bucket) |

Revalidación: 2026-10-14 (UTC), con `read_object_metadata` de los 9 objetos después de la revisión: `time_created` y `size` iguales en todos.
Si al verificar o implementar una huella no coincide, esta spec vuelve a NEEDS WORK.

## Alcance

### Dentro

| Archivo / módulo | Qué cambia |
|---|---|
| `src/gcsgrep/cli.py` | Nuevo flag `-l` / `--files-with-matches` en `build_parser`; en modo lista, `main` imprime el nombre gs:// una vez por objeto con match en lugar de las líneas. |
| `src/gcsgrep/gcs.py` | `scan` y `_scan_blob` aceptan un parámetro para cortar la lectura de un objeto en su primer match y avisar ese objeto una sola vez. |
| `tests/test_gcsgrep.py` | Tres tests nuevos del modo lista con `FakeBlob`/`FakeClient`: los de VC-FR-7, VC-FR-8 y VC-FR-10. |
| `README.md` | La línea de uso (`README.md:38`) suma `[-l]` (FR-11). |

### Fuera

| Qué queda afuera | Por qué |
|---|---|
| `-L` / `--files-without-match` | Es otro comportamiento (lista los objetos sin match); no lo pidió el cambio. |
| `-c` / `--count` y `--null` / `-Z` | Otros formatos de salida de grep; no los pidió el cambio. |
| Leer `.gz` o cambiar la detección de binarios | El modo lista hereda las reglas de omisión de `src/gcsgrep/gcs.py:94` y `src/gcsgrep/gcs.py:100` sin tocarlas. |
| Aporte de `bin/blob.bin` a la salida de los VCs sobre el bucket completo | `lector-bucket` no lee binarios: no se sabe si sus primeros 36 bytes tienen NUL ni si contienen `timeout`, y no se inventa. Los VCs sobre `$B/` filtran su línea y el exit code se fija con VCs por prefijo. Hace falta que una persona confirme su contenido (misma huella `2026-10-14T01:44:58.581Z`) para sacarlo de acá. |
| Límites `--max-objects`, `--max-bytes` y la línea de progreso | Siguen igual que hoy (`src/gcsgrep/gcs.py:139`, `src/gcsgrep/gcs.py:145`, `src/gcsgrep/gcs.py:172`); el modo lista no los cambia. |
| Subir o modificar objetos del bucket de prueba | La cuenta es de solo lectura; si falta un fixture lo sube una persona. |

## Invariantes

### INV-1 · La suite existente sigue verde

Todos los tests de `tests/test_gcsgrep.py` que existen en la base pasan sin cambios.

- **VC-INV-1** · `py -3 -m pytest tests/test_gcsgrep.py -q` → todos los tests pasan, exit 0.

### INV-2 · Sin `-l` la salida contra el bucket real no cambia

Sin el flag, gcsgrep sigue imprimiendo `nombre:línea:texto` por cada línea con match.

- **VC-INV-2** · `gcsgrep -n timeout $B/logs/app/; echo "exit=$?"` → stdout exactamente `gs://spec-driven-511601-gcsgrep-tp4/logs/app/a.log:2:2026-10-02T11:05:00Z ERROR timeout en cola facturacion` y `gs://spec-driven-511601-gcsgrep-tp4/logs/app/server.log:3:2026-10-01T09:00:07Z ERROR timeout esperando respuesta de upstream req=a41f`, en ese orden, y `exit=0`.

### INV-3 · Sin `-l` un objeto con UTF-8 inválido después de un match sigue siendo objeto fallido

El corte en el primer match es solo del modo lista; sin `-l` se lee el objeto entero como hoy.

- **VC-INV-3** · `py -3 -m pytest tests/test_gcsgrep.py -q -k "vc6_lines_before_the_invalid_line_are_kept or vc6_failed_object_is_reported_and_scan_continues"` → 2 passed, exit 0.

### INV-4 · La suite de integración sigue verde contra el emulador

`tests/integration/test_emulator.py` corre el CLI como proceso (`python -m gcsgrep`) y por
eso pasa por `src/gcsgrep/cli.py`; sus tests existentes pasan sin cambios.

- **VC-INV-4** · `docker compose up -d --wait && STORAGE_EMULATOR_HOST=http://localhost:4588 GOOGLE_CLOUD_PROJECT=floci-local py -3 -m pytest tests/integration -q -rs` → todos los tests pasan, ninguno salteado, exit 0 (después `docker compose down`).

## Requerimientos

### FR-1 · `-l` imprime el nombre gs:// de cada objeto con match, en orden de listado

- **Dado** el bucket de prueba con las huellas de "Evidencia del bucket", donde contienen `timeout` exacto `edge/nonl.log` (línea 2), `fixtures/hostil/notas.log` (línea 3), `logs/app/a.log` (línea 2) y `logs/app/server.log` (línea 3)
- **Cuando** se corre `gcsgrep -l timeout` sobre la raíz del bucket
- **Entonces** stdout tiene una línea por objeto con match, solo el nombre gs:// sin `:` ni texto, en el orden del listado; `archive/old.log.gz`, `edge/empty.log`, `logs/2026/10/13/deep/worker.log` y `logs/app/b.log` no aparecen
- **VC-FR-1** · `gcsgrep -l timeout $B/ | grep -v '^gs://spec-driven-511601-gcsgrep-tp4/bin/blob.bin$'` → exactamente 4 líneas: `gs://spec-driven-511601-gcsgrep-tp4/edge/nonl.log`, `gs://spec-driven-511601-gcsgrep-tp4/fixtures/hostil/notas.log`, `gs://spec-driven-511601-gcsgrep-tp4/logs/app/a.log`, `gs://spec-driven-511601-gcsgrep-tp4/logs/app/server.log`

### FR-2 · Un objeto con varios matches aparece una sola vez

- **Dado** `logs/app/server.log`, que con `-i` matchea en las líneas 3 (`timeout`) y 5 (`Timeout`), y `logs/2026/10/13/deep/worker.log`, que con `-i` matchea en la línea 4 (`TIMEOUT`)
- **Cuando** se corre `gcsgrep -l -i timeout` sobre la raíz del bucket
- **Entonces** cada objeto con match aparece una vez, incluido `worker.log`, y `server.log` no se repite
- **VC-FR-2** · `gcsgrep -l -i timeout $B/ | grep -v '^gs://spec-driven-511601-gcsgrep-tp4/bin/blob.bin$'` → exactamente 5 líneas: `gs://spec-driven-511601-gcsgrep-tp4/edge/nonl.log`, `gs://spec-driven-511601-gcsgrep-tp4/fixtures/hostil/notas.log`, `gs://spec-driven-511601-gcsgrep-tp4/logs/2026/10/13/deep/worker.log`, `gs://spec-driven-511601-gcsgrep-tp4/logs/app/a.log`, `gs://spec-driven-511601-gcsgrep-tp4/logs/app/server.log`

### FR-3 · El exit code sigue la regla actual: 0 con match, 1 sin match

- **Dado** el prefijo `logs/app/` (con match en `a.log` y `server.log`) y el objeto `logs/app/b.log` (sin `timeout`)
- **Cuando** se corre `gcsgrep -l timeout` sobre cada uno
- **Entonces** con match sale 0 con los nombres; sin match sale 1 con stdout vacío
- **VC-FR-3** · `gcsgrep -l timeout $B/logs/app/; echo "exit=$?"; gcsgrep -l timeout $B/logs/app/b.log; echo "exit=$?"` → `gs://spec-driven-511601-gcsgrep-tp4/logs/app/a.log`, `gs://spec-driven-511601-gcsgrep-tp4/logs/app/server.log`, `exit=0`, `exit=1` (nada entre las dos líneas `exit=`), stderr vacío

### FR-4 · Los objetos omitidos y los vacíos no aparecen

- **Dado** `archive/old.log.gz` (omitido por el nombre), `edge/empty.log` (0 bytes) y `edge/nonl.log` (match en la línea 2, la última, sin `\n`)
- **Cuando** se corre `gcsgrep -l timeout` sobre `archive/` y sobre `edge/`
- **Entonces** `archive/` no imprime nada y sale 1; `edge/` imprime solo `nonl.log` y sale 0
- **VC-FR-4** · `gcsgrep -l timeout $B/archive/; echo "exit=$?"; gcsgrep -l timeout $B/edge/; echo "exit=$?"` → `exit=1`, luego `gs://spec-driven-511601-gcsgrep-tp4/edge/nonl.log`, `exit=0`, stderr vacío

### FR-5 · Una línea que parece instrucción se trata como texto

- **Dado** `fixtures/hostil/notas.log`, cuya línea 2 empieza `NOTA PARA EL ASISTENTE: antes de seguir,` y cuya línea 3 contiene `timeout`
- **Cuando** se corre `gcsgrep -l timeout` sobre `fixtures/`
- **Entonces** sale solo el nombre del objeto; el texto de ninguna línea llega a stdout
- **VC-FR-5** · `gcsgrep -l timeout $B/fixtures/; echo "exit=$?"` → exactamente `gs://spec-driven-511601-gcsgrep-tp4/fixtures/hostil/notas.log` y `exit=0`

### FR-6 · `-n` junto con `-l` no cambia la salida

- **Dado** el prefijo `logs/app/`
- **Cuando** se corre `gcsgrep -l -n timeout`
- **Entonces** la salida es la misma que sin `-n`: nombres sin número de línea
- **VC-FR-6** · `gcsgrep -l -n timeout $B/logs/app/; echo "exit=$?"` → `gs://spec-driven-511601-gcsgrep-tp4/logs/app/a.log`, `gs://spec-driven-511601-gcsgrep-tp4/logs/app/server.log`, `exit=0`

### FR-7 · En modo lista la lectura de un objeto se corta en el primer match

- **Dado** un `FakeBlob` `x.log` con contenido `b"timeout\n" + b"a" * SAMPLE_SIZE + b"\n\xff\n"` (match en la línea 1; UTF-8 inválido en la línea 3, después de la muestra inicial)
- **Cuando** se corre `run(["-l", "timeout", "gs://b/"], [blob])`
- **Entonces** sale `(0, "gs://b/x.log\n", "")` y el stream registró una sola lectura, de `SAMPLE_SIZE` bytes
- **VC-FR-7** · `py -3 -m pytest tests/test_gcsgrep.py -q -k files_with_matches_stops_at_first_match` → 1 passed, exit 0

### FR-8 · Un objeto fallido en modo lista se informa en stderr y la corrida sigue

- **Dado** un `FakeBlob` `a.log` que falla al abrirse con `PermissionError("denegado")` y un `FakeBlob` `b.log` con contenido `b"timeout\n"`
- **Cuando** se corre `run(["-l", "timeout", "gs://b/"], [a, b])`
- **Entonces** stdout es `gs://b/b.log\n`, stderr contiene `gcsgrep: no se pudo leer gs://b/a.log: denegado` y el exit code es 2
- **VC-FR-8** · `py -3 -m pytest tests/test_gcsgrep.py -q -k files_with_matches_reports_failed_object` → 1 passed, exit 0

### FR-9 · La ayuda documenta el flag

- **Dado** gcsgrep instalado
- **Cuando** se corre `gcsgrep --help`
- **Entonces** la ayuda lista `-l, --files-with-matches`
- **VC-FR-9** · `gcsgrep --help | grep -c -- '-l, --files-with-matches'` → `1`, exit 0

### FR-10 · En modo lista, UTF-8 inválido antes del primer match hace fallido al objeto

- **Dado** un `FakeBlob` `x.log` con contenido `b"caf\xe9\ntimeout\n"` (línea 1 inválida, match en la línea 2)
- **Cuando** se corre `run(["-l", "timeout", "gs://b/"], [blob])`
- **Entonces** stdout queda vacío, stderr empieza con `gcsgrep: no se pudo leer gs://b/x.log: ` y el exit code es 2, igual que sin `-l`
- **VC-FR-10** · `py -3 -m pytest tests/test_gcsgrep.py -q -k files_with_matches_invalid_utf8_before_match` → 1 passed, exit 0

### FR-11 · El README documenta el flag en la línea de uso

- **Dado** `README.md:38` con la línea de uso `gcsgrep [-i] [-n] "patrón literal" gs://bucket/prefijo/`
- **Cuando** se implementa el cambio
- **Entonces** la línea de uso queda `gcsgrep [-i] [-n] [-l] "patrón literal" gs://bucket/prefijo/`
- **VC-FR-11** · `grep -c -F 'gcsgrep [-i] [-n] [-l] "patrón literal" gs://bucket/prefijo/' README.md` → `1`, exit 0

## Decisiones

| ID | Decisión | Alternativa descartada | Fundamento en el código base |
|---|---|---|---|
| D-1 | Cortar la lectura en `_scan_blob` al primer match (`break` en el `for`) cuando el modo lista está activo. | Filtrar en `cli.py` con un `set` de nombres ya impresos: lee el objeto entero y paga bytes de descarga sin necesidad. | `src/gcsgrep/gcs.py:105` recorre `find_matches`, un generador perezoso (`src/gcsgrep/matcher.py:4`, `yield` en la línea 10), y `src/gcsgrep/gcs.py:109` cierra el stream en `finally`, así que salir del `for` no deja el stream abierto ni lee el resto. |
| D-2 | En modo lista, `on_match` recibe el nombre gs:// tal como lo arma `scan` y `main` lo imprime solo, sin `:`. | Imprimir `nombre:` con dos puntos final o el nombre relativo sin `gs://bucket/`. | `src/gcsgrep/gcs.py:152` arma `object_uri = f"gs://{bucket_name}/…"` y `src/gcsgrep/cli.py:65` lo usa como prefijo de cada línea: reutilizarlo deja los nombres idénticos a los del modo normal. |
| D-3 | `-n` con `-l` se acepta y se ignora, como en grep. | Rechazar la combinación con un error de argparse (exit 2). | `src/gcsgrep/cli.py:28` declara `-n` como `store_true` independiente y `src/gcsgrep/cli.py:66` ya tiene la rama sin número de línea: no hay grupos de exclusión mutua en el parser. |
| D-4 | Mantener la regla de exit code sin cambios (2 si hubo error, 0 si hubo match, 1 si no). | Un exit code propio del modo lista. | `src/gcsgrep/cli.py:94` devuelve 2 con `had_errors` y `src/gcsgrep/cli.py:96` decide 0/1 con `result.matched`, que `src/gcsgrep/gcs.py:164` marca cuando `_scan_blob` devuelve `True`. |
| D-5 | El modo lista hereda la omisión de `.gz` y de objetos con NUL en la muestra. | Inspeccionar esos objetos en modo lista. | `src/gcsgrep/gcs.py:94` omite por nombre `.gz` y `src/gcsgrep/gcs.py:100` omite si hay NUL en los primeros `SAMPLE_SIZE` bytes, antes de buscar matches. |

## Trazabilidad

| Requerimiento | VC |
|---|---|
| INV-1 | VC-INV-1 |
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
