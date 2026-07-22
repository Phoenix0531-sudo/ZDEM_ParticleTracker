"""Offline diagnostic: sample scan/parse/track + bug probes. Writes to app.log."""
from __future__ import annotations

import logging
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from zdem_particle_tracker.utils.logging_utils import setup_logging, get_logger, log_dir

SAMPLE = Path(r"D:/2_Temp/StructLab/Projects/25_造山带尺度盐构造/物理实验复刻/2/data")

issues: list[str] = []


def note(msg: str, level: str = "INFO"):
    print(f"[{level}] {msg}")
    if level in ("BUG", "WARN"):
        issues.append(f"{level}: {msg}")


def main():
    setup_logging(logging.DEBUG)
    log = get_logger("diag")
    log.info("===== self-diagnostic start =====")
    print("LOG", log_dir() / "app.log")

    from zdem_particle_tracker.parsers.dat_scan import (
        scan_dat_files,
        default_start_index,
        default_end_index,
        select_range,
        leading_ini_end_index,
    )
    from zdem_particle_tracker.parsers.dat_parser import (
        ParseMode,
        parse_dat_file,
        find_particle_in_file,
    )
    from zdem_particle_tracker.services.region_detector import RegionDetector
    from zdem_particle_tracker.services import FileInfo, TrajectoryService
    from zdem_particle_tracker.widgets.selection_logic import (
        id_allowed_at_session_start,
        pick_particle_id,
        play_parse_mode_name,
        validate_time_range_indices,
        filter_trajectory_path_xy,
    )
    from zdem_particle_tracker.services.quality_report import check_frame, check_file_list

    # --- dual entry bug probe ---
    from zdem_particle_tracker import app as app_mod
    from zdem_particle_tracker import __main__ as main_mod

    if not hasattr(main_mod, "main") or main_mod.main is not app_mod.main:
        # after fix they should share
        if getattr(main_mod, "main", None) is not app_mod.main:
            note("__main__.main is not app.main (entry divergence)", "BUG")
        else:
            note("entry points unified OK")
    else:
        note("entry points unified OK")

    if not SAMPLE.is_dir():
        note(f"sample missing: {SAMPLE}", "WARN")
        return 2

    # --- scan ---
    entries = scan_dat_files(str(SAMPLE))
    note(f"scan count={len(entries)} lead_ini={leading_ini_end_index(entries)}")
    if len(entries) < 2:
        note("too few DAT files", "BUG")
    si = default_start_index(entries)
    ei = default_end_index(entries)
    selected = select_range(entries, si, ei, 1)
    note(f"default session start={entries[si].name} end={entries[ei].name} active={len(selected)}")
    if not entries[si].is_ini and leading_ini_end_index(entries) >= 0:
        note("default start is not ini despite leading ini present", "BUG")

    # --- parse start + mid frames ---
    start_path = entries[si].path
    mid = selected[min(3, len(selected) - 1)].path
    for label, path, mode in [
        ("start FULL", start_path, ParseMode.FULL_PARTICLE_PROPERTIES),
        ("start BASIC", start_path, ParseMode.BASIC_FRAME),
        ("mid BASIC", mid, ParseMode.BASIC_FRAME),
    ]:
        t0 = time.perf_counter()
        pd = parse_dat_file(path, mode=mode)
        dt = time.perf_counter() - t0
        note(
            f"parse {label}: step={pd.current_step} count={pd.count} walls={len(pd.wall_data) if pd.wall_data is not None else 0} "
            f"ball_num={pd.ball_num} t={dt:.3f}s groups_unique={len(set(map(str, pd.groups))) if pd.count else 0}"
        )
        if pd.count == 0:
            note(f"empty parse {label} {path}", "BUG")
        if pd.ball_num and pd.count and pd.count != pd.ball_num:
            note(f"ball_num mismatch {label}: {pd.ball_num} vs {pd.count}", "WARN")
        # check ids unique
        if pd.count:
            nuniq = len(set(int(i) for i in pd.ids.tolist()))
            if nuniq != pd.count:
                note(f"duplicate ids {label}: unique={nuniq} count={pd.count}", "BUG")

    start_pd = parse_dat_file(start_path, mode=ParseMode.FULL_PARTICLE_PROPERTIES)
    start_ids = set(int(i) for i in start_pd.ids.tolist())
    pid = int(start_pd.ids[0])
    note(f"probe particle id={pid} group={start_pd.groups[0]} xy=({start_pd.xs[0]:.2f},{start_pd.ys[0]:.2f})")

    # region
    det = RegionDetector()
    meta = dict(left=start_pd.left, right=start_pd.right, bottom=start_pd.bottom, height=start_pd.height)
    reg_w = det.detect_from_walls(start_pd.wall_data, meta)
    reg_m = det.detect_from_metadata(meta)
    note(f"region walls: {reg_w}")
    note(f"region meta: {reg_m}")
    if reg_w is None:
        note("region walls returned None", "WARN")

    # quality
    fl = check_file_list([(e.step, e.path) for e in selected[:5]])
    note(f"file_list quality lines={len(fl.summary_lines())}")
    fr = check_frame(start_pd, filename_step=entries[si].step)
    note(f"frame quality: {fr.summary_lines()[:5]}")

    # pick gate
    picked = pick_particle_id(
        start_pd.xs, start_pd.ys, start_pd.rads, start_pd.ids,
        float(start_pd.xs[0]), float(start_pd.ys[0]),
        start_ids=start_ids,
    )
    if picked != pid:
        note(f"pick_particle_id expected {pid} got {picked}", "BUG")
    else:
        note("pick_particle_id OK")

    # find id mid file
    hit = find_particle_in_file(mid, pid)
    note(f"find mid found={hit.found} file_ok={hit.file_ok} step={hit.current_step} xy=({hit.x},{hit.y})")

    # trajectory extract (sync via worker wait — need QCoreApplication for QThread)
    from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

    app = QCoreApplication.instance() or QCoreApplication([])
    finfos = [
        FileInfo(
            file_order=i,
            filename_step=e.name,
            current_step=e.step,
            dat_path=e.path,
            file_size=os.path.getsize(e.path),
            status="pending",
        )
        for i, e in enumerate(selected[: min(6, len(selected))])
    ]
    svc = TrajectoryService()
    done = {"traj": None, "err": None}

    def on_done(tr):
        done["traj"] = tr
        app.quit()

    def on_err(m):
        done["err"] = m
        app.quit()

    w = svc.start(pid, finfos, max_workers=3)
    w.finished.connect(on_done)
    w.error.connect(on_err)
    # safety timeout
    QTimer.singleShot(120_000, app.quit)
    t0 = time.perf_counter()
    app.exec()
    dt = time.perf_counter() - t0
    if done["err"]:
        note(f"trajectory error: {done['err']}", "BUG")
    traj = done["traj"] or []
    n_ok = sum(1 for p in traj if p.status in ("normal", "present"))
    n_er = sum(1 for p in traj if p.status == "eroded")
    n_fe = sum(1 for p in traj if p.status == "file_error")
    note(f"trajectory points={len(traj)} ok={n_ok} eroded={n_er} fe={n_fe} t={dt:.2f}s")
    if len(traj) != len(finfos):
        # eroded still appends? if present all should match
        if n_er == 0 and n_fe == 0 and len(traj) != len(finfos):
            note(f"trajectory length {len(traj)} != files {len(finfos)}", "BUG")

    # kinematics sanity on first two present
    pts = [p for p in traj if p.status in ("normal", "present")]
    if len(pts) >= 2:
        p0, p1 = pts[0], pts[1]
        # first point displacement should be 0
        if abs(p0.displacement_total_km) > 1e-9:
            note(f"first traj point total disp not 0: {p0.displacement_total_km}", "BUG")
        if abs(p0.velocity_total) > 1e-12:
            note(f"first traj velocity not 0: {p0.velocity_total}", "BUG")
        # path length should be >= total displacement
        if p1.path_length_km + 1e-9 < p1.displacement_total_km:
            note(
                f"path_length < total_disp: path={p1.path_length_km} total={p1.displacement_total_km}",
                "BUG",
            )
        note(
            f"kin p0: disp={p0.displacement_total_km} v={p0.velocity_total}; "
            f"p1: dx={p1.displacement_x_km:.4g} path={p1.path_length_km:.4g} v={p1.velocity_total:.4g}"
        )

    # path filter
    xs, ys = filter_trajectory_path_xy(traj, path_to_current=True, current_step=pts[0].time_step if pts else 0)
    note(f"path clip first step only len={len(xs)}")

    # play mode names
    if play_parse_mode_name("group") != "FULL_PARTICLE_PROPERTIES":
        note("play_parse_mode_name group wrong", "BUG")
    if play_parse_mode_name("color_number") != "BASIC_FRAME":
        note("play_parse_mode_name color wrong", "BUG")

    # missing file behavior
    bad = find_particle_in_file(str(SAMPLE / "all_9999999999.dat"), pid)
    if bad.file_ok:
        note("missing file reported file_ok=True", "BUG")
    else:
        note("missing file file_ok=False OK")
    empty = parse_dat_file(str(SAMPLE / "all_9999999999.dat"), mode=ParseMode.BASIC_FRAME)
    if empty.count != 0:
        note("missing parse should be empty", "BUG")

    # --- known code probes ---
    # FileInfo field: trajectory uses finfo.dat_path - OK
    # __main__ title was different - fixed

    # probe: BASIC mode groups all ***
    basic = parse_dat_file(start_path, mode=ParseMode.BASIC_FRAME)
    if basic.count and len(set(map(str, basic.groups))) == 1 and str(basic.groups[0]) == "***":
        note("BASIC_FRAME groups all *** (expected — FULL needed for groups)", "INFO")

    # probe: session start id not in mid? still trackable by id stream
    mid_pd = parse_dat_file(mid, mode=ParseMode.BASIC_FRAME)
    if mid_pd.count and pid not in set(int(i) for i in mid_pd.ids.tolist()):
        note(f"pid {pid} missing in mid frame — possible erosion early", "WARN")

    # wall format
    if start_pd.wall_data is None or len(start_pd.wall_data) == 0:
        note("no walls in start frame", "WARN")
    else:
        note(f"walls shape={start_pd.wall_data.shape} sample={start_pd.wall_data[0].tolist()}")

    # height semantics
    note(f"meta left={start_pd.left} right={start_pd.right} bottom={start_pd.bottom} height={start_pd.height}")

    log.info("===== issues: %s =====", issues)
    print("\n==== SUMMARY ====")
    if issues:
        for i in issues:
            print(i)
        return 1
    print("No bugs found by automated probes.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise
