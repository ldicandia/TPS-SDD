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

Los tests unitarios usan un cliente falso y no requieren acceso a GCP. La
verificación de integración contra un bucket real se documenta en
`gcsgrep-cobertura-vc.md`.
