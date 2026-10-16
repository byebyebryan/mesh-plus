"""Do not return private reconstruction graphs through exception tracebacks."""

import asyncio
import re
import traceback
from functools import wraps

from ..protocol import ProtocolError, check
from .model import NativeTag


class MovedHead(ProtocolError):
    def __init__(self, tag):
        check(type(tag) is NativeTag, "sync_tag")
        super().__init__("sync_head_moved")
        self.tag = tag


def _retire_error(error):
    signal = type(error) if isinstance(error, (asyncio.CancelledError, KeyboardInterrupt, SystemExit, GeneratorExit)) else None
    detail = error.args[0] if len(error.args) == 1 and type(error.args[0]) is str else None
    code = (detail if detail is not None and len(detail) <= 128 and
            re.fullmatch(r"[a-z][a-z0-9_]{0,127}", detail) else "sync_admission_rejected")
    public = MovedHead(error.tag) if type(error) is MovedHead else None
    pending, seen = [error], set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        pending.extend(item for item in (current.__cause__, current.__context__) if item is not None)
        traceback.clear_frames(current.__traceback__)
        current.__traceback__ = current.__cause__ = current.__context__ = None
    return code, signal, public


def admission_boundary(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        code, signal, public = None, None, None
        try:
            return method(self, *args, **kwargs)
        except BaseException as error:
            code, signal, public = _retire_error(error)
        # No private method frame, native input buffer, original exception/cause
        # or staged graph escapes in the newly raised public error.
        args, kwargs = (), None
        if signal is not None:
            raise signal
        if public is not None:
            raise public
        raise ProtocolError(code)
    return call


def async_admission_boundary(method):
    @wraps(method)
    async def call(*args, **kwargs):
        code, signal, public = None, None, None
        try:
            return await method(*args, **kwargs)
        except BaseException as error:
            code, signal, public = _retire_error(error)
        args, kwargs = (), None
        if signal is not None:
            raise signal
        if public is not None:
            raise public
        raise ProtocolError(code)
    return call
