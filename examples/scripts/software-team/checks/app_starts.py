"""The app starts, answers HTTP on its port, and stops (D55).

    python app_starts.py --port P [--path /] [--wait 30] -- <the project's start command>...

Starts the command with PORT=P in its environment, waits until http://127.0.0.1:P<path> answers with any status
below 500, then stops the command and everything it started. Exits 0 when it answered within --wait seconds, and 1
when it didn't, or exited first.
"""

import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


def answered(url: str) -> int | None:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status
    except urllib.error.HTTPError as e:
        return e.code
    except OSError:
        return None


def main(args: list[str]) -> int:
    port, path, wait = None, "/", 30
    while args and args[0] != "--":
        flag, value, args = args[0], args[1], args[2:]
        if flag == "--port":
            port = int(value)
        elif flag == "--path":
            path = value
        elif flag == "--wait":
            wait = int(value)
    if port is None or len(args) < 2:
        print("usage: app_starts.py --port P [--path /] [--wait 30] -- <command>...")
        return 2
    url = f"http://127.0.0.1:{port}{path}"
    log = tempfile.TemporaryFile()  # a file, not a pipe: an app that prints a lot never blocks on it
    proc = subprocess.Popen(args[1:], env={**os.environ, "PORT": str(port)}, stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True)
    try:
        until = time.monotonic() + wait
        while time.monotonic() < until:
            if proc.poll() is not None:
                log.seek(0)
                print(log.read().decode(errors="replace")[-3000:])
                print(f"the app exited with code {proc.returncode} before answering at {url}")
                return 1
            status = answered(url)
            if status is not None and status < 500:
                print(f"the app answered at {url} with HTTP {status}")
                return 0
            time.sleep(0.3)
        print(f"the app didn't answer at {url} within {wait} s")
        return 1
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proc.wait()
        log.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
