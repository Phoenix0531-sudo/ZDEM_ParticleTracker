# ZDEM Particle Tracker

**面向 ZDEM 结果文件的高性能二维颗粒追踪 — VisPy 真实半径网格渲染。**

[English](README.md) | [中文](README.zh-CN.md)

[![CI](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker/actions/workflows/ci.yml/badge.svg)](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

面向 ZDEM 结果文件的高性能二维颗粒追踪 — VisPy 真实半径网格渲染。

可点选 ID · 区域锁定 · 几何不说谎。


## 功能

- 🎯 点击即填永久颗粒 ID（拒绝空图静默失败）
- 🟣 VisPy **真实 2×半径 Mesh 圆盘**（避免 GL 点白晕 / 缩放空洞）
- 🗺️ 实验区域 = 用户锁定 > 墙 > 元数据（禁止永久仅按颗粒 Y 包围盒裁剪）
- 📈 轨迹追踪：可取消 worker + 进度
- 🧪 严格 CI：Linux 下 Qt 控件用独立子进程构造
- 🧩 侧栏拆分 + 纯逻辑模块，便于维护

## 快速开始

### 安装

```bash
git clone https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker.git
cd ZDEM_ParticleTracker
pip install -r requirements.txt
# recommended: VisPy + PySide6 + numpy/scipy
# or: uv sync
```

### 使用

```bash
python main.py
```

无界面测试：

```bash
set QT_QPA_PLATFORM=offscreen
set ZDEM_FORCE_PYQTGRAPH=1
pytest tests/
```

## 项目结构

```
main.py
zdem_particle_tracker/
  widgets/main_viewer.py
  ui/side_panels.py
  selection_logic.py  viewer_logic.py
  rendering/
tests/
```

## 相关 ZDEM 工具

| 仓库 | 作用 |
|------|------|
| [ZDEM_ParticleTracker](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker) | 交互颗粒追踪 + VisPy 真实半径渲染 |
| [ZDEM_Salt_Kinematics](https://github.com/Phoenix0531-sudo/ZDEM_Salt_Kinematics) | 盐构造几何 / 运动学提取与出图 |
| [ZDEM_Area_Conservation](https://github.com/Phoenix0531-sudo/ZDEM_Area_Conservation) | 面积守恒 / 三角剖分分析 |
| [ZDEM_Bond_Fracture](https://github.com/Phoenix0531-sudo/ZDEM_Bond_Fracture) | 粘结损伤序列 + 桌面 / CLI |
| [ZDEM_Damage_Thresholds](https://github.com/Phoenix0531-sudo/ZDEM_Damage_Thresholds) | 损伤阈值与应变能图 |
| [ZDEM_DFN](https://github.com/Phoenix0531-sudo/ZDEM_DFN) | ZDEM 离散裂隙网络生成 |
| [ZDEM_Model_Editor](https://github.com/Phoenix0531-sudo/ZDEM_Model_Editor) | 模型文件可视化编辑 |
| [ZDEM_Archiver](https://github.com/Phoenix0531-sudo/ZDEM_Archiver) | 大体积模拟结果归档 / 清理 |
| [ZDEM3D_WEB](https://github.com/Phoenix0531-sudo/ZDEM3D_WEB) | CAE 云端界面（Django + React + VTK.js） |

## 说明

盐构造 / 造山 DEM 研究流程工具 — 不是通用多物理 GUI。

## 许可证

MIT。在注明出处的前提下可商业使用（以 LICENSE 为准）。详见 [LICENSE](LICENSE)。
