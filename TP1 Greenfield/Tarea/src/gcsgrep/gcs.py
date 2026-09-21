"""Google Cloud Storage access and streaming scan primitives."""

from __future__ import annotations

import codecs
from dataclasses import dataclass
from itertools import chain
from typing import Callable, Iterable

from .matcher import find_matches

SAMPLE_SIZE = 8192
CHUNK_SIZE = 64 * 1024


class GcsGrepError(Exception):
    """Expected operational error shown without a traceback."""


class CostLimitReached(GcsGrepError):
    """The configured object or byte limit was reached."""


@dataclass
class ScanResult:
    scanned_objects: int = 0
    matched: bool = False
    had_errors: bool = False


def parse_gs_uri(uri: str) -> tuple[str, str]:
    """Return bucket and exact object-name prefix from a gs:// URI."""
    if not uri.startswith("gs://"):
        raise GcsGrepError("la ubicación debe comenzar con gs://")

    remainder = uri[5:]
    if not remainder or remainder.startswith("/"):
        raise GcsGrepError("la ubicación debe incluir un bucket válido")

    bucket, separator, prefix = remainder.partition("/")
    if not bucket or any(char.isspace() for char in bucket):
        raise GcsGrepError("el nombre del bucket no es válido")

    return bucket, prefix if separator else ""


def create_storage_client():
    """Create the official GCS client using Application Default Credentials."""
    try:
        from google.cloud import storage
    except ImportError as exc:  # pragma: no cover - exercised in installation errors
        raise GcsGrepError(
            "falta la dependencia google-cloud-storage; instalá el proyecto con pip"
        ) from exc

    try:
        return storage.Client()
    except Exception as exc:  # pragma: no cover - depends on local credentials
        raise GcsGrepError(f"no se pudieron cargar las credenciales de GCP: {exc}") from exc


def _iter_utf8_lines(stream, first_chunk: bytes) -> Iterable[str]:
    """Decode a stream incrementally and yield lines without buffering the object."""
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    pending = ""

    for chunk in chain(
        (first_chunk,),
        iter(lambda: stream.read(CHUNK_SIZE), b""),
    ):
        pending += decoder.decode(chunk)
        parts = pending.splitlines(keepends=True)
        if parts and not parts[-1].endswith(("\n", "\r")):
            pending = parts.pop()
        else:
            pending = ""

        for part in parts:
            yield part.rstrip("\r\n")

    pending += decoder.decode(b"", final=True)
    if pending:
        yield pending.rstrip("\r\n")


def _scan_blob(
    blob,
    pattern: str,
    ignore_case: bool,
    include_line_numbers: bool,
    on_match: Callable[[str, int, str], None],
) -> bool:
    name = getattr(blob, "name", "")
    if name.lower().endswith(".gz"):
        return False

    stream = blob.open("rb")
    try:
        first_chunk = stream.read(SAMPLE_SIZE)
        if b"\x00" in first_chunk:
            return False

        found = False
        lines = _iter_utf8_lines(stream, first_chunk)
        for line_number, line in find_matches(lines, pattern, ignore_case):
            found = True
            on_match(name, line_number if include_line_numbers else 0, line)
        return found
    finally:
        stream.close()


def scan(
    client,
    location: str,
    pattern: str,
    *,
    ignore_case: bool = False,
    include_line_numbers: bool = False,
    max_objects: int = 1000,
    max_bytes: int = 1024**3,
    on_match: Callable[[str, int, str], None] | None = None,
    on_error: Callable[[str, Exception], None] | None = None,
    on_progress: Callable[[int], None] | None = None,
    progress_every: int = 100,
) -> ScanResult:
    """Scan objects below ``location`` using an injected GCS client."""
    bucket_name, prefix = parse_gs_uri(location)
    bucket = client.bucket(bucket_name)
    on_match = on_match or (lambda _name, _line, _text: None)
    on_error = on_error or (lambda _name, _error: None)
    result = ScanResult()
    bytes_considered = 0

    try:
        blobs = bucket.list_blobs(prefix=prefix)
        for blob in blobs:
            result.scanned_objects += 1
            if result.scanned_objects > max_objects:
                raise CostLimitReached(
                    f"límite de seguridad alcanzado: máximo {max_objects} objetos"
                )

            size = getattr(blob, "size", None) or 0
            if bytes_considered + size > max_bytes:
                raise CostLimitReached(
                    f"límite de seguridad alcanzado: máximo {max_bytes} bytes"
                )
            bytes_considered += size

            try:
                object_uri = f"gs://{bucket_name}/{getattr(blob, 'name', '')}"

                def emit_match(_name, line_number, text):
                    on_match(object_uri, line_number, text)

                if _scan_blob(
                    blob,
                    pattern,
                    ignore_case,
                    include_line_numbers,
                    emit_match,
                ):
                    result.matched = True
            except Exception as exc:
                result.had_errors = True
                on_error(
                    f"gs://{bucket_name}/{getattr(blob, 'name', '<objeto desconocido>')}",
                    exc,
                )

            if progress_every and result.scanned_objects % progress_every == 0:
                if on_progress:
                    on_progress(result.scanned_objects)
    except CostLimitReached:
        raise
    except Exception as exc:
        raise GcsGrepError(f"no se pudo enumerar gs://{bucket_name}/{prefix}: {exc}") from exc

    return result
