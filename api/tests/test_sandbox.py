"""Sandbox run: the sandbox runs the code [AN-04].

Agent-written animation code runs in a child process, with no network and
a time limit. It cannot start other programs or load native code. Nothing
here starts a job or calls the teaching agent.
"""

import os
from pathlib import Path

from polaris.sandbox import (
    NO_NETWORK_ERROR,
    NO_PROCESS_ERROR,
    TIME_LIMIT_ERROR,
    SandboxResult,
    run,
)

_NETWORK_CODE = """
from pathlib import Path
import socket
try:
    socket.create_connection(("127.0.0.1", 9), timeout=1)
except OSError as exc:
    Path("network.txt").write_text(f"{type(exc).__name__}: {exc}")
else:
    Path("network.txt").write_text("open")
"""


def test_the_sandbox_runs_the_code(tmp_path: Path, monkeypatch) -> None:
    """Scenario: the sandbox runs the code [AN-04]."""

    monkeypatch.setenv("POLARIS_NOT_FOR_THE_SANDBOX", "secret-value")
    code = """
from pathlib import Path
import os
Path("marker.txt").write_text(os.environ.get("POLARIS_NOT_FOR_THE_SANDBOX", ""))
Path("pid.txt").write_text(str(os.getpid()))
try:
    import polaris
except ImportError:
    Path("api.txt").write_text("absent")
else:
    Path("api.txt").write_text("present")
"""
    result = run(code, work_dir=tmp_path)

    assert result == SandboxResult(ok=True, error=None)
    assert (tmp_path / "marker.txt").read_text(encoding="utf-8") == ""
    assert (tmp_path / "pid.txt").read_text(encoding="utf-8") != str(os.getpid())
    assert (tmp_path / "api.txt").read_text(encoding="utf-8") == "absent"
    assert not (tmp_path / ".sandbox").exists()
    assert set(SandboxResult.__dataclass_fields__) == {"ok", "error"}


def test_the_sandbox_has_no_network(tmp_path: Path) -> None:
    """Scenario: the sandbox runs the code [AN-04]."""

    result = run(_NETWORK_CODE, work_dir=tmp_path)

    assert result.ok is True
    assert result.error is None
    outcome = (tmp_path / "network.txt").read_text(encoding="utf-8")
    assert outcome != "open"
    assert NO_NETWORK_ERROR in outcome


def test_the_sandbox_cannot_start_a_program(tmp_path: Path) -> None:
    """Scenario: the sandbox runs the code [AN-04]."""

    code = """
import subprocess
import sys
subprocess.run(
    [sys.executable, "-c", "open('child.txt', 'w').write('ran')"],
    check=True,
)
"""
    result = run(code, work_dir=tmp_path)

    assert result.ok is False
    assert result.error is not None
    assert NO_PROCESS_ERROR in result.error
    assert not (tmp_path / "child.txt").exists()


def test_the_sandbox_cannot_run_a_shell_command(tmp_path: Path) -> None:
    """Scenario: the sandbox runs the code [AN-04]."""

    code = """
import os
os.system("echo ran> system.txt")
"""
    result = run(code, work_dir=tmp_path)

    assert result.ok is False
    assert result.error is not None
    assert NO_PROCESS_ERROR in result.error
    assert not (tmp_path / "system.txt").exists()


def test_the_sandbox_cannot_load_native_code(tmp_path: Path) -> None:
    """Scenario: the sandbox runs the code [AN-04]."""

    code = """
from pathlib import Path
import os
import ctypes
ctypes.CDLL("kernel32" if os.name == "nt" else None)
Path("loaded.txt").write_text("yes")
"""
    result = run(code, work_dir=tmp_path)

    assert result.ok is False
    assert result.error is not None
    assert NO_PROCESS_ERROR in result.error
    assert not (tmp_path / "loaded.txt").exists()


def test_the_code_cannot_replace_the_sandbox_hook(tmp_path: Path) -> None:
    """Scenario: the sandbox runs the code [AN-04]."""

    code = """
from pathlib import Path
import subprocess
import sys

def allow(event, args):
    return None

runner = sys.modules["__main__"]
try:
    runner._audit.__code__ = allow.__code__
except OSError as exc:
    Path("hook.txt").write_text(str(exc))
try:
    subprocess.run([sys.executable, "-c", "pass"], check=True)
except OSError as exc:
    Path("program.txt").write_text(str(exc))
else:
    Path("program.txt").write_text("started")
"""
    result = run(code, work_dir=tmp_path)

    assert result == SandboxResult(ok=True, error=None)
    assert (tmp_path / "hook.txt").exists()
    program = (tmp_path / "program.txt").read_text(encoding="utf-8")
    assert program == NO_PROCESS_ERROR


def test_pure_python_animation_code_still_runs(tmp_path: Path) -> None:
    """Scenario: the sandbox runs the code [AN-04]."""

    code = """
from dataclasses import dataclass
from pathlib import Path
import html
import json
import math
import random
import textwrap


@dataclass
class Frame:
    x: float
    y: float


random.seed(4)
frames = [Frame(math.cos(i / 10), math.sin(i / 10)) for i in range(60)]
data = json.dumps([[f.x, f.y] for f in frames])
title = html.escape("Circle <motion>")
page = textwrap.dedent(f'''
    <!doctype html>
    <title>{title}</title>
    <script>const frames = {data};</script>
''')
Path("animation.html").write_text(page, encoding="utf-8")
"""
    result = run(code, work_dir=tmp_path)

    assert result == SandboxResult(ok=True, error=None)
    page = (tmp_path / "animation.html").read_text(encoding="utf-8")
    assert "Circle &lt;motion&gt;" in page
    assert "const frames = [[1.0, 0.0]" in page


def test_the_sandbox_enforces_a_time_limit(tmp_path: Path) -> None:
    """Scenario: the sandbox runs the code [AN-04]."""

    code = """
from pathlib import Path
import time
time.sleep(30)
Path("finished.txt").write_text("yes")
"""
    result = run(code, work_dir=tmp_path, time_limit_seconds=2)

    assert result == SandboxResult(ok=False, error=TIME_LIMIT_ERROR)
    assert not (tmp_path / "finished.txt").exists()


def test_a_failed_run_returns_the_error_without_the_code(tmp_path: Path) -> None:
    """A failed run returns text for the agent and leaves the code out."""

    code = "# SOURCE-SHOULD-STAY-OUT\nraise RuntimeError('animation failed')\n"
    result = run(code, work_dir=tmp_path)

    assert result.ok is False
    assert result.error is not None
    assert "animation failed" in result.error
    assert "SOURCE-SHOULD-STAY-OUT" not in result.error
    assert code not in result.error
    assert not (tmp_path / ".sandbox" / "animation.py").exists()


def test_the_same_work_dir_can_run_again(tmp_path: Path) -> None:
    failed = run("raise RuntimeError('first')\n", work_dir=tmp_path)
    assert failed.ok is False
    assert failed.error is not None
    assert "first" in failed.error

    again = run(
        "from pathlib import Path\nPath('again.txt').write_text('ok')\n",
        work_dir=tmp_path,
    )

    assert again == SandboxResult(ok=True, error=None)
    assert (tmp_path / "again.txt").read_text(encoding="utf-8") == "ok"


def test_empty_animation_code_fails(tmp_path: Path) -> None:
    result = run("  \n", work_dir=tmp_path)
    assert result == SandboxResult(ok=False, error="Animation code is empty.")
