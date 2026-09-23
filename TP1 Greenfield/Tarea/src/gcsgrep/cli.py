"""Command-line interface for gcsgrep."""

from __future__ import annotations

import argparse
import sys
from typing import TextIO

from .gcs import CostLimitReached, GcsGrepError, create_storage_client, parse_gs_uri, scan


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("debe ser un entero positivo") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("debe ser un entero positivo")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gcsgrep",
        description="Busca texto dentro de objetos de Google Cloud Storage.",
    )
    parser.add_argument("-i", "--ignore-case", action="store_true", help="ignora mayúsculas")
    parser.add_argument("-n", "--line-number", action="store_true", help="muestra número de línea")
    parser.add_argument(
        "--max-objects",
        type=_positive_int,
        default=1000,
        help="máximo de objetos a inspeccionar (default: 1000)",
    )
    parser.add_argument(
        "--max-bytes",
        type=_positive_int,
        default=1024**3,
        help="máximo de bytes declarados por los objetos (default: 1 GiB)",
    )
    parser.add_argument("pattern", help="texto literal a buscar")
    parser.add_argument("location", help="ubicación gs://bucket/prefijo")
    return parser


def main(
    argv: list[str] | None = None,
    *,
    client_factory=create_storage_client,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        # Validate the location before touching credentials so a typo reports the URI error.
        parse_gs_uri(args.location)
        client = client_factory()

        def emit_match(name: str, line_number: int, text: str) -> None:
            if line_number:
                print(f"{name}:{line_number}:{text}", file=stdout)
            else:
                print(f"{name}:{text}", file=stdout)

        def emit_error(name: str, error: Exception) -> None:
            print(f"gcsgrep: no se pudo leer {name}: {error}", file=stderr)

        def emit_progress(count: int) -> None:
            print(f"gcsgrep: objetos procesados: {count}", file=stderr)

        result = scan(
            client,
            args.location,
            args.pattern,
            ignore_case=args.ignore_case,
            include_line_numbers=args.line_number,
            max_objects=args.max_objects,
            max_bytes=args.max_bytes,
            on_match=emit_match,
            on_error=emit_error,
            on_progress=emit_progress,
        )
    except CostLimitReached as exc:
        print(f"gcsgrep: {exc}", file=stderr)
        return 2
    except GcsGrepError as exc:
        print(f"gcsgrep: {exc}", file=stderr)
        return 2

    if result.had_errors:
        return 2
    return 0 if result.matched else 1
