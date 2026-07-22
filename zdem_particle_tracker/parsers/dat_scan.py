"""DAT experiment directory scanning and session range selection.

ZDEM deposition phase dumps use the ``_ini`` suffix, e.g.::

    all_0000000000_ini.dat
    all_0000003000_ini.dat
    all_0000006000_ini.dat   ← last leading _ini  (= default session start)
    all_0000026000.dat       ← formal experiment frames
    ...

Leading consecutive ``*_ini.dat`` files (before the first non-ini) are the
deposition phase.  Default analysis start = last of that leading prefix.
Later mid-run ``*_ini`` restart dumps are NOT treated as deposition.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple


_DAT_NAME = re.compile(r"^all_(\d+)(_ini)?\.dat$", re.IGNORECASE)


@dataclass(frozen=True)
class DatFileEntry:
    """One all_*.dat (or all_*_ini.dat) file in an experiment directory."""

    step: int
    path: str
    is_ini: bool
    name: str

    @property
    def label(self) -> str:
        """Human-readable step label for comboboxes."""
        return f"{self.step} · ini" if self.is_ini else str(self.step)

    def as_tuple(self) -> Tuple[int, str]:
        """Backward-compatible (step, path)."""
        return self.step, self.path


def scan_dat_files(directory: str) -> List[DatFileEntry]:
    """Non-recursive scan. Sort by (step, ini-first)."""
    out: List[DatFileEntry] = []
    if not os.path.isdir(directory):
        return out
    for e in os.scandir(directory):
        if not e.is_file():
            continue
        m = _DAT_NAME.match(e.name)
        if not m:
            continue
        step = int(m.group(1))
        is_ini = m.group(2) is not None
        out.append(
            DatFileEntry(step=step, path=e.path, is_ini=is_ini, name=e.name)
        )
    # ini before non-ini at the same step (restart dump ordering)
    out.sort(key=lambda x: (x.step, 0 if x.is_ini else 1, x.name.lower()))
    return out


def leading_ini_end_index(entries: Sequence[DatFileEntry]) -> int:
    """Index of the last file in the leading ``_ini`` deposition prefix.

    Returns -1 if there is no leading ini file.
    """
    last = -1
    for i, e in enumerate(entries):
        if e.is_ini:
            last = i
        else:
            break
    return last


def default_start_index(entries: Sequence[DatFileEntry]) -> int:
    """Default analysis start: last leading ``_ini``, else 0."""
    li = leading_ini_end_index(entries)
    return li if li >= 0 else 0


def default_end_index(entries: Sequence[DatFileEntry]) -> int:
    return max(0, len(entries) - 1)


def index_for_step(
    entries: Sequence[DatFileEntry],
    step: int,
    prefer_ini: Optional[bool] = None,
) -> int:
    """Find first index with matching step. prefer_ini: True/False/None."""
    for i, e in enumerate(entries):
        if e.step != step:
            continue
        if prefer_ini is None or e.is_ini is prefer_ini:
            return i
    for i, e in enumerate(entries):
        if e.step == step:
            return i
    return -1


def select_range(
    entries: Sequence[DatFileEntry],
    start_index: int,
    end_index: int,
    stride: int = 1,
) -> List[DatFileEntry]:
    """Slice [start_index, end_index] inclusive, then take every *stride* file.

    Always includes the start file. Stride < 1 is treated as 1.
    """
    if not entries:
        return []
    n = len(entries)
    s = max(0, min(int(start_index), n - 1))
    e = max(0, min(int(end_index), n - 1))
    if e < s:
        s, e = e, s
    stride = max(1, int(stride))
    chunk = list(entries[s : e + 1])
    if stride == 1:
        return chunk
    selected = chunk[::stride]
    # Ensure last frame is present if user selected it as end
    if chunk and (not selected or selected[-1] is not chunk[-1]):
        selected.append(chunk[-1])
    return selected


def entries_to_tuples(entries: Iterable[DatFileEntry]) -> List[Tuple[int, str]]:
    return [e.as_tuple() for e in entries]
