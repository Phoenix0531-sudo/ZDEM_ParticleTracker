# ZDEM Particle Tracker

**Interactive 2D particle tracking for ZDEM discrete-element dumps — VisPy true-radius mesh discs, permanent IDs, explicit region policy.**

[English](README.md) | [中文](README.zh-CN.md)

[![CI](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker/actions/workflows/ci.yml/badge.svg)](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Research desktop app for **ZDEM** frame sequences (`all_*.dat` / deposition `_ini` frames). It is not a generic multi-physics GUI: the data path, renderer, and region rules are opinionated for salt-tectonics / granular DEM post-processing on Windows + Python.

## Preview

![ZDEM Particle Tracker](docs/screenshots/preview.png)

## Why this exists

| Pain | What this app does |
|------|---------------------|
| GL point sprites look “fat” or leave white halos / holes when zooming | Default renderer draws **mesh discs in real space** (`VisPyRenderer`), not `GL_POINTS` markers |
| Silent empty plots after a bad click | Click path fills **permanent particle IDs** through selection logic; failures are logged |
| Auto camera crop only on particle Y bbox hides walls / experiment box | `RegionDetector` + UI policy: **user lock > walls > metadata** |
| Multi-GB frame sets freeze the UI | Frame load worker, LRU frame cache, trajectory cancel + progress |

## Architecture (real packages)

```
main.py
zdem_particle_tracker/
  app.py                 # QApplication, Fusion style, APP_STYLESHEET (Apple-ish UI)
  config.py              # QSS
  parsers/
    dat_parser.py        # frame payload
    dat_scan.py          # scan all_*.dat / _ini series
  rendering/
    vispy_renderer.py    # GPU mesh discs, wall lines, selection, trajectory
    cpu_raster.py        # fallback path
    backend.py           # backend selection
  services/
    region_detector.py   # walls → bbox; metadata fallback
    trajectory_service.py
    export_service.py / quality_report.py / project_config.py
  widgets/
    main_viewer.py       # MainViewer entry
    selection_logic.py / viewer_logic.py
    series_plot.py
  ui/side_panels.py      # group legend, controls
  workers/frame_load_worker.py
  models/particle_data.py
  utils/frame_cache.py, color_mapping.py, logging_utils.py
```

Entry: `python main.py` → `zdem_particle_tracker.app.main` → `MainViewer`.

## Rendering details that matter

From `rendering/vispy_renderer.py`:

- Particles are **disc meshes** (`_DISC_SEGMENTS = 16`, reduced to 8 when far / dense)
- Viewport culling + optional decimation when particle count is large (`_MAX_DRAW_PARTICLES = 80000`)
- Mesh buffer reuse for frame scrubbing performance
- Walls drawn as line sets; selection / origin markers and trajectory polyline are first-class layers
- On Windows Qt, canvas uses `create_native()` **without** the broken `show=False/parent=self` pattern that mis-embeds VisPy

CPU / pyqtgraph path remains available for headless CI (`ZDEM_FORCE_PYQTGRAPH=1` in test docs/history).

## Region policy

`services/region_detector.py`:

1. `detect_from_walls(walls)` — walls array `(N, 4)` as `[x1,y1,x2,y2]`; unique endpoints → axis-aligned bbox; collinear / empty → fallback
2. `detect_from_metadata` — uses frame metadata `left` / `right` / `bottom` / `height`
3. UI layer can **user-lock** four bounds so temporary “fit particles” zoom does not become permanent experiment region

This matches the lab rule: **never treat particle Y-only bbox as the lasting experiment domain**.

## Tracking and performance

- Trajectory service supports cancelable workers and progress (see `tests/test_trajectory_cancel.py`)
- Frame loading is asynchronous (`workers/frame_load_worker.py`) with cache (`utils/frame_cache.py`)
- Color modes include **color#** group coloring (group legend panel), not only single-color scatter
- Project config can restore previously selected particle IDs after reload

## Install

```bash
git clone https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker.git
cd ZDEM_ParticleTracker
pip install -r requirements.txt
# pyproject: PySide6, numpy, pyqtgraph, scipy, matplotlib, scienceplots
# VisPy is required for the mesh path (install if missing in your env)
```

Python **>= 3.11**.

## Run

```bash
python main.py
# or
python -m zdem_particle_tracker
```

Headless / CI-oriented:

```bash
set QT_QPA_PLATFORM=offscreen
set ZDEM_FORCE_PYQTGRAPH=1
pytest tests/
```

Linux GitHub Actions constructs some Qt widgets in an **isolated subprocess** (`tests/qt_subprocess.py`) to avoid process-wide abort when mixing backends.

## Tests (what is actually covered)

| Area | Tests (examples) |
|------|------------------|
| DAT parse / scan | `test_dat_parser.py`, `test_dat_scan.py` |
| Selection / viewer pure logic | `test_selection_logic.py`, `test_viewer_logic.py`, `test_selection_gate.py` |
| Trajectory cancel | `test_trajectory_cancel.py` |
| Render / interaction | `test_render_pixels.py`, `test_interaction_paths.py`, `test_gui_smoke.py` |
| Perf paths | `test_perf_paths.py`, `test_deep_paths.py` |

## Related ZDEM tools

| Repo | Role |
|------|------|
| [ZDEM_Salt_Kinematics](https://github.com/Phoenix0531-sudo/ZDEM_Salt_Kinematics) | Post-process salt geometry metrics |
| [ZDEM_Area_Conservation](https://github.com/Phoenix0531-sudo/ZDEM_Area_Conservation) | Area conservation / triangulation |
| [ZDEM_Bond_Fracture](https://github.com/Phoenix0531-sudo/ZDEM_Bond_Fracture) | Bond damage series |
| [ZDEM_Model_Editor](https://github.com/Phoenix0531-sudo/ZDEM_Model_Editor) | Model file visual editor |

## Scope

- **In:** ZDEM 2D dumps, interactive ID tracking, true-radius display, region locks, export/report hooks
- **Out:** 3D solver UI, cloud collaboration, automatic constitutive inversion

## License

MIT. See [LICENSE](LICENSE).
