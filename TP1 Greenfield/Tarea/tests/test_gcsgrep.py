from __future__ import annotations

import io

from gcsgrep.cli import main
from gcsgrep.gcs import parse_gs_uri, scan


class FakeBlob:
    def __init__(self, name: str, content: bytes, *, fail: Exception | None = None):
        self.name = name
        self.content = content
        self.size = len(content)
        self.fail = fail

    def open(self, mode):
        if self.fail:
            raise self.fail
        return io.BytesIO(self.content)


class FakeBucket:
    def __init__(self, blobs):
        self.blobs = blobs
        self.requested_prefix = None

    def list_blobs(self, *, prefix):
        self.requested_prefix = prefix
        return (blob for blob in self.blobs if blob.name.startswith(prefix))


class FakeClient:
    def __init__(self, blobs):
        self.bucket_instance = FakeBucket(blobs)

    def bucket(self, name):
        self.bucket_name = name
        return self.bucket_instance


def test_parse_gs_uri():
    assert parse_gs_uri("gs://logs/app/") == ("logs", "app/")
    assert parse_gs_uri("gs://logs") == ("logs", "")


def test_parse_gs_uri_rejects_invalid_scheme():
    try:
        parse_gs_uri("bucket/logs")
    except Exception as exc:
        assert "gs://" in str(exc)
    else:
        raise AssertionError("expected invalid URI to fail")


def test_scan_finds_literal_matches_and_line_numbers():
    client = FakeClient([FakeBlob("app.log", b"ok\nrequest timeout\nend\n")])
    matches = []

    result = scan(
        client,
        "gs://logs/",
        "timeout",
        include_line_numbers=True,
        on_match=lambda name, number, text: matches.append((name, number, text)),
    )

    assert result.matched is True
    assert matches == [("gs://logs/app.log", 2, "request timeout")]


def test_scan_ignore_case_and_skip_binary_and_gzip():
    client = FakeClient(
        [
            FakeBlob("binary.dat", b"timeout\x00not text"),
            FakeBlob("compressed.gz", b"timeout"),
            FakeBlob("app.log", b"TIMEOUT\n"),
        ]
    )
    matches = []

    result = scan(
        client,
        "gs://logs/",
        "timeout",
        ignore_case=True,
        on_match=lambda name, number, text: matches.append((name, text)),
    )

    assert result.matched is True
    assert matches == [("gs://logs/app.log", "TIMEOUT")]


def test_scan_continues_after_object_error():
    errors = []
    matches = []
    client = FakeClient(
        [
            FakeBlob("broken.log", b"", fail=OSError("permission denied")),
            FakeBlob("good.log", b"timeout\n"),
        ]
    )

    result = scan(
        client,
        "gs://logs/",
        "timeout",
        on_match=lambda name, number, text: matches.append(name),
        on_error=lambda name, error: errors.append((name, str(error))),
    )

    assert result.had_errors is True
    assert matches == ["gs://logs/good.log"]
    assert errors == [("gs://logs/broken.log", "permission denied")]


def test_cli_exit_code_one_when_no_match():
    client = FakeClient([FakeBlob("app.log", b"healthy\n")])
    stdout = io.StringIO()
    stderr = io.StringIO()

    code = main(
        ["timeout", "gs://logs/"],
        client_factory=lambda: client,
        stdout=stdout,
        stderr=stderr,
    )

    assert code == 1
    assert stdout.getvalue() == ""


def test_cli_formats_match_and_returns_zero():
    client = FakeClient([FakeBlob("app.log", b"ok\nRequest Timeout\n")])
    stdout = io.StringIO()
    stderr = io.StringIO()

    code = main(
        ["-i", "-n", "timeout", "gs://logs/"],
        client_factory=lambda: client,
        stdout=stdout,
        stderr=stderr,
    )

    assert code == 0
    assert stdout.getvalue() == "gs://logs/app.log:2:Request Timeout\n"


def test_cli_returns_two_for_invalid_location():
    stdout = io.StringIO()
    stderr = io.StringIO()

    code = main(
        ["timeout", "bucket/logs"],
        client_factory=lambda: FakeClient([]),
        stdout=stdout,
        stderr=stderr,
    )

    assert code == 2
    assert "gs://" in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()


def test_cli_returns_two_when_object_limit_is_reached():
    client = FakeClient(
        [FakeBlob("one.log", b"timeout\n"), FakeBlob("two.log", b"timeout\n")]
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    code = main(
        ["--max-objects", "1", "timeout", "gs://logs/"],
        client_factory=lambda: client,
        stdout=stdout,
        stderr=stderr,
    )

    assert code == 2
    assert "límite" in stderr.getvalue()


def test_scan_reports_progress_every_hundred_objects():
    client = FakeClient([FakeBlob(f"object-{index}.log", b"healthy\n") for index in range(100)])
    progress = []

    result = scan(
        client,
        "gs://logs/",
        "timeout",
        on_progress=progress.append,
    )

    assert result.scanned_objects == 100
    assert progress == [100]
