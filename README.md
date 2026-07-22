# ZDEM Particle Tracker

**High-performance 2D particle tracking for ZDEM dumps — true-radius VisPy mesh rendering.**

[English](README.md) | [中文](README.zh-CN.md)

[![CI](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker/actions/workflows/ci.yml/badge.svg)](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

High-performance 2D particle tracking for ZDEM dumps — true-radius VisPy mesh rendering.

Interactive IDs. Region locks. Honest geometry.


## Features

- 🎯 Click-to-fill permanent particle IDs (no silent empty plots)
- 🟣 VisPy **mesh discs at true 2×radius** (not halo-prone GL points)
- 🗺️ Experiment region = user lock > walls > metadata (never permanent auto-crop to Y-bbox)
- 📈 Trajectory tracking with cancelable workers + progress
- 🧪 Hard CI: Qt widget construction via isolated subprocess on Linux
- 🧩 Side-panel extraction + pure viewer logic for maintainability

## Get started

### Install

```bash
git clone https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker.git
cd ZDEM_ParticleTracker
pip install -r requirements.txt
# recommended: VisPy + PySide6 + numpy/scipy
# or: uv sync
```

### Usage

```bash
python main.py
```

Headless tests:

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
  selection_logic.py  viewer_logic.py
  rendering/
tests/
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

## Notes

Research workflow tool for salt-tectonics / orogenic DEM campaigns — not a generic multi-physics GUI.

## License

MIT. Free for commercial use with attribution where applicable. See [LICENSE](LICENSE).
