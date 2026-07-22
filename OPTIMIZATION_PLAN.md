# 历史笔记（已过时）

本文件保留为开发过程记录，**不再作为优化 backlog**。

当前权威说明见：

- `README.md` — 功能、_ini 默认起点、运行与限制
- 代码：`parsers/dat_scan.py`、`widgets/main_viewer.py`、`rendering/vispy_renderer.py`

已完成（摘要）：

- VisPy Mesh 真圆盘（非 pyqtgraph Scatter / GL_POINTS）
- 并行轨迹流式查找 + 运动学
- 异步帧加载 / LRU / 预取
- 前导 `_ini` 默认时间起点
- 着色 color# / Group / 单色
- 项目配置延迟恢复选中颗粒

若需新优化项，请直接开 issue 或改代码，勿再更新本文件的「Plan」段落。
