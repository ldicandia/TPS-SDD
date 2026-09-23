# Entrega TP1 — `gcsgrep`

## Integrantes

| Nombre |
|---|
| Lucas Di Candia |
| Timoteo Feeney |
| Matias Sapino |

## Artefactos entregados

Todo vive en [`TP1 Greenfield/Tarea/`](<TP1 Greenfield/Tarea/>).

| Artefacto | Archivo | Contenido |
|---|---|---|
| Base context refinado | [`gcsgrep-base-context.md`](<TP1 Greenfield/Tarea/gcsgrep-base-context.md>) | Borrador del enunciado con las preguntas abiertas resueltas y justificadas |
| Spec revisada | [`gcsgrep-spec.md`](<TP1 Greenfield/Tarea/gcsgrep-spec.md>) | 8 FRs, 5 BRs y 3 NFRs con umbrales; 16 VCs y trazabilidad completa; sin preguntas abiertas |
| Plan | [`gcsgrep-plan.md`](<TP1 Greenfield/Tarea/gcsgrep-plan.md>) | 3 iteraciones; el alcance diferido (regex, `-l`, `-c`, JSON, `.gz`, concurrencia) vive acá |
| Código de la Iteración 1 | [`src/gcsgrep/`](<TP1 Greenfield/Tarea/src/gcsgrep/>) | CLI con búsqueda literal, `-i`, `-n`, streaming, solo lectura y exit codes estilo `grep` |
| Tests | [`tests/`](<TP1 Greenfield/Tarea/tests/>) | 11 tests unitarios con cliente falso y 15 tests de integración contra la API de GCS |
| Cobertura de VCs | [`gcsgrep-cobertura-vc.md`](<TP1 Greenfield/Tarea/gcsgrep-cobertura-vc.md>) | Evidencia por VC: 13 pasando (VC-1 a VC-12 y VC-16) y 3 diferidos a la Iteración 2 |

## Decisiones principales

- **Búsqueda:** literal sobre texto UTF-8; regex queda para la Iteración 3.
- **Auth:** Application Default Credentials a través del cliente oficial de GCS.
- **Direccionamiento:** `gs://bucket/prefijo`, validado estrictamente.
- **Flags:** `-i` y `-n`.
- **Binarios y `.gz`:** se saltean; la descompresión al vuelo queda para la Iteración 3.
- **Guardrails de costo:** por defecto se escanean como máximo 1.000 objetos o 1 GiB; al alcanzar el límite el escaneo se corta con exit `2`.
- **Solo lectura:** la herramienta no realiza ninguna escritura en GCS.

El detalle y la justificación de cada decisión están en el base context y en la spec.

## Cómo verificar

Desde `TP1 Greenfield/Tarea/`, con Python 3.10 o superior. Verificado en Windows
(PowerShell) y en WSL (Ubuntu 24.04); los comandos para Windows están en el
[README](<TP1 Greenfield/Tarea/README.md>).

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e . pytest
pytest -q                      # 11 passed, 15 skipped
```

Con el emulador de GCS [Floci](https://floci.io/gcp/) (requiere Docker, sin cuenta de GCP):

```bash
docker compose up -d --wait
export STORAGE_EMULATOR_HOST=http://localhost:4588
export GOOGLE_CLOUD_PROJECT=floci-local
pytest -q                      # 26 passed
docker compose down
```

Contra un bucket real de GCP, con ADC configurado:

```bash
GCSGREP_INTEGRATION=1 pytest -q tests/integration
```

## Estado

- **Iteración 1:** completa. Todos los criterios de éxito del plan están cumplidos.
- **Iteración 2:** pendiente. Incluye reintentos (VC-15), memoria con objetos grandes (VC-14), verificación de generación (VC-13), concurrencia y una corrida contra GCP real con el caso de IAM de VC-10.
- **Iteración 3:** alcance diferido, documentado en el plan.
