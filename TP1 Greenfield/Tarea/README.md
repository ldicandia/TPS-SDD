# gcsgrep

CLI de la Iteración 1 para buscar texto dentro de objetos de Google Cloud Storage
sin descargarlos previamente a disco.

## Instalación

Se requiere Python 3.10 o superior:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e . pytest
```

La autenticación usa Application Default Credentials:

```bash
gcloud auth application-default login
```

No se deben guardar credenciales ni archivos de service account en el repositorio.

## Uso

```bash
gcsgrep [-i] [-n] "patrón literal" gs://bucket/prefijo/
```

Ejemplo:

```bash
gcsgrep -i -n "timeout" gs://logs/app/
```

La salida tiene formato:

```text
gs://logs/app/server.log:42:request timeout
```

La v1 procesa objetos secuencialmente, lee por streaming, saltea `.gz` y objetos
binarios, y aplica por defecto un límite de 1.000 objetos o 1 GiB.

## Exit codes

| Código | Significado |
|---:|---|
| 0 | Se encontró al menos una coincidencia. |
| 1 | La búsqueda terminó sin coincidencias. |
| 2 | Ocurrió un error o se alcanzó un límite de seguridad. |

## Tests

```bash
pytest -q
```

Los tests unitarios (`tests/test_gcsgrep.py`) usan un cliente falso y no
requieren acceso a GCP. Los tests de integración (`tests/integration/`) ejecutan
el CLI real contra la API de GCS y se saltean si no hay un emulador o entorno
configurado.

### Verificación de integración con Floci (sin cuenta de GCP)

[Floci](https://floci.io/gcp/) emula la API de GCS en `localhost:4588`. Requiere
Docker; el `docker-compose.yml` del proyecto lo levanta:

```bash
docker compose up -d --wait
export STORAGE_EMULATOR_HOST=http://localhost:4588
export GOOGLE_CLOUD_PROJECT=floci-local
pytest -q          # 25 passed
docker compose down
```

En PowerShell las variables se definen con
`$env:STORAGE_EMULATOR_HOST = "http://localhost:4588"` y
`$env:GOOGLE_CLOUD_PROJECT = "floci-local"`.

No hace falta ningún cambio en `gcsgrep`: el cliente oficial detecta
`STORAGE_EMULATOR_HOST` y usa credenciales anónimas. Los tests crean un bucket
efímero `gcsgrep-it-<uuid>`, lo siembran con objetos de prueba y lo borran al
terminar. El estado del emulador es en memoria: `docker compose down` lo
descarta por completo.

### Verificación contra GCP real

Con ADC configurado y un proyecto activo:

```bash
GCSGREP_INTEGRATION=1 pytest -q tests/integration
```

La suite crea y borra un bucket de prueba en el proyecto por defecto de ADC. La
evidencia de cada corrida se registra en `gcsgrep-cobertura-vc.md`.
