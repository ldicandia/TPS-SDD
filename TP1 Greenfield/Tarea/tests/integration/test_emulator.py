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
    # Prefijo literal (FR-2): gs://B/logs/ excluye logs-other/, gs://B/logs no.
    "logs/a.log": b"prefixmark\n",
    "logs/b.log": b"prefixmark\n",
    "logs/c.log": b"prefixmark\n",
    "logs-other/d.log": b"prefixmark\n",
    # Bordes de línea y objeto vacío (FR-3).
    "edge/nonl.log": b"a\nb timeout",
    "empty/zero.log": b"",
    # Orden de salida (FR-16): se sube b antes que a a propósito.
    "order/b.log": b"ordmark 1\nx\nordmark 3\n",
    "order/a.log": b"x\nordmark 2\n",
    # Límite de bytes exacto (FR-14): 10 y 20 bytes declarados.
    "bytes/ten.log": b"timeout!!\n",
    "bytes/twenty.log": b"timeout 01234567890\n",
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


# --- VC-1 / FR-1: bucket completo --------------------------------------------


def test_vc1_bucket_root_covers_every_prefix(seeded_bucket):
    without_slash = run_cli("timeout", f"gs://{seeded_bucket.name}")
    with_slash = run_cli("timeout", seeded_bucket.uri())

    assert f"{seeded_bucket.uri('app/server.log')}:connection timeout after 30s" in (
        without_slash.stdout_lines
    )
    assert f"{seeded_bucket.uri('other/notes.txt')}:timeout outside prefix" in (
        without_slash.stdout_lines
    )
    assert with_slash.stdout == without_slash.stdout
    # La raíz incluye broken/latin1.log (objeto fallido), por eso FR-6 exige 2.
    assert without_slash.code == 2


# --- VC-2 / FR-2: prefijo literal --------------------------------------------


def test_vc2_prefix_with_slash_excludes_similar_prefix(seeded_bucket):
    run = run_cli("prefixmark", seeded_bucket.uri("logs/"))
    assert run.code == 0
    assert run.stdout_lines == [
        f"{seeded_bucket.uri('logs/a.log')}:prefixmark",
        f"{seeded_bucket.uri('logs/b.log')}:prefixmark",
        f"{seeded_bucket.uri('logs/c.log')}:prefixmark",
    ]


def test_vc2_prefix_without_slash_is_not_completed(seeded_bucket):
    run = run_cli("prefixmark", seeded_bucket.uri("logs"))
    assert run.code == 0
    assert len(run.stdout_lines) == 4
    assert f"{seeded_bucket.uri('logs-other/d.log')}:prefixmark" in run.stdout_lines


# --- VC-17 / VC-18 / FR-3: bordes de línea y objeto vacío --------------------


def test_vc17_last_line_without_newline_counts_as_line(seeded_bucket):
    run = run_cli("-n", "b timeout", seeded_bucket.uri("edge/"))
    assert run.code == 0
    assert run.stdout_lines == [f"{seeded_bucket.uri('edge/nonl.log')}:2:b timeout"]


def test_vc18_empty_object_produces_no_output(seeded_bucket):
    run = run_cli("timeout", seeded_bucket.uri("empty/"))
    assert run.code == 1
    assert run.stdout == ""
    assert run.stderr == ""


# --- VC-4 / FR-4 y VC-19 / FR-9: formato de salida ---------------------------


def test_vc4_output_without_line_number(seeded_bucket):
    run = run_cli("timeout", seeded_bucket.uri("app/"))
    assert run.code == 0
    assert run.stdout_lines == [
        f"{seeded_bucket.uri('app/server.log')}:connection timeout after 30s"
    ]


def test_vc19_output_with_line_number(seeded_bucket):
    run = run_cli("-n", "timeout", seeded_bucket.uri("app/"))
    assert run.code == 0
    assert run.stdout_lines == [
        f"{seeded_bucket.uri('app/server.log')}:4:connection timeout after 30s"
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


# --- VC-6 / FR-6: objeto fallido ---------------------------------------------


def test_vc6_unreadable_object_is_reported_and_scan_continues(seeded_bucket):
    run = run_cli("-n", "timeout", seeded_bucket.uri("broken/"))
    assert run.code == 2
    assert run.stdout_lines == [f"{seeded_bucket.uri('broken/ok.log')}:1:timeout here"]
    assert run.stderr.startswith(
        f"gcsgrep: no se pudo leer {seeded_bucket.uri('broken/latin1.log')}:"
    )
    assert_no_traceback(run)


# --- VC-7 / FR-7: sin matches ------------------------------------------------


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
    assert run.stderr.splitlines() == ["gcsgrep: objetos procesados: 100"]
    assert not any(line.startswith("gcsgrep:") for line in run.stdout_lines)


# --- VC-20 / FR-10: exit 0 ---------------------------------------------------


def test_vc20_match_without_errors_returns_zero(seeded_bucket):
    run = run_cli("timeout", seeded_bucket.uri("app/"))
    assert run.code == 0
    assert run.stdout_lines
    assert run.stderr == ""


# --- VC-21 / FR-11: URI inválido ---------------------------------------------


@pytest.mark.parametrize("location", ["{name}/app/", "gs://", "gs:///app", "gs://a b"])
def test_vc21_invalid_uri_exits_two_with_message(seeded_bucket, location):
    run = run_cli("timeout", location.format(name=seeded_bucket.name))
    assert run.code == 2
    assert run.stdout == ""
    assert run.stderr.startswith("gcsgrep: ")
    assert_no_traceback(run)


# --- VC-22 / FR-12: fallo al enumerar ----------------------------------------


def test_vc22_missing_bucket_exits_two(seeded_bucket):
    run = run_cli("timeout", "gs://gcsgrep-no-such-bucket-000/")
    assert run.code == 2
    assert run.stdout == ""
    assert run.stderr.startswith("gcsgrep: no se pudo enumerar")
    assert_no_traceback(run)


# --- VC-23 / FR-13: --max-objects --------------------------------------------


def test_vc23_max_objects_adjusts_object_limit(seeded_bucket):
    limited = run_cli("--max-objects", "2", "prefixmark", seeded_bucket.uri("logs/"))
    exact = run_cli("--max-objects", "3", "prefixmark", seeded_bucket.uri("logs/"))

    assert limited.code == 2
    assert "gcsgrep: límite de seguridad alcanzado: máximo 2 objetos" in limited.stderr
    assert exact.code == 0
    assert "límite" not in exact.stderr


# --- VC-24 / FR-14: --max-bytes ----------------------------------------------


def test_vc24_max_bytes_adjusts_byte_limit(seeded_bucket):
    limited = run_cli("--max-bytes", "29", "timeout", seeded_bucket.uri("bytes/"))
    exact = run_cli("--max-bytes", "30", "timeout", seeded_bucket.uri("bytes/"))

    assert limited.code == 2
    assert limited.stdout_lines == [f"{seeded_bucket.uri('bytes/ten.log')}:timeout!!"]
    assert "gcsgrep: límite de seguridad alcanzado: máximo 29 bytes" in limited.stderr
    assert exact.code == 0
    assert len(exact.stdout_lines) == 2


# --- VC-25 / FR-15: valor de límite inválido ---------------------------------


@pytest.mark.parametrize(
    "flag, value", [("--max-objects", "0"), ("--max-objects", "-5"), ("--max-bytes", "abc")]
)
def test_vc25_invalid_limit_value_exits_two(seeded_bucket, flag, value):
    run = run_cli(flag, value, "timeout", seeded_bucket.uri())
    assert run.code == 2
    assert run.stdout == ""
    assert "debe ser un entero positivo" in run.stderr
    assert_no_traceback(run)


# --- VC-26 / FR-16: orden de la salida ---------------------------------------


def test_vc26_output_is_lexicographic_and_deterministic(seeded_bucket):
    first = run_cli("-n", "ordmark", seeded_bucket.uri("order/"))
    second = run_cli("-n", "ordmark", seeded_bucket.uri("order/"))

    assert first.stdout_lines == [
        f"{seeded_bucket.uri('order/a.log')}:2:ordmark 2",
        f"{seeded_bucket.uri('order/b.log')}:1:ordmark 1",
        f"{seeded_bucket.uri('order/b.log')}:3:ordmark 3",
    ]
    assert first.stdout == second.stdout


# --- VC-9 / BR-1: solo lectura -----------------------------------------------


def test_vc9_bucket_is_unchanged_after_scans(seeded_bucket):
    from google.cloud import storage

    run_cli("-i", "-n", "timeout", seeded_bucket.uri())
    run_cli("timeout", seeded_bucket.uri("broken/"))
    run_cli("--max-objects", "1", "timeout", seeded_bucket.uri("app/"))
    run_cli("--max-bytes", "29", "timeout", seeded_bucket.uri("bytes/"))

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
    assert run.stderr.startswith("gcsgrep: no se pudieron cargar las credenciales")
    assert_no_traceback(run)


# --- VC-11 / BR-3: guardrail de costo ----------------------------------------


def test_vc11_object_limit_stops_scan_with_two(seeded_bucket):
    run = run_cli("--max-objects", "2", "timeout", seeded_bucket.uri("app/"))
    assert run.code == 2
    assert "gcsgrep: límite de seguridad alcanzado: máximo 2 objetos" in run.stderr
    assert_no_traceback(run)


def test_vc11_byte_limit_stops_scan_with_two(seeded_bucket):
    run = run_cli("--max-bytes", "10", "timeout", seeded_bucket.uri("app/"))
    assert run.code == 2
    assert "gcsgrep: límite de seguridad alcanzado: máximo 10 bytes" in run.stderr
    assert_no_traceback(run)


# --- VC-12 / BR-4: binarios y .gz --------------------------------------------


def test_vc12_gz_and_binary_objects_are_skipped(seeded_bucket):
    run = run_cli("-i", "timeout", seeded_bucket.uri("app/"))
    assert run.code == 0
    assert "archive.gz" not in run.stdout
    assert "blob.bin" not in run.stdout
    assert "\x00" not in run.stdout
    assert "archive.gz" not in run.stderr
    assert "blob.bin" not in run.stderr
