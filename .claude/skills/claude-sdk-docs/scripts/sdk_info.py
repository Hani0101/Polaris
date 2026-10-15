"""Report the installed claude-agent-sdk version, the latest on PyPI, and where it lives.

Run with the project's interpreter so it inspects the right environment:

    E:\\Polaris\\.venv\\Scripts\\python.exe sdk_info.py

Stdlib only. The PyPI lookup is best effort; offline just skips it.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from importlib import metadata

PACKAGE = "claude-agent-sdk"
MODULE = "claude_agent_sdk"


def installed() -> tuple[str | None, str | None]:
    try:
        version = metadata.version(PACKAGE)
    except metadata.PackageNotFoundError:
        return None, None
    try:
        module = __import__(MODULE)
        path = str(module.__path__[0])
    except Exception:
        path = None
    return version, path


def latest_on_pypi() -> str | None:
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{PACKAGE}/json", timeout=8) as resp:
            return json.load(resp)["info"]["version"]
    except Exception:
        return None


def main() -> int:
    version, path = installed()
    latest = latest_on_pypi()

    print(f"interpreter : {sys.executable}")
    if version is None:
        print(f"installed   : {PACKAGE} is NOT installed in this interpreter")
    else:
        print(f"installed   : {PACKAGE} {version}")
        print(f"source path : {path}")
    print(f"latest PyPI : {latest or 'unknown (offline?)'}")

    if version and latest and version != latest:
        print(f"note        : installed is not the latest; docs describe the latest ({latest}), "
              "so confirm names against the source path before using newer options.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
