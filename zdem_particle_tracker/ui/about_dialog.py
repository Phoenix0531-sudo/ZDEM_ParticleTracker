"""About / shortcuts dialog for MainViewer."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout

APP_VERSION = "1.0.0"

ABOUT_HTML = f"""
<h2 style="margin-bottom:4px;">ZDEM Particle Tracker</h2>
<p style="color:#666;margin-top:0;">版本 {APP_VERSION} · ECUT 盐构造 / ZDEM</p>
<p>读取 <code>all_*.dat</code> 实验输出，按<strong>永久颗粒 ID</strong>追踪位移与速度。</p>
<ul>
<li>默认时间起点：前导沉积阶段最后一个 <code>_ini</code> 文件</li>
<li>位移零点：会话起始帧中该颗粒的位置</li>
<li>仅可选择<strong>起始帧中存在</strong>的颗粒</li>
<li>选中后自动提取轨迹；「追踪」仍可手动重跑</li>
</ul>
"""

SHORTCUTS_HTML = """
<h3>快捷键</h3>
<table cellspacing="6">
<tr><td><b>Ctrl+O</b></td><td>打开实验目录</td></tr>
<tr><td><b>Ctrl+S</b></td><td>保存项目配置</td></tr>
<tr><td><b>Space</b></td><td>播放 / 暂停</td></tr>
<tr><td><b>Left / Right</b></td><td>上一帧 / 下一帧</td></tr>
<tr><td><b>Home / End</b></td><td>第一帧 / 最后一帧</td></tr>
<tr><td><b>F</b></td><td>适配实验区域</td></tr>
<tr><td><b>G</b></td><td>适配颗粒</td></tr>
<tr><td><b>L</b></td><td>定位选中颗粒</td></tr>
<tr><td><b>Esc</b></td><td>清除选择与轨迹</td></tr>
<tr><td><b>F1</b></td><td>关于与快捷键</td></tr>
</table>
<p style="color:#86868b;font-size:12px;">图例：双击仅显示该组；右键修改 Group 颜色（可写入项目配置）。</p>
"""


def show_about_dialog(parent=None) -> None:
    dlg = QDialog(parent)
    dlg.setWindowTitle("关于 ZDEM Particle Tracker")
    dlg.resize(480, 420)
    lay = QVBoxLayout(dlg)
    browser = QTextBrowser()
    browser.setOpenExternalLinks(False)
    browser.setHtml(ABOUT_HTML + SHORTCUTS_HTML)
    lay.addWidget(browser)
    bb = QDialogButtonBox(QDialogButtonBox.Ok)
    bb.accepted.connect(dlg.accept)
    lay.addWidget(bb)
    dlg.exec()
