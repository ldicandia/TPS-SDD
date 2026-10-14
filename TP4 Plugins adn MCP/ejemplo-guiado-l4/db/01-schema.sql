-- turnos-api — schema mínimo para el ejemplo guiado de la Lección 4.
--
-- Es el schema que decidió ADR-0001 (examples/03-skills/ejemplo-guiado/docs/adr/):
-- la doble reserva la impide la base, con UNIQUE (profesional_id, inicio).
-- Fijate qué índices hay y cuáles no: es lo que el agente va a descubrir por MCP.

CREATE TABLE profesionales (
  id            bigserial PRIMARY KEY,
  nombre        text NOT NULL,
  especialidad  text NOT NULL
);

CREATE TABLE pacientes (
  id         bigserial PRIMARY KEY,
  nombre     text NOT NULL,
  creado_en  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE turnos (
  id                  bigserial PRIMARY KEY,
  profesional_id      bigint NOT NULL REFERENCES profesionales (id),
  paciente_id         bigint NOT NULL REFERENCES pacientes (id) ON DELETE RESTRICT,
  inicio              timestamptz NOT NULL,
  estado              text NOT NULL DEFAULT 'reservado'
                        CHECK (estado IN ('reservado', 'cancelado', 'atendido')),
  datos_especialidad  jsonb NOT NULL DEFAULT '{}',
  CONSTRAINT turnos_profesional_inicio_key UNIQUE (profesional_id, inicio)
);

-- Lo que escribe el paciente al reservar ("llego 10 minutos tarde", "traigo estudios").
-- Es texto que viene de afuera: para la base es un string; para un agente que lo lee,
-- puede parecer una instrucción (Lección 4, "Un objeto que da órdenes").
CREATE TABLE comentarios_turno (
  id         bigserial PRIMARY KEY,
  turno_id   bigint NOT NULL REFERENCES turnos (id) ON DELETE CASCADE,
  texto      text NOT NULL,
  creado_en  timestamptz NOT NULL DEFAULT now()
);
