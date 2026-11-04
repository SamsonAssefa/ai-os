"""Opt-in, network-isolated runner for reviewed, digest-pinned plugin images."""
import json
import os
import re
import shutil
import subprocess
import threading


class SandboxError(RuntimeError):
    pass


def execute(image, payload, timeout=20):
    if os.getenv("AIOS_ENABLE_SANDBOX") != "1":
        raise SandboxError("isolated runner is disabled; set AIOS_ENABLE_SANDBOX=1")
    if not re.fullmatch(r"[A-Za-z0-9./:_-]+@sha256:[0-9a-f]{64}", image or ""):
        raise SandboxError("runner requires a digest-pinned image")
    if not shutil.which("docker"):
        raise SandboxError("Docker is not installed")
    raw = json.dumps(payload, separators=(",", ":"))
    if len(raw.encode()) > 65536:
        raise SandboxError("plugin input exceeds 64 KiB")
    command = [
        "docker", "run", "--rm", "--pull", "never", "--interactive",
        "--network", "none", "--read-only", "--user", "65534:65534",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--pids-limit", "64", "--memory", "128m", "--cpus", "0.5",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m", image,
    ]
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
    except OSError as exc:
        raise SandboxError("could not start the isolated runner") from exc
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    overflow = threading.Event()

    def drain(name, stream):
        while True:
            chunk = stream.read(8192)
            if not chunk:
                return
            target = buffers[name]
            if len(target) + len(chunk) > 65536:
                overflow.set()
                try:
                    process.kill()
                except OSError:
                    pass
                return
            target.extend(chunk)

    readers = [threading.Thread(target=drain, args=(name, stream), daemon=True)
               for name, stream in (("stdout", process.stdout), ("stderr", process.stderr))]
    for reader in readers:
        reader.start()
    def send_input():
        try:
            process.stdin.write(raw.encode())
            process.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    writer = threading.Thread(target=send_input, daemon=True)
    writer.start()
    try:
        process.wait(timeout=max(1, min(int(timeout), 30)))
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait()
        raise SandboxError("plugin exceeded the execution time limit") from exc
    except OSError as exc:
        process.kill()
        process.wait()
        raise SandboxError("could not send input to the isolated runner") from exc
    finally:
        writer.join(timeout=1)
        for reader in readers:
            reader.join(timeout=1)
        for stream in (process.stdout, process.stderr):
            stream.close()
    if overflow.is_set():
        raise SandboxError("plugin output exceeds 64 KiB")
    stdout = buffers["stdout"].decode("utf-8", errors="replace")
    stderr = buffers["stderr"].decode("utf-8", errors="replace")
    if process.returncode:
        raise SandboxError(f"plugin exited with status {process.returncode}: {stderr[:1000]}")
    return stdout
