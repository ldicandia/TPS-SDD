# taskcli — tabla de cobertura de VCs

> Salida del paso **Verificar**. Esto es lo que se muestra en una presentación
> cuando alguien pregunta "¿cómo sabés que está terminado?".
>
> La tabla no dice "lo probé". Dice, para cada criterio de verificación, **con qué
> se lo ejercita y qué se observó**. Un VC sin evidencia es un VC que no pasó.

## Resumen

| | |
|---|---|
| Requerimientos (FR + BR + NFR) | 15 |
| VCs definidos | 15 |
| VCs con cobertura ejecutable | 15 |
| VCs pasando | 15 |
| **Requerimientos sin VC** | **0** |

## Cobertura, uno por uno

| VC | Requerimiento | Ejercitado por | Se observa | Estado |
|---|---|---|---|---|
| VC-1 | FR-1 agregar | `test_add.py::test_agrega_sobre_store_vacio` | exit `0`, ID impreso, 1 tarea pendiente en el store | ✅ |
| VC-2 | FR-2 listar | `test_list.py::test_lista_en_orden_por_id` | exit `0`, 3 líneas en orden 1·2·3, la 2 marcada distinto | ✅ |
| VC-3 | FR-3 duplicados | `test_add.py::test_rechaza_duplicado_pendiente` | exit `1`, `duplicate` en stderr, conteo sin cambios | ✅ |
| VC-4 | FR-4 completar | `test_done.py::test_completa_pendiente` | exit `0`, estado `completada` persistido | ✅ |
| VC-5 | FR-5 ID inexistente | `test_done.py::test_rechaza_id_inexistente` | exit `1`, `not found` en stderr, archivo byte a byte igual | ✅ |
| VC-6 | FR-6 store vacío | `test_list.py::test_lista_vacia_no_es_error` | exit `0`, mensaje de lista vacía en stdout | ✅ |
| VC-7 | FR-7 primer uso | `test_store.py::test_crea_store_en_primer_uso` | exit `0`, archivo creado, JSON válido de store vacío | ✅ |
| VC-8 | FR-8 store corrupto | `test_store.py::test_no_sobrescribe_store_corrupto` | exit `2`, contenido original preservado | ✅ |
| VC-9 | BR-1 longitud título | `test_add.py::test_limites_de_titulo` (paramétrico: `""`, `"   "`, 200, 201) | exit `1`/`0`/`1` según corresponde, store intacto en las fallas | ✅ |
| VC-10 | BR-2 unicidad | `test_add.py::test_permite_reagregar_titulo_completado` | exit `0`, 2 tareas con el mismo título y estados distintos | ✅ |
| VC-11 | BR-3 IDs no se reusan | `test_core.py::test_ids_no_se_reusan` | tras borrar la 3 a mano, la siguiente recibe el `4` | ✅ |
| VC-12 | BR-4 falla deja intacto | `test_integridad.py::test_hash_invariante_en_fallas` (paramétrico sobre los 4 casos de falla) | hash SHA-256 idéntico antes y después en los 4 casos | ✅ |
| VC-13 | NFR-1 latencia | `bench_list.py` — 10 corridas sobre store de 10.000 | mediana **41 ms** (umbral: < 100 ms) | ✅ |
| VC-14 | NFR-2 cota de tamaño | `test_carga.py::test_diez_mil_tareas` | `add`, `list`, `done` completan y respetan sus VCs | ✅ |
| VC-15 | NFR-3 scripting | `test_salida.py::test_errores_van_a_stderr` (paramétrico sobre los casos de falla) | stdout vacío, stderr no vacío, sin `Traceback` ni rutas de fuente | ✅ |

## Cómo se ejercita todo

```bash
pytest -q                       # los 15 VCs funcionales
python bench_list.py            # VC-13, imprime la mediana medida
```

## Qué mirar en esta tabla

Tres cosas, y son las mismas que se corrigen en la presentación:

1. **Cada fila tiene un ejercitador nombrado.** No dice "verificado manualmente";
   dice qué correr para reproducirlo.
2. **La columna "Se observa" es observable.** Exit codes, contenido de archivo,
   hashes, milisegundos. No dice "funciona bien".
3. **Hay caminos de falla, no solo el feliz.** De los 15 VCs, 6 ejercitan fallas o
   bordes. Una tabla donde todo es camino feliz es una tabla que no verificó nada.

## Nota sobre VC-13

La mediana medida (41 ms) está cómodamente bajo el umbral de 100 ms, pero el umbral
se escribió **antes** de implementar, en la spec. Ese es el orden que importa: si
el número se hubiera elegido después de medir, no sería un requerimiento, sería una
descripción de lo que salió.
