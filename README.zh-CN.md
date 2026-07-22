# ZDEM Particle Tracker

**高性能 2D 颗粒追踪，VisPy 真实半径渲染**

[English](README.md) | [中文](README.zh-CN.md)

![CI](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)

面向 2D **ZDEM** 离散元结果的桌面查看与**单颗粒轨迹追踪**（Windows / Python）。

研究工作流工具，不是通用 DEM GUI。理解 `all_*.dat` / `all_*_ini.dat`、永久颗粒 ID、**color#** 组、墙体列（P1/P2）与沉积（`_ini`）框。

## 为什么做这个

盐构造 / 造山 DEM 需要交互选 ID、区域锁定与诚实的半径渲染。点精灵易出白晕与缩放空洞；本应用优先 **VisPy 网格圆盘（真实 2×半径）**，CI / 无头环境可回退 pyqtgraph。

## 功能

- VisPy 网格渲染；`ZDEM_FORCE_PYQTGRAPH=1` 强制 CPU 路径  
- 区域：用户锁定 > 墙体 > 元数据  
- 可取消轨迹 worker + 进度  
- 滚动日志 / 解析耗时 / 自检  
- Linux CI：Qt 控件在**独立子进程**中硬断言  

## 安装

```bash
git clone https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker.git
cd ZDEM_ParticleTracker
pip install -r requirements.txt
```

## 使用

```bash
python main.py
```

```bash
set QT_QPA_PLATFORM=offscreen
set ZDEM_FORCE_PYQTGRAPH=1
pytest tests/
```

## 目录结构

```
main.py
zdem_particle_tracker/
tests/qt_subprocess.py
```

## 相关 ZDEM 工具

| 仓库 | 作用 |
|------|------|
| [ZDEM_ParticleTracker](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker) | 交互式颗粒追踪 + VisPy 真实半径渲染 |
| [ZDEM_Salt_Kinematics](https://github.com/Phoenix0531-sudo/ZDEM_Salt_Kinematics) | 盐体几何/运动学提取与出图 |
| [ZDEM_Area_Conservation](https://github.com/Phoenix0531-sudo/ZDEM_Area_Conservation) | 面积守恒 / 三角网格分析 |
| [ZDEM_Bond_Fracture](https://github.com/Phoenix0531-sudo/ZDEM_Bond_Fracture) | 粘结损伤序列 + 桌面/CLI |
| [ZDEM_Damage_Thresholds](https://github.com/Phoenix0531-sudo/ZDEM_Damage_Thresholds) | 损伤阈值与应变–能量图 |
| [ZDEM_DFN](https://github.com/Phoenix0531-sudo/ZDEM_DFN) | ZDEM 离散裂隙网络生成 |
| [ZDEM_Model_Editor](https://github.com/Phoenix0531-sudo/ZDEM_Model_Editor) | 模型文件可视化编辑 |
| [ZDEM_Archiver](https://github.com/Phoenix0531-sudo/ZDEM_Archiver) | 大体量模拟结果归档清理 |
| [ZDEM3D_WEB](https://github.com/Phoenix0531-sudo/ZDEM3D_WEB) | CAE 云端界面（Django + React + VTK.js） |
## 许可证

MIT。可在署名前提下商用。见 [LICENSE](LICENSE)。
