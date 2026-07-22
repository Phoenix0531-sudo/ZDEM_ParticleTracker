# ZDEM Particle Tracker

**Interactive 2D particle tracking for ZDEM dumps with true-radius VisPy mesh rendering.**

[English](README.md) | [中文](README.zh-CN.md)

[![CI](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker/actions/workflows/ci.yml/badge.svg)](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Click fills permanent IDs. Region policy is explicit. Geometry does not lie.

## Preview

![ZDEM Particle Tracker](docs/screenshots/preview.png)

## Features

- VisPy mesh discs at true 2x radius (optional pyqtgraph path for headless CI)
- Region priority: user lock > walls > metadata (no permanent Y-bbox-only crop)
- Trajectory tracking with cancelable workers and progress feedback
- color# grouping and wall columns (P1/P2) understood by the data path
- Linux CI constructs Qt widgets in an isolated subprocess to avoid aborts

## Get started

### Install

```bash
git clone https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker.git
cd ZDEM_ParticleTracker
pip install -r requirements.txt
```

### Usage

```bash
python main.py

set QT_QPA_PLATFORM=offscreen
set ZDEM_FORCE_PYQTGRAPH=1
pytest tests/
```

## Project layout

```
main.py
zdem_particle_tracker/
  widgets/  ui/  rendering/
tests/
```

## Related ZDEM tools

| Repo | Role |
|------|------|
| [ZDEM_ParticleTracker](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker) | Interactive particle tracking + true-radius render |
| [ZDEM_Salt_Kinematics](https://github.com/Phoenix0531-sudo/ZDEM_Salt_Kinematics) | Salt geometry / kinematics extraction and plots |
| [ZDEM_Area_Conservation](https://github.com/Phoenix0531-sudo/ZDEM_Area_Conservation) | Area-conservation / triangulation analysis |
| [ZDEM_Bond_Fracture](https://github.com/Phoenix0531-sudo/ZDEM_Bond_Fracture) | Bond damage series + visualizer |
| [ZDEM_Damage_Thresholds](https://github.com/Phoenix0531-sudo/ZDEM_Damage_Thresholds) | Damage thresholds and energy plots |
| [ZDEM_DFN](https://github.com/Phoenix0531-sudo/ZDEM_DFN) | Discrete fracture network generator |
| [ZDEM_Model_Editor](https://github.com/Phoenix0531-sudo/ZDEM_Model_Editor) | Model file visual editor |
| [ZDEM_Archiver](https://github.com/Phoenix0531-sudo/ZDEM_Archiver) | Archive / purge bulky dumps |
| [ZDEM3D_WEB](https://github.com/Phoenix0531-sudo/ZDEM3D_WEB) | CAE cloud UI (Django + React + VTK.js) |


## Notes

Research workflow tool for salt-tectonics / orogenic DEM campaigns.

## License

MIT. Free for commercial use with attribution where applicable. See [LICENSE](LICENSE).
