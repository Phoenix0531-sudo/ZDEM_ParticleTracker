# ZDEM Particle Tracker

**High-performance particle tracking desktop app with VisPy rendering**

[English](README.md) | [中文](README.zh-CN.md)

![CI](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)

二维 ZDEM 离散元实验结果查看与单颗粒轨迹追踪工具（Windows / Python）。

## 主要功能

- 扫描实验目录中的 `all_*.dat` / `all_*_ini.dat`
- **默认时间起点 = 前导沉积阶段最后一个 `_ini` 文件**
- VisPy Mesh 真半径圆盘绘制（非 GL_POINTS）
- 按 color# / Group / 单色着色
- 实验区域：用户锁定 > 外墙 > 元数据
- 永久颗粒 ID 点击 / 输入追踪
- 位移、路径长度、`v = Δx/Δstep` 速度曲线
- 异步帧加载 + LRU + 预取；播放默认 BASIC 解析
- 项目配置 `.zdemtrack.json`（不写实验数据）

## 支持 / 不支持

| 支持 | 不支持（第一版） |
|------|------------------|
| `all_<step>.dat` | `.sav` 二进制 |
| `all_<step>_ini.dat` | `vtk_inters_*.vtk` 接触网 |
| 单颗粒轨迹 | 多颗粒同时追踪 |
| 剥蚀 / 文件错误区分 | 周期边界 |

## 关于 `_ini`（沉积阶段）

ZDEM 造山带/盐构造实验常见两段输出：

1. **沉积 / 初始化阶段**：`all_0000000000_ini.dat` … `all_0000006000_ini.dat`
2. **正式加载变形**：`all_0000026000.dat` …

程序把**从目录开头起连续的 `*_ini.dat`** 视为沉积阶段，  
**默认起始帧 = 最后一个前导 `_ini`**（沉积结束、正式实验前的形态）。  
中途重启产生的 `*_ini`（前面已有非 ini 文件）**不会**当作默认起点。

用户可在左侧「时间范围」中改起始/结束/间隔 N。

## 环境

- Python 3.11+
- PySide6, NumPy, VisPy, SciPy, Matplotlib（可选 scienceplots）

```bash
cd ZDEM_ParticleTracker
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
# 或
uv sync
```

## 运行

```bash
python main.py
# 或
python -m zdem_particle_tracker
# 或
uv run python -m zdem_particle_tracker
```

## 选择与追踪

- **仅可选择会话起始帧中存在的永久 ID**（位移零点 = 起始帧）
- 点击或输入 ID 后 **自动提取轨迹**；「追踪」可手动重跑
- **清除选择**（Esc）会同时清除轨迹、路径、曲线与数据表
- 修改时间范围后会提示零点重置并清除旧轨迹

选择/播放等纯逻辑在 `widgets/selection_logic.py`，便于无 GUI 单测。

## 快捷键

| 键 | 作用 |
|----|------|
| Ctrl+O | 打开实验目录 |
| Ctrl+S | 保存项目配置 |
| Space | 播放/暂停 |
| ← → | 上一帧/下一帧 |
| Home/End | 首帧/末帧 |
| F / G | 适配区域 / 适配颗粒 |
| L | 定位选中颗粒 |
| Esc | 清除选择与轨迹 |
| F1 | 关于与快捷键 |

图例：双击仅显示该组；右键修改 Group 颜色（保存项目配置后持久化）。

## 字段说明

| 字段 | 含义 |
|------|------|
| `index` | 当前文件内局部序号，**不可**跨帧追踪 |
| `id` | **永久颗粒 ID**，追踪唯一键 |
| `color` | DAT 原始 color 编号 |
| `group` | 材料/层组（salt, sand, base…；`***`=未指定） |

## 剥蚀判定

- 文件有效但找不到目标 `id` → **剥蚀**，停止后续有效轨迹
- 文件缺失/损坏 → **file_error**，**不**算剥蚀

## 性能设计

- 颗粒：NumPy 数组 + VisPy Mesh 批量圆盘
- 帧：QThread 加载，LRU(5)，预取下一帧
- 播放 / 预取：`BASIC_FRAME`（按 Group 着色时自动 FULL）
- 轨迹：`find_particle_in_file` 流式 + 线程池

## 日志

写入用户目录，**不**写实验数据目录：

`%LOCALAPPDATA%\ZDEM_ParticleTracker\logs\app.log`

## 测试

```bash
uv run python -m unittest discover -s tests -v
```

## 已知限制

- 导出 UI 暂未接线（服务代码保留）
- 单位标签尚未统一（坐标/半径量级随实验而定）
- 无 OpenGL 环境无法使用 VisPy 主视图
- `OPTIMIZATION_PLAN.md` 为历史笔记，以本 README 为准

## 未来方向

- 导出菜单、单位体系
- 多颗粒 / 框选统计
- VTK 接触网络
- 墙体 visual 缓冲复用

## 许可与作者

科研用途。ECUT 盐构造 / ZDEM 工作流配套工具。

## License

[MIT](LICENSE) — free for commercial use with attribution.
