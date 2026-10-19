# Terminal client and task lifetime

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

The focused coverage lives in `tests/test_terminal_lifetime.py`. It checks
terminal request and iterator delivery, preserved queue accounting and handle
tombstones, typed and fallback diagnostics, independent sibling clients,
caller-owned error/Subscription lifetime, GC-disabled retirement after failed
request and subscribe operations, repeated caller cancellation during child
cleanup, inner task failure identity, and Reader/Bridge/Client watch teardown
through local IPC.
