"""Fast parser for ZDEM all_*.dat files. Handles real ZDEM format and bracket format."""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

import numpy as np

from ..models.particle_data import ParticleData
from ..utils.logging_utils import get_logger

log = get_logger("parsers.dat_parser")


class ParseMode(Enum):
    """How much of the DAT file to read."""

    METADATA_ONLY = auto()
    BASIC_FRAME = auto()  # particles + walls, skip heavy contact sections
    FULL_PARTICLE_PROPERTIES = auto()  # + property table / groups
    FIND_SINGLE_PARTICLE = auto()  # stream until target id found


@dataclass
class SingleParticleHit:
    """Result of FIND_SINGLE_PARTICLE mode."""

    found: bool
    current_step: int = 0
    particle_id: int = 0
    index: int = -1
    x: float = float("nan")
    y: float = float("nan")
    rad: float = 0.0
    color: int = 0
    group: str = "***"
    source_path: str = ""
    file_ok: bool = True
    error: str = ""


def parse_dat_file(
    path: str,
    mode: ParseMode = ParseMode.FULL_PARTICLE_PROPERTIES,
    target_id: Optional[int] = None,
) -> ParticleData:
    """Parse a ZDEM all_*.dat file. Returns ParticleData.

    For FIND_SINGLE_PARTICLE use :func:`find_particle_in_file` instead.
    Missing/unreadable files return empty ParticleData (never raise).
    """
    if mode is ParseMode.FIND_SINGLE_PARTICLE:
        hit = find_particle_in_file(path, int(target_id or -1))
        pd = ParticleData()
        pd.current_step = hit.current_step
        if hit.found:
            pd.ids = np.array([hit.particle_id], dtype=np.int64)
            pd.indices = np.array([hit.index], dtype=np.int64)
            pd.xs = np.array([hit.x], dtype=np.float64)
            pd.ys = np.array([hit.y], dtype=np.float64)
            pd.rads = np.array([hit.rad], dtype=np.float64)
            pd.colors = np.array([hit.color], dtype=np.int32)
            pd.groups = np.array([hit.group], dtype=object)
            pd.ball_num = 1
        return pd

    t0 = time.perf_counter()
    log.debug("parse_dat_file begin path=%s mode=%s", path, getattr(mode, "name", mode))
    pd = ParticleData()
    section = None
    in_particles = False
    in_walls = False
    in_props = False
    wall_header = False
    prop_header = False
    p_idx, p_id, p_x, p_y, p_rad, p_col = [], [], [], [], [], []
    groups_by_id: dict[int, str] = {}
    wdata = []
    particle_lines = 0
    wall_lines = 0
    need_props = mode is ParseMode.FULL_PARTICLE_PROPERTIES
    need_particles = mode is not ParseMode.METADATA_ONLY
    need_walls = mode is not ParseMode.METADATA_ONLY

    try:
        fh = open(path, "r", encoding="utf-8", errors="replace")
    except OSError as e:
        log.warning("无法打开 DAT: %s (%s)", path, e)
        return pd

    with fh as f:
        for raw in f:
            line = raw.rstrip("\n\r")
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            lc = s.lower()

            new_section = None
            if lc.startswith("**"):
                new_section = lc.lstrip("*").strip()
            elif "parameter data" in lc:
                new_section = "metadata"
            elif "wall data" in lc and "contact" not in lc:
                new_section = "walls"
            elif "ball data" in lc:
                new_section = "particles"
            elif "contact data" in lc or "bond data" in lc:
                new_section = "skip"
            elif lc.startswith("[metadata]"):
                new_section = "metadata"
            elif lc.startswith("[walls]"):
                new_section = "walls"
            elif lc.startswith("[particles]") or lc.startswith("[particle_basic]"):
                new_section = "particles"
            elif lc.startswith("[properties]"):
                new_section = "properties"

            if new_section is not None:
                # Early exit: basic frame done after particles (+ walls already)
                if (
                    section == "particles"
                    and new_section in ("properties", "skip")
                    and not need_props
                    and particle_lines > 0
                ):
                    break
                if new_section == "skip" and mode is ParseMode.METADATA_ONLY:
                    break
                section = new_section
                in_particles = False
                in_walls = False
                in_props = False
                wall_header = False
                prop_header = False
                continue

            if section == "metadata":
                if ":" in s:
                    k, _, v = s.partition(":")
                    k = k.strip().lower()
                    v = v.strip()
                    try:
                        vals = v.split()
                        if k == "current_step":
                            pd.current_step = int(float(vals[0]))
                        elif k == "ball_num":
                            pd.ball_num = int(float(vals[0]))
                        elif k == "left":
                            pd.left = float(vals[0])
                        elif k == "right":
                            pd.right = float(vals[0])
                        elif k == "bottom":
                            pd.bottom = float(vals[0])
                        elif k in ("height", "top"):
                            pd.height = float(vals[0])
                    except Exception:
                        pass
                if mode is ParseMode.METADATA_ONLY and pd.current_step and pd.ball_num:
                    # keep scanning a bit for walls/params; exit on next major section handled above
                    pass

            elif section == "walls" and need_walls:
                if "wall num" in lc:
                    try:
                        pd.wall_count = int(float(s.split(":")[-1].strip()))
                    except Exception:
                        pass
                    continue
                if "p1[0]" in lc or ("p1" in lc.split() and "p2" in lc.split()):
                    in_walls = True
                    wall_header = True
                    continue
                if in_walls and ("xf" in lc or "kn" in lc) and "index" in lc:
                    in_walls = False
                    if mode is ParseMode.METADATA_ONLY:
                        break
                    section = "skip"
                    continue
                if in_walls and wall_header:
                    parts = s.split()
                    # Real ZDEM: index id P1[0] P1[1] P2[0] P2[1] ...
                    # Minimal / tests: x1 y1 x2 y2
                    try:
                        if len(parts) >= 6:
                            # Prefer index/id + endpoints when first two look integer-like
                            try:
                                int(float(parts[0]))
                                int(float(parts[1]))
                                x1 = float(parts[2])
                                y1 = float(parts[3])
                                x2 = float(parts[4])
                                y2 = float(parts[5])
                            except Exception:
                                x1 = float(parts[0])
                                y1 = float(parts[1])
                                x2 = float(parts[2])
                                y2 = float(parts[3])
                        elif len(parts) >= 4:
                            x1 = float(parts[0])
                            y1 = float(parts[1])
                            x2 = float(parts[2])
                            y2 = float(parts[3])
                        else:
                            continue
                        wdata.append([x1, y1, x2, y2])
                        wall_lines += 1
                        if pd.wall_count > 0 and wall_lines >= pd.wall_count:
                            in_walls = False
                    except Exception:
                        # Non-numeric line → end of wall data
                        in_walls = False

            elif section == "particles" and need_particles:
                if "ball num" in lc:
                    try:
                        pd.ball_num = int(float(s.split(":")[-1].strip()))
                    except Exception:
                        pass
                    continue
                if not in_particles:
                    tokens = lc.split()
                    if "index" in tokens and "id" in tokens and "rad" in tokens:
                        in_particles = True
                    continue

                parts = s.split()
                if len(parts) >= 6:
                    try:
                        vals = [float(p) for p in parts[:11]]
                        p_idx.append(int(vals[0]))
                        p_id.append(int(vals[1]))
                        p_x.append(vals[2])
                        p_y.append(vals[3])
                        p_rad.append(vals[4])
                        p_col.append(int(vals[5]))
                        particle_lines += 1
                        if pd.ball_num > 0 and particle_lines >= pd.ball_num:
                            if need_props:
                                section = "properties"
                                in_particles = False
                            else:
                                # BASIC_FRAME: stop after basic table
                                break
                    except Exception:
                        pass

            elif section == "properties" and need_props:
                if not in_props:
                    tokens = lc.split()
                    if "index" in tokens and "id" in tokens and (
                        "group" in tokens or "m" in tokens
                    ):
                        in_props = True
                        prop_header = True
                    continue
                if in_props and prop_header:
                    parts = s.split()
                    if len(parts) < 3:
                        continue
                    try:
                        pid = int(float(parts[1]))
                        group = parts[-1]
                        try:
                            float(group)
                            group = "***"
                        except ValueError:
                            pass
                        groups_by_id[pid] = group
                        # Early stop if we collected all ball groups
                        if pd.ball_num > 0 and len(groups_by_id) >= pd.ball_num:
                            break
                    except Exception:
                        if not parts[0].replace(".", "", 1).lstrip("-").isdigit():
                            section = "skip"
                            break

    pd.indices = np.array(p_idx, dtype=np.int64) if p_idx else np.array([], dtype=np.int64)
    pd.ids = np.array(p_id, dtype=np.int64) if p_id else np.array([], dtype=np.int64)
    pd.xs = np.array(p_x, dtype=np.float64) if p_x else np.array([], dtype=np.float64)
    pd.ys = np.array(p_y, dtype=np.float64) if p_y else np.array([], dtype=np.float64)
    pd.rads = np.array(p_rad, dtype=np.float64) if p_rad else np.array([], dtype=np.float64)
    pd.colors = np.array(p_col, dtype=np.int32) if p_col else np.array([], dtype=np.int32)

    if len(pd.ids) > 0:
        if groups_by_id:
            grp = [groups_by_id.get(int(i), "***") for i in pd.ids]
        else:
            grp = ["***"] * len(pd.ids)
        pd.groups = np.array(grp, dtype=object)
    else:
        pd.groups = np.array([], dtype=object)

    if wdata:
        pd.wall_data = np.array(wdata, dtype=np.float64)
    dt = time.perf_counter() - t0
    n = int(pd.count) if hasattr(pd, "count") else len(pd.ids)
    log.info(
        "parse_dat_file done path=%s mode=%s step=%s balls=%s walls=%s groups=%s t=%.3fs",
        os.path.basename(path),
        getattr(mode, "name", mode),
        pd.current_step,
        n,
        len(pd.wall_data) if getattr(pd, "wall_data", None) is not None else 0,
        len(set(map(str, pd.groups))) if n else 0,
        dt,
    )
    if pd.ball_num > 0 and n and n != int(pd.ball_num):
        log.warning(
            "ball_num mismatch path=%s declared=%s read=%s",
            os.path.basename(path),
            pd.ball_num,
            n,
        )
    return pd


def find_particle_in_file(path: str, target_id: int) -> SingleParticleHit:
    """Stream-parse DAT and stop as soon as permanent id is found.

    Does not build full particle arrays. Also returns group if property
    table is reached before end (best-effort).
    """
    hit = SingleParticleHit(
        found=False, particle_id=int(target_id), source_path=path, file_ok=True
    )
    t0 = time.perf_counter()
    try:
        section = None
        in_particles = False
        in_props = False
        ball_num = 0
        particle_lines = 0
        found_basic = False
        group = "***"

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                s = raw.strip()
                if not s or s.startswith("#"):
                    continue
                lc = s.lower()

                new_section = None
                if lc.startswith("**"):
                    new_section = lc.lstrip("*").strip()
                elif "parameter data" in lc:
                    new_section = "metadata"
                elif "wall data" in lc and "contact" not in lc:
                    new_section = "walls"
                elif "ball data" in lc:
                    new_section = "particles"
                elif "contact data" in lc or "bond data" in lc:
                    new_section = "skip"
                elif lc.startswith("[metadata]"):
                    new_section = "metadata"
                elif lc.startswith("[particles]") or lc.startswith("[particle_basic]"):
                    new_section = "particles"
                elif lc.startswith("[properties]"):
                    new_section = "properties"

                if new_section is not None:
                    # After particles, if found basic, try properties briefly
                    if section == "particles" and found_basic and new_section != "properties":
                        break
                    if found_basic and new_section in ("skip", "walls") and section == "properties":
                        break
                    section = new_section
                    in_particles = False
                    in_props = False
                    continue

                if section == "metadata" and ":" in s:
                    k, _, v = s.partition(":")
                    k = k.strip().lower()
                    try:
                        if k == "current_step":
                            hit.current_step = int(float(v.split()[0]))
                        elif k == "ball_num":
                            ball_num = int(float(v.split()[0]))
                    except Exception:
                        pass
                    continue

                if section == "particles":
                    if "ball num" in lc:
                        try:
                            ball_num = int(float(s.split(":")[-1].strip()))
                        except Exception:
                            pass
                        continue
                    if not in_particles:
                        tokens = lc.split()
                        if "index" in tokens and "id" in tokens and "rad" in tokens:
                            in_particles = True
                        continue
                    parts = s.split()
                    if len(parts) < 6:
                        continue
                    try:
                        vals = [float(p) for p in parts[:6]]
                        pid = int(vals[1])
                        particle_lines += 1
                        if pid == int(target_id):
                            hit.found = True
                            hit.index = int(vals[0])
                            hit.x = float(vals[2])
                            hit.y = float(vals[3])
                            hit.rad = float(vals[4])
                            hit.color = int(vals[5])
                            found_basic = True
                            # continue into properties if present for group
                            # but we can stop scanning particles
                            in_particles = False
                            section = "properties"
                            continue
                        if ball_num > 0 and particle_lines >= ball_num:
                            # not found in basic table
                            break
                    except Exception:
                        continue

                elif section == "properties" and found_basic:
                    if not in_props:
                        tokens = lc.split()
                        if "index" in tokens and "id" in tokens and (
                            "group" in tokens or "m" in tokens
                        ):
                            in_props = True
                        continue
                    parts = s.split()
                    if len(parts) < 3:
                        continue
                    try:
                        pid = int(float(parts[1]))
                        if pid != int(target_id):
                            continue
                        g = parts[-1]
                        try:
                            float(g)
                            g = "***"
                        except ValueError:
                            pass
                        group = g
                        hit.group = group
                        break
                    except Exception:
                        break

        hit.group = group
        return hit
    except FileNotFoundError as e:
        hit.file_ok = False
        hit.error = str(e)
        return hit
    except OSError as e:
        hit.file_ok = False
        hit.error = str(e)
        log.warning("find_particle open fail path=%s id=%s", path, target_id)
        return hit
    except Exception as e:
        hit.file_ok = False
        hit.error = str(e)
        log.debug("find_particle path=%s id=%s found=%s file_ok=%s t=%.3fs", os.path.basename(path), target_id, hit.found, hit.file_ok, time.perf_counter()-t0)
    return hit


def find_dat_files(directory: str) -> list[tuple[int, str]]:
    """Return sorted (step, path) for all_*.dat and all_*_ini.dat files.

    Thin wrapper over :func:`dat_scan.scan_dat_files` for backward
    compatibility. Prefer :mod:`dat_scan` when you need ``is_ini`` metadata.
    """
    from .dat_scan import scan_dat_files

    return [(e.step, e.path) for e in scan_dat_files(directory)]
