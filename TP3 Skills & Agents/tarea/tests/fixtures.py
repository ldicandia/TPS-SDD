"""Spec válida mínima que usan las regresiones del checker y del hook.

Está acá y no en `tarea/evidencia/specs/` a propósito: la spec de evidencia es la
salida de una sesión de Claude y se regenera cada vez que se vuelve a correr el
flujo. Si los tests mutan ese archivo, una corrida nueva los rompe sin que haya
cambiado ninguna pieza del toolkit — que es exactamente lo que pasó cuando la
sesión del 2026-10-08 produjo una spec sin NFR.

El fixture cubre un FR, un INV, un NFR y una decisión, que es lo que las mutaciones
necesitan. Que la spec entregada siga pasando el checker se comprueba aparte, en
`test_check_spec.CheckSpecTests.test_delivered_spec_passes`.
"""

SPEC_VALIDA = """# Spec — flag `-c` / `--count` en `gcsgrep`

**Base:** `gcsgrep` @ `b28ad1f38606bfdaf7e9059c92411c97eaf99e77` · **Fecha:** 2026-10-07

## Propósito

Quien busca un patrón en un bucket puede saber cuántas líneas coinciden en cada
objeto sin recibir las líneas.

## Términos

| Término | Significa |
|---|---|
| línea coincidente | Línea de un objeto que contiene el patrón. Una línea que lo contiene tres veces sigue siendo una sola línea coincidente. |
| conteo | Cantidad de líneas coincidentes de un objeto. |

## Alcance

### Dentro

| Archivo / módulo | Qué cambia |
|---|---|
| `src/gcsgrep/cli.py` | `build_parser` agrega `-c`/`--count`; en modo conteo `main` imprime `gs://bucket/objeto:N`. |
| `src/gcsgrep/gcs.py` | `_scan_blob` devuelve el conteo en lugar de un booleano. |

### Fuera

| Qué queda afuera | Por qué |
|---|---|
| Contar apariciones en lugar de líneas | El matcher decide por línea (`src/gcsgrep/matcher.py:9`). |
| Imprimir objetos con conteo 0 | Rompería "sin coincidencias, stdout vacío" (D-1). |

## Invariantes

### INV-1 · La suite unitaria existente sigue verde

Los tests de `tests/test_gcsgrep.py` en la base pasan sin modificarlos.

- **VC-INV-1** · `python -m pytest -q tests/test_gcsgrep.py` → ningún `failed`, exit 0

## Requerimientos

### FR-1 · `-c` imprime el conteo de cada objeto en lugar de las líneas

- **Dado** el objeto `app/a.log` = `timeout timeout\\nok\\ntimeout\\n` y el objeto `app/b.log` = `connection timeout\\n`
- **Cuando** se ejecuta `gcsgrep -c timeout gs://B/app/`
- **Entonces** stdout tiene una línea `gs://B/app/<objeto>:<conteo>` por objeto, sin ninguna línea del contenido; exit 0
- **VC-FR-1** · `run(["-c", "timeout", "gs://B/app/"], [FakeBlob("app/a.log", b"timeout timeout\\nok\\ntimeout\\n"), FakeBlob("app/b.log", b"connection timeout\\n")])` → stdout `gs://B/app/a.log:2\\ngs://B/app/b.log:1\\n`, stderr vacío, exit 0

### NFR-1 · El modo conteo lee por streaming, igual que la base

- **Métrica** Tamaños solicitados al stream (`blob.stream.read_sizes`) y archivos locales creados.
- **Umbral** Cada lectura solicita como máximo 65.536 bytes y se crean 0 archivos locales.
- **Carga** Un objeto de más de 73.728 bytes con 3 líneas, 2 de ellas coincidentes.

- **VC-NFR-1** · `run(["-c", "timeout", "gs://logs/"], [blob])` con `open` parcheado para fallar → cada tamaño en `(0, 65536]`, exit 0

## Decisiones

| ID | Decisión | Alternativa descartada | Fundamento en el código base |
|---|---|---|---|
| D-1 | No imprimir objetos con conteo 0 | Imprimir `uri:0` como `grep -c` | `src/gcsgrep/cli.py:96` fija que sin coincidencias stdout queda vacío con exit 1 |

## Trazabilidad

| Requerimiento | VC |
|---|---|
| INV-1 | VC-INV-1 |
| FR-1 | VC-FR-1 |
| NFR-1 | VC-NFR-1 |
"""
