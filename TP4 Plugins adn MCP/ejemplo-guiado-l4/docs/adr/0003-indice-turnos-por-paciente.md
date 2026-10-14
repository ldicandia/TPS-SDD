# ADR-0003: Indexar los turnos por paciente

Estado: Propuesto
Fecha: 2026-10-02

## Contexto
La pantalla "Mis turnos" lista los turnos de un paciente, del más nuevo al más viejo.
Hoy `turnos` tiene 172.000 filas y crece unos 800 turnos por día hábil. ADR-0001 dejó
la unicidad de la reserva en la base, con un índice sobre `(profesional_id, inicio)`;
ese índice sirve para reservar, no para buscar por paciente.

## Evidencia de la base

Leída en vivo el 2026-10-02 vía MCP: server `postgres-mcp` 0.3.0 en modo
restringido, rol `turnos_lector`.

| Qué | Tool | Lo que devolvió |
|---|---|---|
| Índices de `turnos` | `get_object_details` | `turnos_pkey (id)` y `turnos_profesional_inicio_key (profesional_id, inicio)`. Ninguno empieza por `paciente_id` |
| Plan de `SELECT * FROM turnos WHERE paciente_id = 4242 ORDER BY inicio DESC` | `explain_query` | `Sort` sobre `Seq Scan on turnos`, costo 0.00..3758.00, 9 filas estimadas |
| Huella de `turnos` | `execute_sql` | índices `b1c72a87d8a0c7af526b21da8342ceae`, 172.000 filas estimadas |

Si al aceptar o aplicar esta decisión la huella no coincide, el ADR vuelve a
"Propuesto" y se relee la base.

Para devolver 9 filas, la base recorre la tabla entera. El costo crece con la tabla,
no con los turnos del paciente.

## Opciones consideradas
1. **Índice sobre `(paciente_id, inicio)`** — a favor: la búsqueda deja de recorrer la
   tabla, y el índice ya viene ordenado por fecha. · en contra: cada reserva escribe
   un índice más; ocupa espacio.
2. **Índice solo sobre `paciente_id`** — a favor: más chico. · en contra: el orden por
   `inicio` queda a cargo de un `Sort`; para pacientes con muchos turnos, se nota.
3. **No indexar y cachear "Mis turnos" en la aplicación** — a favor: sin migración. · en
   contra: hay que invalidar la caché en cada reserva y cancelación, y la base sigue
   recorriendo la tabla cuando la caché falla.

## Decisión
Agregamos un índice btree sobre `turnos (paciente_id, inicio)`, con una migración en
`migrations/` que se revisa en el MR. El agente no la ejecuta.

## Consecuencias
- Cada reserva escribe en un índice más.
- La migración usa `CREATE INDEX CONCURRENTLY`, para no bloquear las reservas mientras
  se construye.
- Después de aplicarla, `explain_query` sobre la misma query tiene que mostrar un scan
  por `turnos_paciente_inicio_idx` en vez del `Seq Scan`. Si no, la decisión no logró
  lo que prometía.
