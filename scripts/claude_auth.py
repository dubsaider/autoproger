#!/usr/bin/env python3
"""
Checks Claude Code auth status and runs /login interactively via pty if needed.
Output (including the OAuth URL) is streamed to stdout so it appears in docker logs.
"""
import os
import pty
import subprocess
import sys


def is_authenticated() -> bool:
    try:
        result = subprocess.run(
            ["claude", "-p", "ping", "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0
    except Exception:
        return False


def run_login() -> bool:
    print("=" * 60, flush=True)
    print("Claude Code: not authenticated.", flush=True)
    print("Starting /login — open the URL below in your browser.", flush=True)
    print("=" * 60, flush=True)

    master_fd, slave_fd = pty.openpty()
    proc = subprocess.Popen(
        ["claude", "/login"],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
    )
    os.close(slave_fd)

    while True:
        try:
            data = os.read(master_fd, 1024)
            if data:
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
        except OSError:
            break

    proc.wait()
    os.close(master_fd)

    if proc.returncode == 0:
        print("\nClaude Code authenticated successfully.", flush=True)
        return True
    else:
        print("\nAuthentication failed (exit code %d)." % proc.returncode, flush=True)
        return False


if __name__ == "__main__":
    if is_authenticated():
        print("Claude Code: already authenticated.", flush=True)
        sys.exit(0)

    ok = run_login()
    sys.exit(0 if ok else 1)
