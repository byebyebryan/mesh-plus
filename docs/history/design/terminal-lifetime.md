# Terminal client and task lifetime

> Historical record. This document preserves its original checkpoint and may describe retired providers, interfaces or plans. Use the [current documentation](../../README.md) for supported setup and behavior.

This guide records a compatible implementation rule for terminal cleanup. It
does not change Delivery frames, SDK signatures, stream behavior or the frozen
contract lock.

When a `Client` reaches its first terminal failure, pending request futures and
subscription queues receive the exact original error, and each subscription's
ended event is signalled. The Client retains only a traceback-free immutable
diagnostic template. Exact `DeliveryError` and `ProtocolError` failures retain
their type, code and message when the strings fit the existing 128-character
code and 4096-character message bounds. Invalid or oversized metadata falls
back to a fresh `DeliveryError("channel_failed")` for later operations.
Template construction never calls methods on unknown exception types. The
diagnostic is internal and does not add text or fields to Delivery frames or
`Client.inspect()` output.

The failure path drains queued data and control frames using the existing byte
counters, then clears Client-owned request, operation and subscription
registries. The `Lifecycle` handle table remains intact, so channel-scoped
identifiers stay tombstoned. Caller-held futures, errors and subscriptions
retain their established behavior; a caller-held error can keep traceback
frames and their owners alive until that caller releases the error. Repeated
failure or close does not replace the first diagnostic or enqueue another copy.
After cleanup, private coroutine locals release completed futures, failed
admission handles, raised queue items and joined tasks that otherwise form a
reference cycle through a traceback. They do not clear or rewrite tracebacks.

Cleanup owners retrieve exceptions only from their own child tasks after those
tasks are cancelled and joined. For cancelled tasks, calling the public
`Task.exception()` method and handling its `CancelledError` releases the task's
stored cancellation traceback once no caller retains that error. This does not
clear or rewrite traceback objects, inspect the current caller task, or consume
exceptions from tasks that failed normally. Existing `finish_owned` waiting,
IO deadlines and non-cancellation failures retain their prior behavior.

Closing a `LineChannel` with an owned stdio subprocess first closes its input
writer. The child may exit naturally for up to 250 ms within one monotonic
one-second natural-exit-plus-TERM budget. If it remains alive, cleanup verifies
that the captured child is still the channel's owned process, sends TERM, and
waits only for the time left in that same budget. KILL and reap retain the
existing one-second bound. This gives a bridge time to consume a delivered
protocol close frame without extending the owned-process shutdown envelope.

The Bridge applies the same ownership rule to request, subscription, send,
iterator-close and channel-close work. It clears local child references only
after the owned work has joined. Repeated cancellation is deferred until
subscription iterator and channel cleanup have run; a genuine child failure
keeps precedence over that cancellation. Pending connection failures still
reach their existing caller, and their traceback objects are not modified.

## IPC server terminal ownership

`IPCServer` owns its handler and the private listener until terminal close has
stopped the listener and joined every accepted callback. `asyncio` retains the
server callback factory; the factory retains the bound `IPCServer._accept`
method. Before close, that path keeps the listener owner alive by design.

Close first marks the instance as closing so any late callback rejects its
channel without invoking the handler. It then joins active accept callbacks,
waits for the listener to finish closing, and joins any callback that entered
during that interval. Only after those steps does it release its listener and
handler references. This breaks the closed `asyncio.Server` callback cycle
without weakening the late-accept guard or dropping an in-flight handler during
cleanup. Caller-held handler references are unaffected.

The change is local to IPC resource ownership. Request/response framing,
wire schemas, endpoint paths, leases, client limits, and handler error behavior
remain unchanged. GC-disabled terminal-lifetime tests exercise zero-client
close, a successful direct Bridge request, a reset during a Bridge request,
and a handler whose cancellation cleanup is deliberately held open.

The focused coverage lives in `tests/test_terminal_lifetime.py`. It checks
terminal request and iterator delivery, preserved queue accounting and handle
tombstones, typed and fallback diagnostics, independent sibling clients,
caller-owned error/Subscription lifetime, GC-disabled retirement after failed
request and subscribe operations, repeated caller cancellation during child
cleanup, inner task failure identity, and Reader/Bridge/Client watch teardown
through local IPC.

The additional IPC listener tests exercise zero-client close, a successful
direct Bridge request, a reset during a Bridge request, and a handler whose
cancellation cleanup is deliberately held open.

## Stored stream errors

An asyncio stream can retain its original IO exception after the operation has
failed. Its traceback can consequently retain completed application frames.
After their actual cleanup has unwound, Bridge serve, request, subscription and
emit frames release the adapter, bound callbacks, publication and temporary
body references they no longer use. A failed `LineChannel.send` similarly
releases its temporary input and encoded buffer on exit. Live requests and
iterator cleanup keep their references until they have finished.

The original exception, errno and traceback remain unchanged; no exception or
private asyncio state is cleared. Tests keep a real StreamReader's reset and
its traceback alive while checking application-owner retirement, and retain a
failed writer's original error while checking temporary JSON-body release.
Caller-owned bodies remain alive while the caller retains them. This is an
application lifetime guarantee, not a claim that every internal asyncio object
retires without cyclic GC or that whole-process RSS has reached a plateau.
