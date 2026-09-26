# gcsgrep — plan de iteraciones

> Plan construido a partir de [`gcsgrep-spec.md`](./gcsgrep-spec.md). Cada
> iteración termina con código ejecutable y sus VCs pasando antes de ampliar el
> alcance.

## Orden

| Iteración | Entrega | VCs principales |
|---|---|---|
| 1 | Búsqueda literal secuencial sobre texto UTF-8 | VC-1 a VC-12 y VC-16 a VC-27 (verificados contra el emulador Floci) |
| 2 | Robustez operativa y escalabilidad controlada | VC-13, VC-14, VC-15 y VC-28; VC-8 con progreso configurable |
| 3 | Funcionalidades de grep diferidas | Regex, JSON, filtros y conteos; fuera de la entrega mínima |

## Iteración 1 — Búsqueda literal de punta a punta

### Alcance

- CLI `gcsgrep PATTERN gs://bucket/prefijo`.
- Validación estricta del URI `gs://`.
- Application Default Credentials mediante el cliente oficial de GCS.
- Enumeración secuencial de objetos.
- Lectura incremental por streaming.
- Búsqueda literal UTF-8.
- Flags `-i` y `-n`.
- Salida `objeto:línea:contenido`.
- Salteo de `.gz` y objetos con byte NUL inicial.
- Límites predeterminados de 1.000 objetos y 1 GiB.
- Exit codes `0`, `1` y `2`.
- Errores de un objeto informados sin abortar el resto.

### Fuera de alcance

- Concurrencia configurable.
- Regex.
- JSON, colores, `-l`, `-c` y `--include`.
- Reintentos avanzados y medición de memoria de objetos grandes.

### Criterios de éxito

- [x] La búsqueda encuentra coincidencias y muestra el objeto.
- [x] `-n` muestra el número correcto de línea.
- [x] `-i` ignora mayúsculas y minúsculas.
- [x] Una búsqueda sin matches devuelve `1`.
- [x] Los errores de objetos se informan y permiten continuar.
- [x] Los límites detienen el escaneo con código `2`.
- [x] No se realizan operaciones de escritura en GCS.
- [x] Los tests unitarios y de CLI pasan (11 unitarios + 15 de integración contra el emulador Floci; ver `gcsgrep-cobertura-vc.md`).

### Demostración

```bash
gcsgrep -i -n "timeout" gs://logs/app/
echo $?
```

## Iteración 2 — Robustez y escalabilidad

### Alcance

- Reintentos explícitos para fallos transitorios, según NFR-2 (3 reintentos con esperas de 1 s, 2 s y 4 s).
- Lectura concurrente con `--jobs`, manteniendo límites globales.
- Progreso configurable.
- Verificación de generación del objeto cuando esté disponible.
- Benchmark sobre objetos grandes para comprobar memoria y rendimiento.
- Corrida de la suite `tests/integration` contra un bucket real de GCP (`GCSGREP_INTEGRATION=1`), incluyendo el caso IAM de VC-10 que el emulador no reproduce.

### Criterios de éxito

- [ ] Los reintentos cumplen NFR-2.
- [ ] La concurrencia no supera los límites de objetos o bytes.
- [ ] El progreso sigue yendo a `stderr`.
- [ ] Todos los VCs de la Iteración 1 siguen pasando.

## Iteración 3 — Alcance diferido

Estas funcionalidades se documentan para evitar que aparezcan accidentalmente
durante la Iteración 1:

- `-E` para expresiones regulares.
- `-l` para imprimir solamente nombres de objetos.
- `-c` para contar coincidencias.
- `--include` para filtrar nombres de objetos.
- `--json` para consumidores de máquina.
- Descompresión de `.gz` al vuelo.
- Colores y otras opciones visuales.

## Riesgos aceptados

- No existe una snapshot global del bucket.
- Un bucket grande puede cambiar mientras se ejecuta el listado.
- La primera versión procesa objetos secuencialmente.
- Los metadatos de tipo de contenido no se consideran suficientes para detectar
  binarios.
