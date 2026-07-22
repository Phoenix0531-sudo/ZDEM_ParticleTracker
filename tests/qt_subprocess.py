"""Run Qt-sensitive checks in an isolated process.

Linux GitHub runners can abort (exit 134) when QWidget is created in the
same process that already imported PySide6 OpenGL / pyqtgraph / scipy.
Isolating the construct path keeps CI hard while avoiding process-wide
Qt state pollution.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Mapping, Optional


ROOT = Path(__file__).resolve().parents[1]


def run_qt_script(
    code: str,
    *,
    timeout: float = 90.0,
    extra_env: Optional[Mapping[str, str]] = None,
) -> subprocess.CompletedProcess:
    """Execute *code* under offscreen Qt + forced PyQtGraph."""
    body = textwrap.dedent(code)
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["ZDEM_FORCE_PYQTGRAPH"] = "1"
    env["MPLBACKEND"] = "Agg"
    # Prefer a known font set when available (CI installs fonts-dejavu-core).
    env.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false")
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    if extra_env:
        env.update({k: str(v) for k, v in extra_env.items()})
    return subprocess.run(
        [sys.executable, "-c", body],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        cwd=str(ROOT),
    )


def assert_qt_script_ok(test_case, code: str, marker: str = "SUBPROC_OK", **kwargs) -> None:
    r = run_qt_script(code, **kwargs)
    if r.returncode != 0 or marker not in (r.stdout or ""):
        test_case.fail(
            f"qt subprocess failed code={r.returncode}\n"
            f"stdout={r.stdout}\nstderr={r.stderr}"
        )
