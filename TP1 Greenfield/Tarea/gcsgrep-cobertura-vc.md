# gcsgrep — tabla de cobertura de VCs

> Esta tabla se actualiza con la evidencia de cada verificación. Los tests
> automatizados no requieren credenciales reales; los VCs de integración deben
> ejecutarse contra un bucket de prueba antes de la entrega final.

## Resumen inicial

| | |
|---|---:|
| Requerimientos en la spec | 16 |
| VCs definidos | 16 |
| VCs automatizados en Iteración 1 | 9 |
| VCs de integración pendientes | 7 |
| VCs pasando al momento de escribir | Pendiente de ejecutar |
| Requerimientos sin VC | 0 |

## Cobertura

| VC | Requerimiento | Ejercitado por | Se observa | Estado |
|---|---|---|---|---|
| VC-1 | FR-1 URI válida/inválida | `tests/test_gcsgrep.py::test_parse_gs_uri*` | Parseo correcto y error para URI sin `gs://` | ✅ |
| VC-2 | FR-2 prefijo | `tests/test_gcsgrep.py::test_scan_finds_literal_matches_and_line_numbers` | Se consulta el prefijo y solo se recorren objetos incluidos | ✅ |
| VC-3 | FR-3 streaming | `tests/test_gcsgrep.py::test_scan_finds_literal_matches_and_line_numbers` | El scanner consume un stream y encuentra la línea | ✅ |
| VC-4 | FR-4 objeto y línea | `tests/test_gcsgrep.py::test_cli_formats_match_and_returns_zero` | URI, línea 2 y contenido en stdout | ✅ |
| VC-5 | FR-5 `-i` | `tests/test_gcsgrep.py::test_scan_ignore_case_and_skip_binary_and_gzip` | `TIMEOUT` coincide con patrón `timeout` | ✅ |
| VC-6 | FR-6 error parcial | `tests/test_gcsgrep.py::test_scan_continues_after_object_error` | El segundo objeto se procesa y el error se registra | ✅ |
| VC-7 | FR-7 sin matches | `tests/test_gcsgrep.py::test_cli_exit_code_one_when_no_match` | Exit `1` y stdout vacío | ✅ |
| VC-8 | FR-8 progreso | Test con 100 objetos | Mensaje de progreso en stderr | Pendiente |
| VC-9 | BR-1 solo lectura | Integración contra bucket de prueba | Metadatos y contenido sin cambios | Pendiente |
| VC-10 | BR-2 permisos | Ejecución sin permiso de lectura | Exit `2`, sin contenido protegido | Pendiente |
| VC-11 | BR-3 límites | `tests/test_gcsgrep.py::test_cli_returns_two_when_object_limit_is_reached` | Se detiene y devuelve `2` | ✅ |
| VC-12 | BR-4 binarios y `.gz` | `tests/test_gcsgrep.py::test_scan_ignore_case_and_skip_binary_and_gzip` | No hay basura binaria y el texto siguiente sí se procesa | ✅ |
| VC-13 | BR-5 generación | Integración con objeto reemplazado | Se informa error de generación y continúa | Iteración 2 |
| VC-14 | NFR-1 memoria | Benchmark con objeto de 128 MiB | Pico menor a 64 MiB | Iteración 2 |
| VC-15 | NFR-2 reintentos | Test de stream transitorio | Recuperación tras hasta 3 intentos | Iteración 2 |
| VC-16 | NFR-3 scripting | Tests de CLI y errores de integración | Resultados en stdout, errores en stderr, sin traceback | Parcial |

## Comando de verificación automatizada

```bash
pytest -q
```

Antes de entregar hay que reemplazar los estados `Pendiente`, `Parcial` e
`Iteración 2` por evidencia ejecutada o explicar formalmente que esos VCs quedan
fuera de la Iteración 1 y son parte del alcance diferido.
