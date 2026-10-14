#!/usr/bin/env bash
# 03-rol-lector.sh — la credencial que usa el server MCP.
#
# turnos_lector solo puede leer: SELECT sobre las tablas, nada más, y sus
# transacciones son de solo lectura por defecto. Este rol es el techo de lo que
# el agente puede hacer, aunque el server corriera sin --access-mode=restricted.
#
# La contraseña viene del entorno (LECTOR_PASSWORD), no de este archivo.
set -euo pipefail

psql -v ON_ERROR_STOP=1 -v pass="$LECTOR_PASSWORD" \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE ROLE turnos_lector LOGIN PASSWORD :'pass';
GRANT CONNECT ON DATABASE turnos TO turnos_lector;
GRANT USAGE ON SCHEMA public TO turnos_lector;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO turnos_lector;
ALTER ROLE turnos_lector SET default_transaction_read_only = on;
SQL
