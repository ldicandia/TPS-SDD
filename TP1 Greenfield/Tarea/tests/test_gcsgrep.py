from __future__ import annotations

import builtins
import io
import tempfile

import pytest

from gcsgrep.cli import main
from gcsgrep.gcs import CHUNK_SIZE, SAMPLE_SIZE, parse_gs_uri, scan


class RecordingStream(io.BytesIO):
    """Stream que registra el tamaño de cada lectura, como un BlobReader."""

    def __init__(self, content: bytes):
        super().__init__(content)
        self.read_sizes: list[int] = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


class FakeBlob:
    def __init__(
        self,
        name: str,
        content: bytes,
        *,
        fail: Exception | None = None,
        size: int | None = None,
    ):
        self.name = name
        self.content = content
        self.size = len(content) if size is None else size
        self.fail = fail
        self.opened = False
        self.stream: RecordingStream | None = None

    def open(self, mode):
        self.opened = True
        if self.fail:
            raise self.fail
        self.stream = RecordingStream(self.content)
        return self.stream


class FakeBucket:
    def __init__(self, blobs, *, list_error: Exception | None = None):
        self.blobs = blobs
        self.list_error = list_error
        self.requested_prefix = None

    def list_blobs(self, *, prefix):
        if self.list_error:
            raise self.list_error
        self.requested_prefix = prefix
        return (blob for blob in self.blobs if blob.name.startswith(prefix))


class FakeClient:
    def __init__(self, blobs, *, list_error: Exception | None = None):
        self.bucket_instance = FakeBucket(blobs, list_error=list_error)

    def bucket(self, name):
        self.bucket_name = name
        return self.bucket_instance


def run(argv, blobs=(), *, list_error=None):
    """Ejecuta el CLI con un cliente falso y devuelve (exit code, stdout, stderr)."""
    client = FakeClient(list(blobs), list_error=list_error)
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main(argv, client_factory=lambda: client, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


# --- VC-1 / FR-1: bucket completo --------------------------------------------


def test_vc1_bucket_root_covers_every_prefix():
    blobs = [
        FakeBlob("app/server.log", b"timeout\n"),
        FakeBlob("other/notes.txt", b"timeout\n"),
    ]

    code, stdout, _ = run(["timeout", "gs://logs"], blobs)
    _, stdout_with_slash, _ = run(["timeout", "gs://logs/"], blobs)

    assert code == 0
    assert stdout.splitlines() == [
        "gs://logs/app/server.log:timeout",
        "gs://logs/other/notes.txt:timeout",
    ]
    assert stdout_with_slash == stdout


def test_vc1_parse_bucket_without_prefix():
    assert parse_gs_uri("gs://logs") == ("logs", "")
    assert parse_gs_uri("gs://logs/") == ("logs", "")


# --- VC-2 / FR-2: prefijo literal --------------------------------------------


def test_vc2_prefix_is_literal_and_not_completed_with_slash():
    blobs = [
        FakeBlob("logs/a.log", b"mark\n"),
        FakeBlob("logs/b.log", b"mark\n"),
        FakeBlob("logs/c.log", b"mark\n"),
        FakeBlob("logs-other/d.log", b"mark\n"),
    ]

    _, with_slash, _ = run(["mark", "gs://B/logs/"], blobs)
    _, without_slash, _ = run(["mark", "gs://B/logs"], blobs)

    assert with_slash.splitlines() == [
        "gs://B/logs/a.log:mark",
        "gs://B/logs/b.log:mark",
        "gs://B/logs/c.log:mark",
    ]
    assert len(without_slash.splitlines()) == 4
    assert "gs://B/logs-other/d.log:mark" in without_slash.splitlines()


def test_vc2_parse_prefix():
    assert parse_gs_uri("gs://logs/app/") == ("logs", "app/")
    assert parse_gs_uri("gs://logs/app") == ("logs", "app")


# --- VC-3 / FR-3: streaming --------------------------------------------------


def test_vc3_matches_crossing_chunk_boundaries_without_local_files(monkeypatch):
    # Primer match cruza el borde de la muestra inicial (SAMPLE_SIZE); el segundo,
    # el borde del primer chunk incremental (SAMPLE_SIZE + CHUNK_SIZE).
    content = b"a" * (SAMPLE_SIZE - 5) + b"timeout 1\n"
    second_boundary = SAMPLE_SIZE + CHUNK_SIZE
    content += b"b" * (second_boundary - 5 - len(content)) + b"timeout 2\n"
    content += b"tail\n"
    blob = FakeBlob("big.log", content)
    matches = []

    def forbidden(*_args, **_kwargs):
        raise AssertionError("gcsgrep no debe crear archivos locales")

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        for name in ("TemporaryFile", "NamedTemporaryFile", "SpooledTemporaryFile", "mkstemp"):
            patch.setattr(tempfile, name, forbidden)
        scan(
            FakeClient([blob]),
            "gs://logs/",
            "timeout",
            include_line_numbers=True,
            on_match=lambda name, number, text: matches.append((number, text[-9:])),
        )

    assert matches == [(1, "timeout 1"), (2, "timeout 2")]
    assert len(blob.stream.read_sizes) > 2
    assert all(0 < size <= CHUNK_SIZE for size in blob.stream.read_sizes)


# --- VC-17 / FR-3: última línea sin terminador -------------------------------


def test_vc17_last_line_without_newline_counts_as_line():
    code, stdout, _ = run(["-n", "b timeout", "gs://B/"], [FakeBlob("obj", b"a\nb timeout")])

    assert code == 0
    assert stdout == "gs://B/obj:2:b timeout\n"


def test_vc17_crlf_terminator_is_not_part_of_the_line():
    code, stdout, _ = run(["-n", "timeout", "gs://B/"], [FakeBlob("obj", b"a\r\nb timeout\r\n")])

    assert code == 0
    assert stdout == "gs://B/obj:2:b timeout\n"


# --- VC-29 / FR-3: patrón vacío ---------------------------------------------


def test_vc29_empty_pattern_matches_every_line():
    code, stdout, _ = run(["-n", "", "gs://B/edge/"], [FakeBlob("edge/nonl.log", b"a\nb timeout")])

    assert code == 0
    assert stdout == "gs://B/edge/nonl.log:1:a\ngs://B/edge/nonl.log:2:b timeout\n"


# --- VC-18 / FR-3: objeto de 0 bytes -----------------------------------------


def test_vc18_empty_object_is_inspected_without_output():
    blob = FakeBlob("zero.log", b"")

    code, stdout, stderr = run(["timeout", "gs://B/"], [blob])

    assert code == 1
    assert stdout == ""
    assert stderr == ""
    assert blob.opened


# --- VC-4 / FR-4: formato sin -n ---------------------------------------------


def test_vc4_output_without_line_number():
    blobs = [FakeBlob("app/server.log", b"healthy\nconnection timeout after 30s\n")]

    code, stdout, _ = run(["timeout", "gs://B/app/"], blobs)

    assert code == 0
    assert stdout == "gs://B/app/server.log:connection timeout after 30s\n"


# --- VC-19 / FR-9: formato con -n --------------------------------------------


def test_vc19_output_with_line_number():
    content = b"healthy\nRequest Timeout\nfinished\nconnection timeout after 30s\n"

    code, stdout, _ = run(["-n", "timeout", "gs://B/app/"], [FakeBlob("app/server.log", content)])

    assert code == 0
    assert stdout == "gs://B/app/server.log:4:connection timeout after 30s\n"


# --- VC-5 / FR-5: -i ---------------------------------------------------------


def test_vc5_ignore_case_finds_every_variant():
    blobs = [FakeBlob("app.log", b"TIMEOUT\nTimeout\ntimeout\n")]

    _, with_i, _ = run(["-i", "-n", "timeout", "gs://logs/"], blobs)
    _, without_i, _ = run(["-n", "timeout", "gs://logs/"], blobs)

    assert with_i.splitlines() == [
        "gs://logs/app.log:1:TIMEOUT",
        "gs://logs/app.log:2:Timeout",
        "gs://logs/app.log:3:timeout",
    ]
    assert without_i.splitlines() == ["gs://logs/app.log:3:timeout"]


# --- VC-6 / FR-6: objeto fallido ---------------------------------------------


def test_vc6_failed_object_is_reported_and_scan_continues():
    blobs = [
        FakeBlob("broken/latin1.log", b"caf\xe9 timeout\n"),
        FakeBlob("broken/ok.log", b"timeout here\n"),
    ]

    code, stdout, stderr = run(["timeout", "gs://B/broken/"], blobs)

    assert code == 2
    assert stdout == "gs://B/broken/ok.log:timeout here\n"
    assert stderr.startswith("gcsgrep: no se pudo leer gs://B/broken/latin1.log:")
    assert "Traceback" not in stderr


def test_vc6_lines_before_the_invalid_line_are_kept():
    blobs = [FakeBlob("partial/mixed.log", b"timeout 1\ncaf\xe9 timeout 2\ntimeout 3\n")]

    code, stdout, stderr = run(["-n", "timeout", "gs://B/partial/"], blobs)

    assert code == 2
    assert stdout == "gs://B/partial/mixed.log:1:timeout 1\n"
    assert stderr.startswith("gcsgrep: no se pudo leer gs://B/partial/mixed.log:")


def test_vc6_permission_error_on_open_is_a_failed_object():
    blobs = [
        FakeBlob("broken.log", b"", fail=OSError("permission denied")),
        FakeBlob("good.log", b"timeout\n"),
    ]

    code, stdout, stderr = run(["timeout", "gs://logs/"], blobs)

    assert code == 2
    assert stdout == "gs://logs/good.log:timeout\n"
    assert stderr == "gcsgrep: no se pudo leer gs://logs/broken.log: permission denied\n"


# --- VC-7 / FR-7: sin matches ------------------------------------------------


def test_vc7_no_match_returns_one_with_empty_stdout():
    code, stdout, _ = run(["timeout", "gs://logs/"], [FakeBlob("app.log", b"healthy\n")])

    assert code == 1
    assert stdout == ""


def test_vc30_prefix_without_objects_returns_one():
    code, stdout, stderr = run(["timeout", "gs://B/prefijo-sin-objetos/"], [])

    assert code == 1
    assert stdout == ""
    assert stderr == ""


# --- VC-8 / FR-8: progreso ---------------------------------------------------


def test_vc8_progress_line_every_hundred_objects():
    blobs = [FakeBlob(f"object-{index:03d}.log", b"healthy\n") for index in range(100)]

    code, stdout, stderr = run(["timeout", "gs://logs/"], blobs)

    assert code == 1
    assert stdout == ""
    assert stderr == "gcsgrep: objetos inspeccionados: 100\n"


def test_vc8_no_progress_line_below_hundred_objects():
    blobs = [FakeBlob(f"object-{index:03d}.log", b"healthy\n") for index in range(99)]

    _, _, stderr = run(["timeout", "gs://logs/"], blobs)

    assert "objetos inspeccionados" not in stderr


# --- VC-20 / FR-10: exit 0 ---------------------------------------------------


def test_vc20_match_without_errors_returns_zero():
    code, stdout, stderr = run(
        ["-i", "-n", "timeout", "gs://logs/"], [FakeBlob("app.log", b"ok\nRequest Timeout\n")]
    )

    assert code == 0
    assert stdout == "gs://logs/app.log:2:Request Timeout\n"
    assert stderr == ""


# --- VC-21 / FR-11: URI inválido ---------------------------------------------


@pytest.mark.parametrize("location", ["logs/app", "gs://", "gs:///x", "gs://a b"])
def test_vc21_invalid_uri_fails_before_loading_credentials(location):
    def failing_factory():
        raise AssertionError("no se debe crear el cliente para un URI inválido")

    stdout = io.StringIO()
    stderr = io.StringIO()

    code = main(["x", location], client_factory=failing_factory, stdout=stdout, stderr=stderr)

    assert code == 2
    assert stdout.getvalue() == ""
    assert stderr.getvalue().startswith("gcsgrep: ")
    assert "Traceback" not in stderr.getvalue()


# --- VC-22 / FR-12: fallo al enumerar ----------------------------------------


def test_vc22_listing_failure_returns_two():
    code, stdout, stderr = run(
        ["timeout", "gs://logs/app/"], list_error=RuntimeError("404 Bucket not found")
    )

    assert code == 2
    assert stdout == ""
    assert stderr.startswith("gcsgrep: no se pudo enumerar gs://logs/app/: ")


# --- VC-23 / FR-13: --max-objects --------------------------------------------


def test_vc23_max_objects_adjusts_object_limit():
    blobs = [FakeBlob(f"{name}.log", b"timeout\n") for name in ("a", "b", "c")]

    code_two, _, stderr_two = run(["--max-objects", "2", "timeout", "gs://B/"], blobs)
    code_three, _, stderr_three = run(["--max-objects", "3", "timeout", "gs://B/"], blobs)

    assert code_two == 2
    assert "gcsgrep: límite de seguridad alcanzado: máximo 2 objetos" in stderr_two
    assert code_three == 0
    assert "límite" not in stderr_three


# --- VC-24 / FR-14: --max-bytes ----------------------------------------------


def test_vc24_max_bytes_adjusts_byte_limit_before_reading():
    def blobs():
        return [
            FakeBlob("ten.log", b"timeout!!\n"),
            FakeBlob("twenty.log", b"timeout 01234567890\n"),
        ]

    limited = blobs()
    code_29, stdout_29, stderr_29 = run(["--max-bytes", "29", "timeout", "gs://B/"], limited)
    code_30, stdout_30, _ = run(["--max-bytes", "30", "timeout", "gs://B/"], blobs())

    assert code_29 == 2
    assert stdout_29 == "gs://B/ten.log:timeout!!\n"
    assert "gcsgrep: límite de seguridad alcanzado: máximo 29 bytes" in stderr_29
    assert limited[1].opened is False
    assert code_30 == 0
    assert len(stdout_30.splitlines()) == 2


# --- VC-25 / FR-15: valor de límite inválido ---------------------------------


@pytest.mark.parametrize(
    "flag, value", [("--max-objects", "0"), ("--max-objects", "-5"), ("--max-bytes", "abc")]
)
def test_vc25_invalid_limit_value_exits_two(flag, value, capsys):
    def failing_factory():
        raise AssertionError("no se debe contactar a GCS con un límite inválido")

    stdout = io.StringIO()

    with pytest.raises(SystemExit) as exit_info:
        main([flag, value, "x", "gs://B"], client_factory=failing_factory, stdout=stdout)

    assert exit_info.value.code == 2
    assert stdout.getvalue() == ""
    assert "debe ser un entero positivo" in capsys.readouterr().err


# --- VC-26 / FR-16: orden de la salida ---------------------------------------


def test_vc26_output_follows_listing_order_and_line_order():
    blobs = [
        FakeBlob("app/a.log", b"x\nmark\n"),
        FakeBlob("app/b.log", b"mark 1\nx\nmark 3\n"),
    ]

    _, first, _ = run(["-n", "mark", "gs://B/app/"], blobs)
    _, second, _ = run(["-n", "mark", "gs://B/app/"], blobs)

    assert [line.rsplit(":", 1)[0] for line in first.splitlines()] == [
        "gs://B/app/a.log:2",
        "gs://B/app/b.log:1",
        "gs://B/app/b.log:3",
    ]
    assert first == second


# --- VC-11 / BR-3: guardrail de costo ----------------------------------------


def test_vc11_default_object_limit_stops_at_1001():
    blobs = [FakeBlob(f"object-{index:04d}.log", b"x\n") for index in range(1001)]

    code, _, stderr = run(["timeout", "gs://B/"], blobs)

    assert code == 2
    assert "gcsgrep: límite de seguridad alcanzado: máximo 1000 objetos" in stderr
    assert blobs[1000].opened is False


def test_vc11_exactly_1000_objects_does_not_reach_limit():
    blobs = [FakeBlob(f"object-{index:04d}.log", b"x\n") for index in range(1000)]

    code, _, stderr = run(["timeout", "gs://B/"], blobs)

    assert code == 1
    assert "límite" not in stderr


def test_vc11_skipped_objects_count_toward_limit():
    blobs = [FakeBlob("a.gz", b"timeout"), FakeBlob("b.log", b"timeout\n")]

    code, stdout, stderr = run(["--max-objects", "1", "timeout", "gs://B/"], blobs)

    assert code == 2
    assert stdout == ""
    assert "máximo 1 objetos" in stderr


# --- VC-27 / BR-3: límite de bytes por defecto -------------------------------


def test_vc27_default_byte_limit_keeps_previous_matches():
    big = FakeBlob("big.log", b"timeout\n", size=1024**3 + 1)
    blobs = [FakeBlob("a.log", b"timeout\n"), big]

    code, stdout, stderr = run(["timeout", "gs://B/"], blobs)

    assert code == 2
    assert stdout == "gs://B/a.log:timeout\n"
    assert "gcsgrep: límite de seguridad alcanzado: máximo 1073741824 bytes" in stderr
    assert big.opened is False


# --- VC-12 / BR-4: binarios y .gz --------------------------------------------


def test_vc12_gzip_and_binary_are_skipped_and_next_text_is_processed():
    blobs = [
        FakeBlob("binary.dat", b"timeout\x00not text"),
        FakeBlob("compressed.GZ", b"timeout"),
        FakeBlob("app.log", b"timeout\n"),
    ]

    code, stdout, stderr = run(["timeout", "gs://logs/"], blobs)

    assert code == 0
    assert stdout == "gs://logs/app.log:timeout\n"
    assert stderr == ""


def test_vc12_nul_after_initial_sample_does_not_skip_object():
    content = b"a" * SAMPLE_SIZE + b"\n\x00 timeout\n"

    code, stdout, _ = run(["-n", "timeout", "gs://B/"], [FakeBlob("late-nul.log", content)])

    assert code == 0
    assert stdout == "gs://B/late-nul.log:2:\x00 timeout\n"


# --- VC-16 / NFR-3: scripting ------------------------------------------------


@pytest.mark.parametrize(
    "argv, blobs, list_error",
    [
        (["x", "logs/app"], [], None),
        (["x", "gs://B/"], [], RuntimeError("404")),
        (["x", "gs://B/"], [FakeBlob("bad.log", b"\xe9\n")], None),
        (["--max-objects", "1", "x", "gs://B/"], [FakeBlob("a", b""), FakeBlob("b", b"")], None),
    ],
)
def test_vc16_errors_go_to_stderr_without_traceback(argv, blobs, list_error):
    code, stdout, stderr = run(argv, blobs, list_error=list_error)

    assert code == 2
    assert stdout == ""
    assert stderr.startswith("gcsgrep: ")
    assert "Traceback" not in stderr
