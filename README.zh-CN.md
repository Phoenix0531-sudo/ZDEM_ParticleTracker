# ZDEM Particle Tracker

**面向 ZDEM 离散元帧序列的交互式 2D 颗粒追踪 — VisPy 真实半径 mesh 圆盘、永久 ID、显式区域策略。**

[English](README.md) | [中文](README.zh-CN.md)

[![CI](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker/actions/workflows/ci.yml/badge.svg)](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-%3E%3D3.11-blue.svg)](pyproject.toml)

研究用桌面端，服务 **ZDEM** 帧序列（`all_*.dat` / 沉积 `_ini`）。为盐构造 / 颗粒 DEM 后处理定见设计，不是通用多物理 GUI。

## 截图 / 证据

<table>
  <tr>
    <td width="50%">
      <img src="docs/screenshots/evidence.png" alt="服务层证据">
      <br><strong>服务层证据</strong> — 真实半径圆盘、墙体区域、选中门控、v=Δx/Δstep
    </td>
    <td width="50%">
      <img src="docs/screenshots/preview.png" alt="领域示意图">
      <br><strong>领域示意图</strong> — 解析 → 区域 → mesh 渲染 → 轨迹
    </td>
  </tr>
</table>

```bash
uv run python scripts/generate_evidence.py
```

证据图为**可复现的合成服务级场景**（诚实）：跑 `RegionDetector` / `pick_particle_id` / `_compute_kinematics`，不冒充专有实验 GUI 截图。

## 为什么存在

| 痛点 | 做法 |
|------|------|
| GL 点精灵放大小白边 / 空洞 | 默认 **mesh 圆盘**（`VisPyRenderer`） |
| 点选失败静默空白 | **永久 ID** + 会话起始 ID 门控 |
| 相机只裁颗粒 Y 包络藏墙 | **用户锁定 > 墙体 > 元数据** |
| 大帧序列卡死 UI | 异步加载、LRU、可取消轨迹 |

## 结构

入口：`python main.py` → `MainViewer`。核心包见 `zdem_particle_tracker/{parsers,rendering,services,widgets,workers}`。

## 区域与运动学

- `RegionDetector.detect_from_walls`：墙段端点 AABB
- 速度定义：**`v = Δx / Δstep`**（模拟步），见 `_compute_kinematics`
- 点击选取：`pick_particle_id(..., start_ids=)` 仅允许会话起始帧中出现过的永久 ID

## 安装 / 运行

```bash
git clone https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker.git
cd ZDEM_ParticleTracker
uv sync --extra dev
python main.py
set QT_QPA_PLATFORM=offscreen
set ZDEM_FORCE_PYQTGRAPH=1
uv run pytest -q tests
```

## 测试覆盖

DAT 解析、选中门控、区域检测、运动学、轨迹取消、渲染/交互路径等（见 `tests/` 文件名）。

## 范围

- **做：** ZDEM 2D 帧、ID 追踪、真实比例显示、区域锁定
- **不做：** 3D 求解器 UI、云协作、本构自动反演
- 专有实验全 GUI 截图不入库；公开证据用脚本 + 本地样例

## 许可证

MIT。详见 [LICENSE](LICENSE)。
