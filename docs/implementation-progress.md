# Implementation checkpoints

## Foundation: 0.1.0a1

The runtime package now implements strict candidate framing, transactional
state-product lifecycle guards, private same-user IPC and owned noninteractive
SSH stdio channels. Packaged schema resources preserve the reviewed candidate
bytes. Domain payload validation remains an adapter responsibility. Event
products reject setup until an accepted native codec is integrated.

Eight runtime tests cover hostile parsing, deadline quarantine, terminal
barriers, SSH command policy, real duplex IPC, pathname preservation and owned
listener cleanup. The original design suites remain independent oracles.

This checkpoint is transport infrastructure. It does not yet provide a client,
bridge command, Observer adapter, selected runtime or deployed migration.

Reproduce runtime tests after installing the package into a validation venv:

```sh
rtk proxy uv pip install --python .venv-design/bin/python --no-deps -e .
rtk proxy .venv-design/bin/python -m unittest discover -s tests -v
rtk proxy .venv-design/bin/ruff check src tests scripts
```
