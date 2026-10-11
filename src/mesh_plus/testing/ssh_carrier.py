"""Disposable non-root localhost SSH; no operational SSH configuration edits."""

import asyncio
import contextlib
import json
import os
import pwd
import shlex
import shutil
import socket

from ..transport import finish_owned, ssh_argv, subprocess_channel


async def _stop(process):
    async def retire():
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 3)
            except TimeoutError:
                process.kill()
                await asyncio.wait_for(process.wait(), 3)
    await finish_owned(asyncio.create_task(retire()))


async def _spawn(*argv, **kwargs):
    creation = asyncio.create_task(asyncio.create_subprocess_exec(*argv, **kwargs))
    try:
        return await finish_owned(creation)
    except BaseException:
        if creation.done() and not creation.cancelled() and creation.exception() is None:
            await _stop(creation.result())
        raise


@contextlib.asynccontextmanager
async def ssh_server(directory, command, source):
    """One owned daemon with independently owned reconnectable channels."""
    for name in ("host", "client"):
        child = await _spawn("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(directory / name))
        try:
            if await child.wait() != 0:
                raise RuntimeError("owned key generation failed")
        finally:
            await _stop(child)
    nonce = "b" * 32
    wrapper = f"printf '\\036ROFI_PLUS_REACHED_V1:{nonce}\\037\\n' >&2; exec " + shlex.join(command)
    wrapper_path = directory / "bridge.sh"
    wrapper_path.write_text("#!/bin/sh\n" + wrapper + "\n")
    wrapper_path.chmod(0o700)
    authorized = directory / "authorized_keys"
    authorized.write_text("restrict,command=" + json.dumps(shlex.join([str(wrapper_path)])) + " " + (directory / "client.pub").read_text())
    authorized.chmod(0o600)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    user = pwd.getpwuid(os.getuid()).pw_name
    config = directory / "sshd.conf"
    config.write_text(f"Port {port}\nListenAddress 127.0.0.1\nHostKey {directory / 'host'}\nPidFile {directory / 'sshd.pid'}\n"
                      f"AuthorizedKeysFile {authorized}\nUsePAM no\nPasswordAuthentication no\nKbdInteractiveAuthentication no\n"
                      f"PubkeyAuthentication yes\nStrictModes yes\nPermitRootLogin no\nAllowUsers {user}\n"
                      "AllowTcpForwarding no\nAllowAgentForwarding no\nX11Forwarding no\nPermitTTY no\nLogLevel ERROR\n")
    host_key = (directory / "host.pub").read_text().split()
    known = directory / "known_hosts"
    known.write_text(f"[127.0.0.1]:{port} {host_key[0]} {host_key[1]}\n")
    log = directory / "sshd.log"
    daemon = await _spawn(shutil.which("sshd"), "-D", "-f", str(config), "-E", str(log),
                                                 stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.DEVNULL,
                                                 stderr=asyncio.subprocess.DEVNULL)
    try:
        for _ in range(80):
            if daemon.returncode is not None:
                raise RuntimeError("isolated sshd startup failed")
            try:
                _reader, writer = await asyncio.open_connection("127.0.0.1", port)
                writer.close()
                await writer.wait_closed()
                break
            except OSError:
                await asyncio.sleep(.025)
        else:
            raise RuntimeError("isolated sshd readiness failed")
        argv = ssh_argv(user + "@127.0.0.1", source, nonce=nonce)
        argv[1:1] = ["-F", "/dev/null", "-p", str(port), "-i", str(directory / "client"),
                      "-o", "IdentitiesOnly=yes", "-o", "IdentityAgent=none", "-o", "GlobalKnownHostsFile=/dev/null",
                      "-o", "UserKnownHostsFile=" + str(known)]
        async def connect():
            return await subprocess_channel(argv, reached_nonce=nonce)
        yield connect
    finally:
        await _stop(daemon)


@contextlib.asynccontextmanager
async def ssh_channel(directory, command, source):
    async with ssh_server(directory, command, source) as connect:
        channel = await connect()
        try:
            yield channel
        finally:
            await channel.close()
