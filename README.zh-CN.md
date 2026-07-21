# ZDEM 颗粒追踪器

**VisPy 真实比例渲染的 ZDEM 颗粒追踪桌面应用**

[English](README.md) | [中文](README.zh-CN.md)

![CI](https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)

VisPy 真实比例渲染的 ZDEM 颗粒追踪桌面应用。

> 作者：[Phoenix0531-sudo](https://github.com/Phoenix0531-sudo) · 欢迎学习、二次开发与**商业使用**，请保留本仓库署名与许可证声明。

## 技术栈

Python · PySide6 · VisPy

## 功能特性

- VisPy Mesh 真实粒径渲染（非 Markers 光晕）
- 区域锁定：用户 > 墙体 > 元数据
- 轨迹/速度（Δx/Δstep）与帧加载性能优化

## 快速开始

```bash
git clone https://github.com/Phoenix0531-sudo/ZDEM_ParticleTracker.git
cd ZDEM_ParticleTracker
```

```bash
pip install -e .
python main.py
pytest -q
```

更完整的英文说明见 [README.md](README.md)。

## 仓库结构（摘要）

```
ZDEM_ParticleTracker/
├─ .github/
├─ docs/
├─ tests/
├─ zdem_particle_tracker/
├─ zdem_particle_tracker.egg-info/
├─ LICENSE
├─ main.py
├─ OPTIMIZATION_PLAN.md
├─ pyproject.toml
├─ README.md
├─ README.zh-CN.md
├─ requirements.txt
```

## 测试

```bash
pip install pytest
pytest -q
```

仓库内 `tests/` 至少包含 smoke 测试；有完整测试套件时以 CI 为准。

## CI

GitHub Actions（`push` / `pull_request`）会：

- 安装依赖（requirements / pyproject）
- 运行 `pytest`（**硬失败**）
- 尽力做语法/结构检查

## 许可证

[MIT](LICENSE) — 可自由使用、修改、分发与**商用**，需保留版权与许可声明（提及本仓库 / 作者即可）。

## 关于

维护者：[Phoenix0531-sudo](https://github.com/Phoenix0531-sudo)
