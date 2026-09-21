"""Verificación de integración contra un emulador de GCS (Floci) o un bucket real.

Estos tests ejercitan el CLI real (``python -m gcsgrep``) contra objetos servidos
por la API de GCS. Se saltean si no hay ``STORAGE_EMULATOR_HOST`` definido, así
``pytest -q`` sigue funcionando sin infraestructura.

Uso con Floci:

    docker run -d --name floci-gcp -p 4588:4588 floci/floci-gcp:latest
    export STORAGE_EMULATOR_HOST=http://localhost:4588
    export GOOGLE_CLOUD_PROJECT=floci-local
    pytest -q tests/integration

Contra GCP real (ADC configurado; crea y borra un bucket en el proyecto activo):

    GCSGREP_INTEGRATION=1 pytest -q tests/integration
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from dataclasses import dataclass

import pytest

pytestmark = pytest.mark.skipif(
    not (os.environ.get("STORAGE_EMULATOR_HOST") or os.environ.get("GCSGREP_INTEGRATION")),
    reason="requiere STORAGE_EMULATOR_HOST (emulador) o GCSGREP_INTEGRATION=1 (GCP real)",
)

# Objetos sembrados en el bucket de prueba. Las claves son nombres de objeto.
SEED_OBJECTS: dict[str, bytes] = {
    # Prefijo principal: mezcla de texto con y sin match, binario y .gz.
    "app/server.log": b"healthy\nRequest Timeout\nfinished\nconnection timeout after 30s\n",
    "app/errors.log": b"TIMEOUT\nok\n",
    "app/clean.log": b"nothing here\n",
    "app/archive.gz": b"timeout inside gz\n",
    "app/blob.bin": b"timeout\x00\xff\x00binary",
    # Fuera del prefijo app/: no debe ser visitado por gs://bucket/app/.
    "other/notes.txt": b"timeout outside prefix\n",
    # Prefijo con un objeto ilegible (UTF-8 inválido) seguido de uno legible.
    "broken/latin1.log": b"caf\xe9 timeout\n",
    "broken/ok.log": b"timeout here\n",
}
# Prefijo con 100 objetos para el aviso de progreso (FR-8).
SEED_OBJECTS.update({f"many/obj-{i:03d}.txt": b"filler\n" for i in range(100)})


@dataclass(frozen=True)
class ObjectSnapshot:
    name: str
    size: int
    md5_hash: str | None
    generation: int | None


@dataclass
class SeededBucket:
    name: str
    snapshot: list[ObjectSnapshot]

    def uri(self, prefix: str = "") -> str:
        return f"gs://{self.name}/{prefix}"


@dataclass
class CliRun:
    code: int
    stdout: str
    stderr: str

    @property
    def stdout_lines(self) -> list[str]:
        return self.stdout.splitlines()


def _snapshot(bucket) -> list[ObjectSnapshot]:
    return sorted(
        (
            ObjectSnapshot(blob.name, blob.size, blob.md5_hash, blob.generation)
            for blob in bucket.list_blobs()
        ),
        key=lambda item: item.name,
    )


@pytest.fixture(scope="module")
def seeded_bucket():
    from google.cloud import storage

    client = storage.Client()
    bucket = client.create_bucket(f"gcsgrep-it-{uuid.uuid4().hex[:8]}")
    for name, content in SEED_OBJECTS.items():
        bucket.blob(name).upload_from_string(content, content_type="application/octet-stream")

    yield SeededBucket(bucket.name, _snapshot(bucket))

    for blob in bucket.list_blobs():
        blob.delete()
    bucket.delete()


def run_cli(*args: str, env_overrides: dict[str, str | None] | None = None) -> CliRun:
    """Ejecuta ``python -m gcsgrep`` como proceso separado, igual que lo haría un usuario."""
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    for key, value in (env_overrides or {}).items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    completed = subprocess.run(
        [sys.executable, "-m", "gcsgrep", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    return CliRun(completed.returncode, completed.stdout, completed.stderr)


def assert_no_traceback(run: CliRun) -> None:
    assert "Traceback" not in run.stderr, run.stderr
    assert "Traceback" not in run.stdout, run.stdout


# --- VC-1 / FR-1: ubicación --------------------------------------------------


def test_vc1_invalid_uri_exits_two_with_message(seeded_bucket):
    run = run_cli("timeout", f"{seeded_bucket.name}/app/")
    assert run.code == 2
    assert run.stdout == ""
    assert "gs://" in run.stderr
    assert_no_traceback(run)


def test_vc1_missing_bucket_exits_two(seeded_bucket):
    run = run_cli("timeout", "gs://gcsgrep-no-such-bucket-000/")
    assert run.code == 2
    assert run.stdout == ""
    assert "no se pudo enumerar" in run.stderr
    assert_no_traceback(run)


# --- VC-2 / FR-2: enumeración bajo prefijo -----------------------------------


def test_vc2_only_objects_under_prefix_are_visited(seeded_bucket):
    run = run_cli("timeout", seeded_bucket.uri("app/"))
    assert run.code == 0
    assert run.stdout_lines == [
        f"{seeded_bucket.uri('app/server.log')}:connection timeout after 30s"
    ]
    assert "other/notes.txt" not in run.stdout


def test_vc2_bucket_root_covers_every_prefix(seeded_bucket):
    run = run_cli("timeout outside", seeded_bucket.uri())
    assert run.stdout_lines == [
        f"{seeded_bucket.uri('other/notes.txt')}:timeout outside prefix"
    ]
    # La raíz también incluye broken/latin1.log (ilegible), por eso FR-6 exige 2.
    assert run.code == 2
    assert "broken/latin1.log" in run.stderr


# --- VC-3 / VC-4 / FR-3 / FR-4: streaming, objeto y línea --------------------


def test_vc4_line_numbers_with_n_flag(seeded_bucket):
    run = run_cli("-n", "timeout", seeded_bucket.uri("app/"))
    assert run.code == 0
    assert run.stdout_lines == [
        f"{seeded_bucket.uri('app/server.log')}:4:connection timeout after 30s"
    ]


def test_vc4_no_line_numbers_without_n_flag(seeded_bucket):
    run = run_cli("timeout", seeded_bucket.uri("app/"))
    assert run.code == 0
    assert run.stdout_lines == [
        f"{seeded_bucket.uri('app/server.log')}:connection timeout after 30s"
    ]


# --- VC-5 / FR-5: -i ---------------------------------------------------------


def test_vc5_ignore_case_finds_all_variants(seeded_bucket):
    run = run_cli("-i", "-n", "timeout", seeded_bucket.uri("app/"))
    assert run.code == 0
    assert run.stdout_lines == [
        f"{seeded_bucket.uri('app/errors.log')}:1:TIMEOUT",
        f"{seeded_bucket.uri('app/server.log')}:2:Request Timeout",
        f"{seeded_bucket.uri('app/server.log')}:4:connection timeout after 30s",
    ]


# --- VC-6 / FR-6: continuar ante errores -------------------------------------


def test_vc6_unreadable_object_is_reported_and_scan_continues(seeded_bucket):
    run = run_cli("-n", "timeout", seeded_bucket.uri("broken/"))
    assert run.code == 2
    assert run.stdout_lines == [f"{seeded_bucket.uri('broken/ok.log')}:1:timeout here"]
    assert f"no se pudo leer {seeded_bucket.uri('broken/latin1.log')}" in run.stderr
    assert_no_traceback(run)


# --- VC-7 / FR-7: sin coincidencias ------------------------------------------


def test_vc7_no_match_returns_one_with_empty_stdout(seeded_bucket):
    run = run_cli("no-such-text", seeded_bucket.uri("app/"))
    assert run.code == 1
    assert run.stdout == ""
    assert_no_traceback(run)


# --- VC-8 / FR-8: progreso ---------------------------------------------------


def test_vc8_progress_every_hundred_objects_goes_to_stderr(seeded_bucket):
    run = run_cli("filler", seeded_bucket.uri("many/"))
    assert run.code == 0
    assert len(run.stdout_lines) == 100
    assert "objetos procesados: 100" in run.stderr
    assert "objetos procesados" not in run.stdout


# --- VC-9 / BR-1: solo lectura -----------------------------------------------


def test_vc9_bucket_is_unchanged_after_scans(seeded_bucket):
    from google.cloud import storage

    run_cli("-i", "-n", "timeout", seeded_bucket.uri())
    run_cli("timeout", seeded_bucket.uri("broken/"))
    run_cli("--max-objects", "1", "timeout", seeded_bucket.uri("app/"))

    after = _snapshot(storage.Client().bucket(seeded_bucket.name))
    assert after == seeded_bucket.snapshot


# --- VC-10 / BR-2: credenciales ----------------------------------------------


def test_vc10_without_credentials_fails_with_two(seeded_bucket, tmp_path):
    # Sin emulador y con ADC apuntando a un archivo inexistente no hay credenciales.
    run = run_cli(
        "timeout",
        seeded_bucket.uri("app/"),
        env_overrides={
            "STORAGE_EMULATOR_HOST": None,
            "GOOGLE_APPLICATION_CREDENTIALS": str(tmp_path / "missing.json"),
        },
    )
    assert run.code == 2
    assert run.stdout == ""
    assert "credenciales" in run.stderr
    assert_no_traceback(run)


# --- VC-11 / BR-3: guardrail de costo ----------------------------------------


def test_vc11_max_objects_stops_scan_with_two(seeded_bucket):
    run = run_cli("--max-objects", "2", "timeout", seeded_bucket.uri("app/"))
    assert run.code == 2
    assert "límite de seguridad" in run.stderr
    assert "máximo 2 objetos" in run.stderr
    assert_no_traceback(run)


def test_vc11_max_bytes_stops_scan_with_two(seeded_bucket):
    run = run_cli("--max-bytes", "10", "timeout", seeded_bucket.uri("app/"))
    assert run.code == 2
    assert "máximo 10 bytes" in run.stderr
    assert_no_traceback(run)


# --- VC-12 / BR-4: binarios y .gz --------------------------------------------


def test_vc12_gz_and_binary_objects_are_skipped(seeded_bucket):
    run = run_cli("-i", "timeout", seeded_bucket.uri("app/"))
    assert run.code == 0
    assert "archive.gz" not in run.stdout
    assert "blob.bin" not in run.stdout
    assert "\x00" not in run.stdout
