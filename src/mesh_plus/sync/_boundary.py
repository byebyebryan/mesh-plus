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


def admission_boundary(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        code, signal, public = None, None, None
        try:
            return method(self, *args, **kwargs)
        except BaseException as error:
            if isinstance(error, (asyncio.CancelledError, KeyboardInterrupt, SystemExit, GeneratorExit)):
                signal = type(error)
            detail = error.args[0] if len(error.args) == 1 and type(error.args[0]) is str else None
            code = (detail if detail is not None and len(detail) <= 128 and
                    re.fullmatch(r"[a-z][a-z0-9_]{0,127}", detail) else "sync_admission_rejected")
            if type(error) is MovedHead:
                public = MovedHead(error.tag)
            pending, seen = [error], set()
            while pending:
                current = pending.pop()
                if id(current) in seen:
                    continue
                seen.add(id(current))
                pending.extend(item for item in (current.__cause__, current.__context__) if item is not None)
                traceback.clear_frames(current.__traceback__)
                current.__traceback__ = current.__cause__ = current.__context__ = None
            current = pending = seen = None
        # No private method frame, native input buffer, original exception/cause
        # or staged graph escapes in the newly raised public error.
        args, kwargs = (), None
        if signal is not None:
            raise signal
        if public is not None:
            raise public
        raise ProtocolError(code)
    return call
