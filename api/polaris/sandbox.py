"""The sandbox where agent-written animation code runs.

AN-04: that code runs here, with no network and a time limit. A run does
not start a job and does not call the teaching agent. Each call is one
run. Counting fixes belongs to the caller.

The result is for that caller. It is not a learner-visible payload, and
it never includes the code. ``error`` goes back to the agent. Do not copy
it onto a job.

The child process runs an audit hook. It denies sockets, starting other
programs, and loading native code through ctypes, so the code cannot ask
another program or a native library to reach the network for it.

Audit hooks are not a full sandbox. Known holes:

- The import system can load a native extension module from any file the
  code writes. That load raises no audit event, and native code can open
  sockets and start programs.
- Opening a UNC path such as ``\\\\host\\share`` reaches the network
  through Windows file sharing.
- The code can read and write files outside ``work_dir``.

Closing these needs isolation from the operating system, not this hook.
"""

from __future__ import annotations

import math
import os
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# The feature doc requires a time limit and does not give its length.
DEFAULT_TIME_LIMIT_SECONDS = 120

TIME_LIMIT_ERROR = (
    "The sandbox stopped this run because the animation code passed the time limit."
)

NO_NETWORK_ERROR = "The sandbox has no network."

NO_PROCESS_ERROR = "The sandbox cannot start other programs or load native code."

_LOCKED_ERROR = "The sandbox does not allow replacing function code."

_EMPTY_CODE_ERROR = "Animation code is empty."

_FAILED_ERROR = "The animation code failed."

_ERROR_LIMIT = 8000

_PRIVATE_DIR = ".sandbox"

# Installed in the child before the animation code. Audit hooks stay in
# place for the life of that process, including after the code reloads
# the socket module.
#
# The code can reach this module through sys.modules["__main__"], so the
# hook reads no module globals. Its messages and event names are literals,
# and replacing any function's code is denied so the hook keeps its body.
#
# Event names come from the CPython audit events table at
# https://docs.python.org/3/library/audit_events.html. Some are raised
# only on POSIX and some only on Windows.
_RUNNER = """
import sys


def _audit(event, args):
    if event.startswith("socket."):
        raise OSError(__NO_NETWORK__)
    if event.startswith("ctypes.") or event in {
        "subprocess.Popen",
        "os.system",
        "os.exec",
        "os.spawn",
        "os.posix_spawn",
        "os.startfile",
        "os.startfile/2",
        "os.fork",
        "os.forkpty",
        "pty.spawn",
        "_winapi.CreateProcess",
        "_posixsubprocess.fork_exec",
    }:
        raise OSError(__NO_PROCESS__)
    if event == "object.__setattr__" and args[1] == "__code__":
        raise OSError(__LOCKED__)


sys.addaudithook(_audit)

if __name__ == "__main__":
    code_path = sys.argv[1]
    with open(code_path, encoding="utf-8") as handle:
        source = handle.read()
    compiled = compile(source, code_path, "exec")
    exec(compiled, {"__name__": "__main__", "__file__": code_path})
"""


@dataclass(frozen=True)
class SandboxResult:
    """Outcome of one sandbox run.

    Success is ``ok=True`` and ``error=None``.
    Failure is ``ok=False`` and ``error`` set to text for the agent.
    """

    ok: bool
    error: str | None = None

    def __post_init__(self) -> None:
        if self.ok and self.error is not None:
            raise ValueError("A successful sandbox run has no error.")
        if not self.ok and not self.error:
            raise ValueError("A failed sandbox run includes an error.")


def run(
    code: str,
    *,
    work_dir: Path | str,
    time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS,
) -> SandboxResult:
    """Run animation code in the sandbox.

    Success returns ``SandboxResult(ok=True, error=None)``.
    Failure returns ``SandboxResult(ok=False, error=<text for the agent>)``.
    A time limit failure uses ``TIME_LIMIT_ERROR``. Any other failure uses
    the code's error text, with the submitted code removed.

    ``work_dir`` is the directory the code runs in. Files it writes land
    there. This call blocks until the code finishes or the time limit
    stops it.
    """

    if not isinstance(code, str):
        raise TypeError("Animation code must be a string.")
    if not math.isfinite(time_limit_seconds) or time_limit_seconds <= 0:
        raise ValueError("The time limit must be a positive number of seconds.")
    if not code.strip():
        return SandboxResult(ok=False, error=_EMPTY_CODE_ERROR)

    root = Path(work_dir)
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    private = root / _PRIVATE_DIR
    private.mkdir(exist_ok=True)
    code_path = private / "animation.py"
    runner_path = private / "runner.py"
    code_path.write_text(code, encoding="utf-8", newline="\n")
    runner_path.write_text(_runner_source(), encoding="utf-8", newline="\n")
    try:
        return _execute(
            runner_path,
            code_path,
            root,
            code,
            time_limit_seconds,
        )
    finally:
        _remove_private(private)


def _runner_source() -> str:
    return (
        _RUNNER.replace("__NO_NETWORK__", repr(NO_NETWORK_ERROR))
        .replace("__NO_PROCESS__", repr(NO_PROCESS_ERROR))
        .replace("__LOCKED__", repr(_LOCKED_ERROR))
    )


def _execute(
    runner_path: Path,
    code_path: Path,
    work_dir: Path,
    code: str,
    time_limit_seconds: float,
) -> SandboxResult:
    proc = subprocess.Popen(
        [sys.executable, "-s", "-P", str(runner_path), str(code_path)],
        cwd=work_dir,
        env=_child_env(work_dir),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        **_popen_flags(),
    )
    try:
        _stdout, stderr = proc.communicate(timeout=time_limit_seconds)
    except subprocess.TimeoutExpired:
        _kill(proc)
        return SandboxResult(ok=False, error=TIME_LIMIT_ERROR)
    if proc.returncode == 0:
        return SandboxResult(ok=True, error=None)
    return SandboxResult(ok=False, error=_error_text(stderr or "", code))


def _child_env(work_dir: Path) -> dict[str, str]:
    """Environment for the child. Parent secrets are not copied."""

    names = (
        "SYSTEMROOT",
        "WINDIR",
        "SYSTEMDRIVE",
        "PATH",
        "PATHEXT",
        "COMSPEC",
        "HOMEDRIVE",
        "HOMEPATH",
        "USERPROFILE",
    )
    env = {name: os.environ[name] for name in names if os.environ.get(name)}
    env["TEMP"] = str(work_dir)
    env["TMP"] = str(work_dir)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONSAFEPATH"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _popen_flags() -> dict[str, object]:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {"start_new_session": True}


def _kill(proc: subprocess.Popen[str]) -> None:
    """Stop the sandbox process and programs it started."""

    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    try:
        proc.kill()
    except OSError:
        pass
    try:
        proc.communicate(timeout=5)
    except (subprocess.TimeoutExpired, OSError, ValueError):
        pass


def _error_text(stderr: str, code: str) -> str:
    text = stderr.replace(code, "").strip()
    if not text:
        return _FAILED_ERROR
    if len(text) > _ERROR_LIMIT:
        return text[-_ERROR_LIMIT:]
    return text


def _remove_private(private: Path) -> None:
    for name in ("animation.py", "runner.py"):
        (private / name).unlink(missing_ok=True)
    try:
        private.rmdir()
    except OSError:
        return
