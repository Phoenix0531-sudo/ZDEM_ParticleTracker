# ZDEM Particle Tracker

**面向 ZDEM 离散元结果的交互式二维颗粒追踪 — VisPy 真实半径 Mesh 圆盘、永久 ID、明确的区域策略。**

[English](README.md) | [中文](README.zh-CN.md)

[![CI](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker/actions/workflows/ci.yml/badge.svg)](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

研究向桌面程序，服务 **ZDEM** 帧序列（`all_*.dat` / 沉积 `_ini` 帧）。不是通用多物理 GUI：数据路径、渲染器与区域规则都为盐构造 / 颗粒 DEM 后处理而设（Windows + Python）。

## 预览

![ZDEM Particle Tracker](docs/screenshots/preview.png)

## 为什么做

| 痛点 | 本程序做法 |
|------|------------|
| GL 点精灵发胖、白晕、缩放空洞 | 默认 **真实空间 Mesh 圆盘**（`VisPyRenderer`），不是 `GL_POINTS` |
| 点错后静默空图 | 点击路径写入 **永久颗粒 ID**；失败走日志 |
| 相机只按颗粒 Y 包围盒裁切，墙/实验框消失 | **用户锁定 > 墙 > 元数据** |
| 大帧序列卡死 UI | 异步帧加载、LRU 缓存、轨迹可取消 + 进度 |

## 真实包结构

```
main.py → zdem_particle_tracker.app.main → MainViewer
parsers/   dat_parser.py, dat_scan.py
rendering/ vispy_renderer.py, cpu_raster.py, backend.py
services/  region_detector.py, trajectory_service.py, ...
widgets/   main_viewer.py, selection_logic.py, viewer_logic.py
ui/        side_panels.py, group_legend_panel.py
workers/   frame_load_worker.py
```

## 渲染要点（代码事实）

`rendering/vispy_renderer.py`：

- 颗粒 = 圆盘网格（近景 16 分段，远景可降到 8）
- 视口裁剪 + 颗粒过多时抽稀（`_MAX_DRAW_PARTICLES = 80000`）
- Mesh 缓冲复用，利于拖动时间轴
- 墙线段、选中标记、轨迹折线分层绘制
- Windows 下 `create_native()`，避免错误的 `show=False/parent=self` 嵌入方式

无界面 / CI 可走 CPU·pyqtgraph 路径（`ZDEM_FORCE_PYQTGRAPH=1`）。

## 区域策略

`services/region_detector.py`：

1. 墙数组 `(N,4)=[x1,y1,x2,y2]` → 端点包围盒；退化则回退
2. 元数据 `left/right/bottom/height`
3. UI **用户锁定** 四边界，防止临时“适配颗粒”变成永久实验域

## 安装与运行

```bash
git clone https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker.git
cd ZDEM_ParticleTracker
pip install -r requirements.txt
python main.py
```

Python **>= 3.11**。依赖含 PySide6、numpy、pyqtgraph、scipy、matplotlib、scienceplots；Mesh 路径需要 VisPy。

```bash
set QT_QPA_PLATFORM=offscreen
set ZDEM_FORCE_PYQTGRAPH=1
pytest tests/
```

Linux CI 对部分 Qt 构造使用 **独立子进程**（`tests/qt_subprocess.py`），避免后端混用导致整进程 abort。

## 测试覆盖（节选）

DAT 解析/扫描、selection/viewer 纯逻辑、轨迹取消、渲染像素、GUI 冒烟、性能路径等，见 `tests/test_*.py`。

## 相关仓库

ParticleTracker 负责**交互追踪**；盐构造几何指标、面积守恒、粘结损伤、模型编辑等见同系列 ZDEM 仓（Salt / Area / Bond Fracture / Model Editor 等）。

## 范围

- **做：** ZDEM 二维结果、ID 追踪、真半径显示、区域锁定、导出/报告钩子  
- **不做：** 三维求解器 UI、云协作、本构自动反演  

## 许可证

MIT。详见 [LICENSE](LICENSE)。
