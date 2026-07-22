# ZDEM Particle Tracker

**High-performance particle tracking desktop app with VisPy true-radius rendering**

[English](README.md) | [中文](README.zh-CN.md)

![CI](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)

Desktop viewer and single-particle trajectory tracker for 2D **ZDEM** (discrete-element) experiment dumps on Windows / Python.

This is a research workflow tool, not a generic DEM GUI: it understands ZDEM `all_*.dat` / `all_*_ini.dat` layouts, permanent particle IDs, color# groups, wall columns, and deposition (`_ini`) framing.

## Why this exists

ZDEM salt-tectonics / orogen-scale experiments write tens of thousands of per-step text dumps. Opening them one-by-one is useless for:

1. **Playback** of the full loading history without reloading every frame from disk on the UI thread
2. **True geometric scale** (radius as real disc radius, not point markers with white halos)
3. **Permanent-ID tracking** across frames (local `index` is **not** stable)
4. **Honest region bounds** — user lock > outer walls > metadata, never silent auto-crop to the particle Y-bbox alone

Particle Tracker is built around those four constraints.

## Features

- Scan experiment folders for `all_*.dat` / `all_*_ini.dat`
- **Default session start** = last leading deposition `*_ini` file (not mid-run restarts)
- VisPy **Mesh** true-radius discs (not `GL_POINTS` / marker sprites)
- Coloring: color# / Group / solid
- Experiment region priority: **user lock > walls > metadata**
- Click or type a permanent particle ID to track
- Displacement, path length, velocity `v = Δx / Δstep`
- Async frame load + LRU(5) + prefetch; playback defaults to BASIC parse
- Project file `.zdemtrack.json` (never written into experiment data)
- Rotating logs under `%LOCALAPPDATA%\ZDEM_ParticleTracker\logs\` (`ZDEM_LOG_LEVEL`, `ZDEM_LOG_CONSOLE`)

## Supported / not supported

| Supported | Not in v1 |
|-----------|-----------|
| `all_<step>.dat` | `.sav` binary |
| `all_<step>_ini.dat` | `vtk_inters_*.vtk` contact nets |
| Single-particle track | Multi-particle simultaneous tracks |
| Erosion vs file-error split | Periodic BC handling |

## Deposition frames (`_ini`)

Typical orogen / salt experiments export two phases:

1. **Deposition / init**: `all_0000000000_ini.dat` … `all_0000006000_ini.dat`
2. **Main loading**: `all_0000026000.dat` …

The app treats the **longest leading run of `*_ini.dat`** as deposition.  
**Default start frame** = last of that leading run (end of deposition, start of formal loading).  
`*_ini` files that appear after a non-ini frame (mid-run restart) are **not** used as the default zero.

You can still override start / end / every-Nth frame in the left “time range” panel.

## Environment

- Python 3.11+
- PySide6, NumPy, VisPy, SciPy, Matplotlib (optional `scienceplots`)

```bash
cd ZDEM_ParticleTracker
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
# or: uv sync
```

## Run

```bash
python main.py
# or
python -m zdem_particle_tracker
# or
uv run python -m zdem_particle_tracker
```

## Selection & tracking rules

- **Only IDs present at the session start frame are selectable** (displacement zero = start frame)
- Click or enter an ID → trajectory extraction starts automatically; “Track” re-runs manually
- **Clear selection** (Esc) clears trajectory, path, curves, and data table together
- Changing the time range resets the zero point and clears old tracks
- Pure selection logic lives in `widgets/selection_logic.py` (unit-tested without GUI)

## Shortcuts

| Key | Action |
|-----|--------|
| Ctrl+O | Open experiment directory |
| Ctrl+S | Save project config |
| Space | Play / pause |
| ← → | Prev / next frame |
| Home / End | First / last frame |
| F / G | Fit region / fit particles |
| L | Locate selected particle |
| Esc | Clear selection + trajectory |
| F1 | About & shortcuts |

Legend: double-click isolates a group; right-click edits Group color (persisted in project config).

## Field meanings

| Field | Meaning |
|-------|---------|
| `index` | Local row in **this file only** — **not** for cross-frame track |
| `id` | **Permanent particle ID** — the only track key |
| `color` | Raw DAT color index |
| `group` | Material / layer group (`salt`, `sand`, `base`, …; `***` = unspecified) |

## Erosion vs file error

- File OK but target `id` missing → **erosion**; stop later valid track samples
- File missing / corrupt → **file_error**; **not** counted as erosion

## Performance notes

- Particles: NumPy arrays + VisPy Mesh batch discs
- Frames: QThread load, LRU(5), prefetch next frame
- Playback / prefetch: `BASIC_FRAME` (auto FULL when coloring by Group)
- Tracks: streaming `find_particle_in_file` + thread pool

## 日志

写入用户目录，**不**写实验数据目录：

`%LOCALAPPDATA%\ZDEM_ParticleTracker\logs\app.log`（轮转，最大约 5×5MB）

环境变量：

| 变量 | 作用 |
|------|------|
| `ZDEM_LOG_LEVEL=DEBUG` | 文件日志级别（默认 INFO） |
| `ZDEM_LOG_CONSOLE=1` | 同时把 INFO 打到 stderr |

覆盖：启动/退出、目录扫描、DAT 解析耗时、帧加载、区域检测、选中/拒绝 ID、轨迹开始/进度取消/完成、未捕获异常与 Qt 警告。

自检脚本：

```bash
uv run python scripts/self_diag.py
```

## 测试

```bash
# 默认快速套件（含 MainViewer 构造 + CPU 像素 + 有 GL 时 VisPy 截图）
uv run python -m unittest discover -s tests -t .

# 交互路径（无主窗业务逻辑）
uv run python -m unittest tests.test_interaction_paths tests.test_viewer_logic

# 渲染 / 主窗构造（默认会跑）
uv run python -m unittest tests.test_render_pixels tests.test_gui_smoke

# 无 OpenGL 的 CI / 远端：强制 PyQtGraph + offscreen
set QT_QPA_PLATFORM=offscreen
set ZDEM_FORCE_PYQTGRAPH=1
uv run python -m unittest tests.test_gui_smoke tests.test_render_pixels

# 真实样本 + 选中清除（约 1 分钟）
set ZDEM_GUI_SAMPLE=1
uv run python -m unittest tests.test_render_pixels.TestMainViewerConstruct.test_load_sample_select_clear

# 离线自检
uv run python scripts/self_diag.py
```

环境变量：

| 变量 | 作用 |
|------|------|
| `ZDEM_FORCE_PYQTGRAPH=1` | 禁用 VisPy，主窗用 PyQtGraph（headless 安全） |
| `ZDEM_FORCE_VISPY=1` | 在 offscreen 上仍尝试 VisPy |
| `QT_QPA_PLATFORM=offscreen` | 默认自动改走 PyQtGraph（无 GL） |
| `ZDEM_GUI_SAMPLE=1` | 加载真实实验目录做点选 smoke |
| `ZDEM_LOG_LEVEL=DEBUG` | 详细文件日志 |
| `ZDEM_LOG_CONSOLE=1` | 日志镜像到 stderr |

模块拆分（便于维护与单测）：

| 模块 | 职责 |
|------|------|
| `widgets/selection_logic.py` | 选中门闸 / KD 拾取 / 路径裁剪 / 播放帧索引 |
| `widgets/viewer_logic.py` | 曲线序列 / 表行 / 区域校验 / ID 解析 / 配置着色 |
| `ui/side_panels.py` | 左栏/右栏/播放条 Qt 工厂（无业务逻辑） |
| `rendering/backend.py` | VisPy / PyQtGraph 选择 |
| `rendering/cpu_raster.py` | 无 GL 的圆盘像素真值 |
| `rendering/vispy_renderer.py` | VisPy Mesh + `render_to_array` |
| `widgets/main_viewer.py` | 编排：加载帧、渲染、信号连接 |

## Tests

```bash
# Pure unit suite (parsers, selection, scan) — CI uses this
python -m pytest -q tests

# or unittest
python -m unittest discover -s tests -t .

# Real sample + interactive pick (needs display; not CI)
set ZDEM_GUI_SAMPLE=1
python -m unittest tests.test_gui_smoke.TestGuiSmoke.test_load_sample_and_start_ids
```

CI installs system Qt libs and runs headless (`QT_QPA_PLATFORM=offscreen`) for import-safe tests.

## Known limits

- Export UI not wired yet (service code kept)
- Unit labels not unified (coords / radii follow each experiment)
- Main view needs OpenGL / VisPy
- Historical `OPTIMIZATION_PLAN.md` is notes only; this README is the contract

## Roadmap

- Export menu + unit system
- Multi-particle / box selection stats
- VTK contact networks
- Wall visual buffer reuse

## ZDEM Tool Family

Related open-source tools in the same ZDEM / DEM workflow (same author):

| Repo | Role |
|------|------|
| [ZDEM_ParticleTracker](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker) | VisPy particle tracking desktop app (true-radius discs, permanent IDs) |
| [ZDEM_Archiver](https://github.com/Phoenix0531-sudo/ZDEM_Archiver) | Safe purge of timestep dumps while keeping reproducible sources |
| [ZDEM_Area_Conservation](https://github.com/Phoenix0531-sudo/ZDEM_Area_Conservation) | Delaunay coverage area vs load step |
| [ZDEM_Bond_Fracture](https://github.com/Phoenix0531-sudo/ZDEM_Bond_Fracture) | Bond damage / fracture time series + ROI |
| [ZDEM_Damage_Thresholds](https://github.com/Phoenix0531-sudo/ZDEM_Damage_Thresholds) | Damage evolution and crack thresholds |
| [ZDEM_DFN](https://github.com/Phoenix0531-sudo/ZDEM_DFN) | Discrete fracture network generation |
| [ZDEM_Model_Editor](https://github.com/Phoenix0531-sudo/ZDEM_Model_Editor) | tkinter + matplotlib model file editor |
| [ZDEM_Salt_Kinematics](https://github.com/Phoenix0531-sudo/ZDEM_Salt_Kinematics) | Salt kinematics automation for ZDEM outputs |
| [ZDEM3D_WEB](https://github.com/Phoenix0531-sudo/ZDEM3D_WEB) | 3D web CAE front (VTK + Django/React) |

Typical pipeline: **Model_Editor / DFN → ZDEM run → Archiver (disk) → ParticleTracker / Bond / Area / Salt / Damage (analysis)**.

## License

[MIT](LICENSE) — free for commercial use with attribution.
