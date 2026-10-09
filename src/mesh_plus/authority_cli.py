"""Host Mesh v1 authority process facade; no picker/history dependencies."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
from typing import TextIO

from .authority import (
    MAX_ERROR_MESSAGE_CODEPOINTS,
    MeshError,
    MeshPersistenceError,
    RouteHealthStore,
    load_mesh,
    report_route,
    route_health_path,
)

# These limits are part of the Host Mesh v1 process profile.  The final LF is
# included in ``MAX_STDOUT_BYTES``; stderr is intentionally never a machine
# channel and is kept bounded by avoiding argparse's unbounded diagnostics.
MAX_STDOUT_BYTES = 512 * 1024
MAX_STDERR_BYTES = 64 * 1024
_ERROR_CODE_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]*\Z")


class _JsonOutputTooLarge(ValueError):
    """The producer response cannot fit the Host Mesh stdout profile."""


class _JsonEncodingError(ValueError):
    """The producer response cannot be represented as strict UTF-8 JSON."""


class _MeshArgumentError(ValueError):
    """Internal parser failure with no stderr side effects."""


def _json_bytes(payload: object) -> bytes:
    """Encode one canonical response document and enforce its byte cap."""

    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8", errors="strict")
    except (TypeError, UnicodeError, ValueError) as exc:
        raise _JsonEncodingError("response is not strict UTF-8 JSON") from exc
    result = encoded + b"\n"
    if len(result) > MAX_STDOUT_BYTES:
        raise _JsonOutputTooLarge(
            f"response exceeds {MAX_STDOUT_BYTES} stdout bytes"
        )
    return result


def _json_write(stream: TextIO, payload: object) -> None:
    """Write exactly one UTF-8 document followed by one LF.

    Real process stdout is written through its binary buffer so the result is
    independent of the user's locale.  Unit-test text streams receive the
    same bytes decoded strictly as UTF-8.
    """

    data = _json_bytes(payload)
    buffer = getattr(stream, "buffer", None)
    if buffer is not None and hasattr(buffer, "write"):
        buffer.write(data)
        buffer.flush()
    else:
        text = data.decode("utf-8", errors="strict")
        try:
            stream.write(text)
        except TypeError:
            # A binary test/embedding stream (for example ``BytesIO``) has no
            # ``buffer`` attribute but still provides the desired byte sink.
            # The first write cannot have modified a normal binary stream when
            # it rejects text, so retrying with the already bounded bytes is
            # safe and keeps the process contract testable without wrappers.
            stream.write(data)  # type: ignore[arg-type]
        stream.flush()


def _error_payload(code: str, message: str) -> dict[str, object]:
    if (
        not isinstance(code, str)
        or not code
        or len(code) > 64
        or _ERROR_CODE_RE.fullmatch(code) is None
    ):
        code = "persistence_failed"
    if not isinstance(message, str):
        message = str(message)
    if not message:
        message = "Host Mesh operation failed"
    # Error messages are diagnostic and may include an OS/configuration error
    # that is much larger than the wire profile.  Truncate before encoding so
    # the fallback envelope remains small and structurally valid.
    message = message[:MAX_ERROR_MESSAGE_CODEPOINTS]
    return {
        "schemaVersion": 1,
        "ok": False,
        "error": {"code": code, "message": message},
    }


def _write_error(stream: TextIO, code: str, message: str) -> None:
    """Write a bounded typed error, with a fixed-size construction fallback."""

    try:
        _json_write(stream, _error_payload(code, message))
    except (_JsonOutputTooLarge, _JsonEncodingError):
        # This branch is defensive: _error_payload already bounds messages,
        # but preserving one small envelope is preferable if future fields or
        # a custom exception accidentally exceed the profile.
        _json_write(
            stream,
            _error_payload("persistence_failed", "unable to construct response"),
        )


class _MeshArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that never writes unbounded usage text to stderr."""

    def error(self, message: str) -> None:  # pragma: no cover - exercised via parse
        raise _MeshArgumentError(message)

    def exit(self, status: int = 0, message: str | None = None) -> None:
        del status
        raise _MeshArgumentError(message or "invalid mesh command arguments")


def _mesh_parser() -> argparse.ArgumentParser:
    parser = _MeshArgumentParser(prog="mesh-plus mesh", add_help=False)
    subparsers = parser.add_subparsers(dest="command", required=True)
    list_parser = subparsers.add_parser("list", add_help=False)
    list_parser.add_argument("--json", action="store_true")
    report_parser = subparsers.add_parser("report-route", add_help=False)
    report_parser.add_argument("--json", action="store_true")
    report_parser.add_argument("--host")
    report_parser.add_argument("--route")
    report_parser.add_argument("--status")
    report_parser.add_argument("--source")
    report_parser.add_argument("--mesh-revision", dest="mesh_revision")
    report_parser.add_argument("--observed-at", dest="observed_at", type=int)
    return parser


def _mesh_main(args: Sequence[str], environ: Mapping[str, str], stdout: TextIO) -> int:
    parser = _mesh_parser()
    try:
        parsed = parser.parse_args(list(args))
    except (SystemExit, _MeshArgumentError):
        _write_error(stdout, "invalid_input", "invalid mesh command arguments")
        return 1
    if not parsed.json:
        _write_error(stdout, "invalid_input", "mesh commands require --json")
        return 1
    try:
        if parsed.command == "report-route":
            required = {
                "host": parsed.host,
                "route": parsed.route,
                "status": parsed.status,
                "source": parsed.source,
                "mesh revision": parsed.mesh_revision,
                "observed-at": parsed.observed_at,
            }
            missing = next(
                (label for label, value in required.items() if value is None), None
            )
            if missing is not None:
                raise MeshError("invalid_input", f"{missing} is required")
        mesh = load_mesh(environ)
        if parsed.command == "list":
            try:
                _json_write(stdout, mesh.to_dict())
            except _JsonOutputTooLarge:
                # An otherwise valid configuration can still exceed the
                # aggregate wire cap once all hosts/routes are rendered.
                _write_error(
                    stdout,
                    "invalid_config",
                    "Host Mesh response exceeds the stdout size limit",
                )
                return 1
            return 0
        accepted = report_route(
            mesh,
            host_id=parsed.host,
            route=parsed.route,
            status=parsed.status,
            source=parsed.source,
            mesh_revision=parsed.mesh_revision,
            observed_at=parsed.observed_at,
            health_store=RouteHealthStore(route_health_path(environ)),
        )
        _json_write(stdout, {"schemaVersion": 1, "ok": True, "accepted": accepted})
        return 0
    except MeshError as exc:
        _write_error(stdout, exc.code, exc.message)
        return 1
    except (MeshPersistenceError, OSError) as exc:
        _write_error(stdout, "persistence_failed", str(exc))
        return 1
    except (_JsonOutputTooLarge, _JsonEncodingError):
        _write_error(
            stdout,
            "persistence_failed",
            "Host Mesh response could not be encoded within the wire profile",
        )
        return 1
    except (TypeError, ValueError, UnicodeError) as exc:
        # Keep the public envelope consistent even if response construction
        # encounters an unexpected standard-library conversion failure.
        _write_error(stdout, "persistence_failed", str(exc))
        return 1
    except Exception as exc:  # pragma: no cover - defensive process boundary
        # No uncaught ordinary exception should turn into an unbounded Python
        # traceback on stderr or leave consumers without an exit envelope.
        _write_error(stdout, "persistence_failed", str(exc))
        return 1


def main(argv=None, *, environ=None, stdout=None):
    return _mesh_main(list(sys.argv[1:] if argv is None else argv),
                      os.environ if environ is None else environ,
                      sys.stdout if stdout is None else stdout)
