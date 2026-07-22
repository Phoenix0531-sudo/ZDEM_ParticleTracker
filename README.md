# ZDEM Particle Tracker

**High-performance 2D particle tracking with VisPy true-radius rendering**

[English](README.md) | [中文](README.zh-CN.md)

![CI](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)

Desktop viewer and **single-particle trajectory tracker** for 2D **ZDEM** discrete-element dumps on Windows / Python.

Research workflow tool — not a generic DEM GUI. It understands `all_*.dat` / `all_*_ini.dat`, permanent particle IDs, **color#** groups, wall columns (P1/P2), and deposition (`_ini`) framing.

## Why this exists

Salt-tectonics / orogenic DEM campaigns need interactive ID picking, region locks, and honest radius rendering. Marker-based GL points create white halos and zoom voids; this app prefers **VisPy mesh discs at true 2×radius**, with pyqtgraph fallback for headless CI.

## Features

- VisPy mesh rendering (true radius); `ZDEM_FORCE_PYQTGRAPH=1` forces CPU path
- Region bounds: user lock > walls > metadata (never auto-crop only to particle Y bbox as permanent policy)
- Trajectory tracking with cancelable workers + progress
- Rotating logs / parse timings / self-diagnostics
- Hard CI: Qt widget construction via **isolated subprocess** on Linux

## Install

```bash
git clone https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker.git
cd ZDEM_ParticleTracker
pip install -r requirements.txt
# VisPy + PySide6 + numpy/scipy recommended
```

## Usage

```bash
python main.py
```

Headless-friendly env for tests:

```bash
set QT_QPA_PLATFORM=offscreen
set ZDEM_FORCE_PYQTGRAPH=1
pytest tests/
```

## Project layout

```
main.py
zdem_particle_tracker/
  widgets/main_viewer.py
  ui/side_panels.py
  selection_logic.py viewer_logic.py
  rendering/
tests/qt_subprocess.py
```

## Related ZDEM tools

| Repo | Role |
|------|------|
| [ZDEM_ParticleTracker](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker) | Interactive particle tracking + VisPy true-radius render |
| [ZDEM_Salt_Kinematics](https://github.com/Phoenix0531-sudo/ZDEM_Salt_Kinematics) | Salt geometry / kinematics extraction & plots |
| [ZDEM_Area_Conservation](https://github.com/Phoenix0531-sudo/ZDEM_Area_Conservation) | Area-conservation / triangulation analysis |
| [ZDEM_Bond_Fracture](https://github.com/Phoenix0531-sudo/ZDEM_Bond_Fracture) | Bond damage series + desktop / CLI |
| [ZDEM_Damage_Thresholds](https://github.com/Phoenix0531-sudo/ZDEM_Damage_Thresholds) | Damage thresholds & strain–energy plots |
| [ZDEM_DFN](https://github.com/Phoenix0531-sudo/ZDEM_DFN) | Discrete fracture network generator for ZDEM |
| [ZDEM_Model_Editor](https://github.com/Phoenix0531-sudo/ZDEM_Model_Editor) | Model file visual editor |
| [ZDEM_Archiver](https://github.com/Phoenix0531-sudo/ZDEM_Archiver) | Purge / archive bulky simulation dumps |
| [ZDEM3D_WEB](https://github.com/Phoenix0531-sudo/ZDEM3D_WEB) | CAE cloud UI (Django + React + VTK.js) |
## License

MIT. Free for commercial use with attribution. See [LICENSE](LICENSE).
