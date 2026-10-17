# Raw-log whitespace exception

Evidence commit `30e2011` preserves the original unittest log bytes. Its broad
`git diff --cached --check` reported trailing whitespace on the first lines of
`diagnostics/initial-before-314.log`, `results/before-311.log` and
`results/before-314.log`. Unittest emits a space after the test's `...` before
printing nested subtest results on the next line. These raw records are not
trimmed, because [receipt.json](receipt.json) and the original qualification
reports pin their exact bytes.

This exception applies only to those three raw-log lines. Runtime source,
Python evidence scripts, Markdown and JSON whitespace checks pass. The 116
design/link checks and Ruff pass; the canonical 407-test result and immutable
136-method-per-Python results retain their recorded inputs. This is an
evidence-format exception, not a source/test failure or broader acceptance.
