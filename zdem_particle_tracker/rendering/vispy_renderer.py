"""VisPy-based GPU-accelerated particle renderer for ZDEM data.

Particles are drawn as real-space disc meshes (not GL_POINTS markers).
Supports mesh buffer reuse, viewport culling, and far-view decimation.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget
from vispy import scene
from vispy.scene import SceneCanvas


class VisPySignalBridge(QObject):
    """Bridge VisPy events to Qt signals."""

    clicked = Signal(float, float)  # x, y in data coords


class VisPyRenderer(QWidget):
    """GPU-accelerated 2D particle renderer using VisPy mesh discs."""

    _DISC_SEGMENTS = 16
    # When span/diameter is large, reduce segments / decimate for performance
    _FAR_SEGMENTS = 8
    _MAX_DRAW_PARTICLES = 80000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._canvas = None
        self._mesh = None
        self._wall_lines = []
        self._selection_markers = []
        self._origin_markers = []
        self._traj_line = None
        self._xmin = self._xmax = self._ymin = self._ymax = 0
        self._signal_bridge = VisPySignalBridge()
        self._particle_positions = None
        self._particle_rads = None
        self._last_n = 0
        self._last_seg = self._DISC_SEGMENTS
        self._init_vispy()

    @property
    def clicked(self):
        return self._signal_bridge.clicked

    def _init_vispy(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Windows Qt: create_native() without show=False/parent=self
        self._canvas = SceneCanvas(keys=None, size=(800, 600))
        self._canvas.create_native()
        self._canvas.bgcolor = (1.0, 1.0, 1.0, 1.0)
        layout.addWidget(self._canvas.native)

        self._view = self._canvas.central_widget.add_view()
        self._view.camera = scene.PanZoomCamera(aspect=1)
        self._view.camera.set_range(x=(0, 1), y=(0, 1))
        self._canvas.events.mouse_press.connect(self._on_canvas_click)

    def _on_canvas_click(self, event):
        if event.button != 1 or self._view.camera is None:
            return
        try:
            tr = self._view.scene.transform
            if tr is None:
                nx = event.pos[0] / self._canvas.size[0] if self._canvas.size[0] else 0
                ny = 1 - event.pos[1] / self._canvas.size[1] if self._canvas.size[1] else 0
                data_pos = self._view.camera.transform.imap((nx * 2 - 1, ny * 2 - 1))
            else:
                data_pos = self._view.scene.transform.imap(event.pos)
            if data_pos is not None:
                self._signal_bridge.clicked.emit(float(data_pos[0]), float(data_pos[1]))
        except Exception:
            try:
                rect = self._view.camera.rect
                w, h = self._canvas.size
                if w > 0 and h > 0 and rect is not None:
                    x = rect.left + (event.pos[0] / w) * rect.width
                    y = rect.bottom + (1.0 - event.pos[1] / h) * rect.height
                    self._signal_bridge.clicked.emit(float(x), float(y))
            except Exception:
                pass

    def get_view_rect(self):
        """Return (xmin, xmax, ymin, ymax) of current camera, or None."""
        try:
            rect = self._view.camera.rect
            if rect is None:
                return None
            return (
                float(rect.left),
                float(rect.left + rect.width),
                float(rect.bottom),
                float(rect.bottom + rect.height),
            )
        except Exception:
            return None

    @classmethod
    def _build_disc_mesh(cls, xs, ys, rads, rgba, n_seg=None):
        if n_seg is None:
            n_seg = cls._DISC_SEGMENTS

        xs = np.asarray(xs, dtype=np.float64)
        ys = np.asarray(ys, dtype=np.float64)
        rads = np.asarray(rads, dtype=np.float64)
        n = len(xs)
        if n == 0:
            return (
                np.zeros((0, 3), dtype=np.float32),
                np.zeros((0, 3), dtype=np.uint32),
                np.zeros((0, 4), dtype=np.float32),
            )

        angles = np.linspace(0.0, 2.0 * np.pi, n_seg, endpoint=False)
        ux = np.cos(angles)
        uy = np.sin(angles)

        v_per = n_seg + 1
        vertices = np.empty((n * v_per, 3), dtype=np.float32)
        colors = np.empty((n * v_per, 4), dtype=np.float32)

        vertices[0::v_per, 0] = xs
        vertices[0::v_per, 1] = ys
        vertices[0::v_per, 2] = 0.0

        rim_x = xs[:, None] + rads[:, None] * ux[None, :]
        rim_y = ys[:, None] + rads[:, None] * uy[None, :]

        for k in range(n_seg):
            vertices[1 + k :: v_per, 0] = rim_x[:, k]
            vertices[1 + k :: v_per, 1] = rim_y[:, k]
            vertices[1 + k :: v_per, 2] = 0.0

        rgba = np.asarray(rgba, dtype=np.float32)
        if rgba.ndim == 1:
            rgba = np.broadcast_to(rgba, (n, 4)).copy()
        for k in range(v_per):
            colors[k::v_per] = rgba

        faces = np.empty((n * n_seg, 3), dtype=np.uint32)
        base = (np.arange(n, dtype=np.uint32) * v_per)[:, None]
        rim_idx = np.arange(1, n_seg + 1, dtype=np.uint32)
        rim_next = np.roll(rim_idx, -1)
        faces[:, 0] = np.repeat(base.ravel(), n_seg)
        faces[:, 1] = (base + rim_idx[None, :]).ravel()
        faces[:, 2] = (base + rim_next[None, :]).ravel()

        return vertices, faces, colors

    def _select_draw_subset(self, xs, ys, rads, rgba, enhanced=False):
        """Viewport cull + far-view decimation. Returns subset + n_seg."""
        xs = np.asarray(xs, dtype=np.float64)
        ys = np.asarray(ys, dtype=np.float64)
        rads = np.asarray(rads, dtype=np.float64)
        rgba = np.asarray(rgba, dtype=np.float32)
        n = len(xs)
        if n == 0:
            return xs, ys, rads, rgba, self._DISC_SEGMENTS

        # Viewport cull with pad = max radius
        rect = self.get_view_rect()
        mask = None
        if rect is not None:
            xmin, xmax, ymin, ymax = rect
            pad = float(np.max(rads)) * 2 if n else 0.0
            # also expand pad a bit for enhanced visibility
            if enhanced:
                pad = max(pad, (xmax - xmin) * 0.002)
            mask = (
                (xs + rads >= xmin - pad)
                & (xs - rads <= xmax + pad)
                & (ys + rads >= ymin - pad)
                & (ys - rads <= ymax + pad)
            )
            # If cull removes almost everything due to bad rect, fall back
            if mask is not None and int(mask.sum()) < max(10, n // 1000):
                # maybe camera not ready — draw all
                mask = None

        if mask is not None:
            xs, ys, rads, rgba = xs[mask], ys[mask], rads[mask], rgba[mask]
            n = len(xs)

        # Segment LOD from apparent size
        n_seg = self._DISC_SEGMENTS
        if rect is not None and n > 0:
            xmin, xmax, ymin, ymax = rect
            span = max(xmax - xmin, ymax - ymin, 1.0)
            med_d = float(np.median(rads) * 2) if n else 1.0
            if med_d / span < 0.002:
                n_seg = self._FAR_SEGMENTS

        # Decimate if still huge
        if n > self._MAX_DRAW_PARTICLES:
            step = int(np.ceil(n / self._MAX_DRAW_PARTICLES))
            xs, ys, rads, rgba = xs[::step], ys[::step], rads[::step], rgba[::step]

        return xs, ys, rads, rgba, n_seg

    def set_data(self, xs, ys, rads, colors, enhanced=False):
        """Draw particles as real-space filled discs.

        *colors* should be (N, 3|4) float array in 0–1, or list of QColor
        (slow path kept for compatibility).
        """
        self._particle_positions = np.column_stack([xs, ys]).astype(np.float32)
        self._particle_rads = np.asarray(rads, dtype=np.float64)
        n = len(xs)
        if n == 0:
            if self._mesh is not None:
                self._mesh.parent = None
                self._mesh = None
            self._last_n = 0
            return

        # Colors -> (N, 4) float
        if isinstance(colors, list) and len(colors) > 0:
            rgba = np.array(
                [
                    (c.red() / 255.0, c.green() / 255.0, c.blue() / 255.0, 1.0)
                    for c in colors
                ],
                dtype=np.float32,
            )
        elif isinstance(colors, np.ndarray) and colors.ndim == 2:
            rgba = colors.astype(np.float32)
            if rgba.shape[1] == 3:
                a = np.ones((rgba.shape[0], 1), dtype=np.float32)
                rgba = np.hstack([rgba, a])
            rgba[:, 3] = 1.0
        else:
            rgba = np.ones((n, 4), dtype=np.float32)
            rgba[:, :3] = 0.5

        dxs, dys, drads, drgba, n_seg = self._select_draw_subset(
            xs, ys, rads, rgba, enhanced=enhanced
        )
        dn = len(dxs)
        vertices, faces, vcolors = self._build_disc_mesh(
            dxs, dys, drads, drgba, n_seg=n_seg
        )

        # Reuse mesh when topology (N, segments) matches
        can_reuse = (
            self._mesh is not None
            and dn == self._last_n
            and n_seg == self._last_seg
            and dn > 0
        )
        if can_reuse:
            try:
                self._mesh.set_data(
                    vertices=vertices, faces=faces, vertex_colors=vcolors
                )
            except Exception:
                can_reuse = False

        if not can_reuse:
            if self._mesh is not None:
                self._mesh.parent = None
                self._mesh = None
            if dn > 0:
                self._mesh = scene.visuals.Mesh(
                    vertices=vertices,
                    faces=faces,
                    vertex_colors=vcolors,
                    parent=self._view.scene,
                )
                try:
                    self._mesh.shading = None
                except Exception:
                    pass

        self._last_n = dn
        self._last_seg = n_seg

    def set_region(self, xmin, xmax, ymin, ymax):
        self._xmin, self._xmax = xmin, xmax
        self._ymin, self._ymax = ymin, ymax
        mx = (xmax - xmin) * 0.05
        my = (ymax - ymin) * 0.05
        self._view.camera.set_range(
            x=(xmin - mx, xmax + mx),
            y=(ymin - my, ymax + my),
        )

    def set_walls(self, wall_data):
        self.clear_walls()
        if wall_data is None or len(wall_data) == 0:
            return
        wall_data = np.asarray(wall_data, dtype=np.float64)
        for i in range(wall_data.shape[0]):
            x1, y1, x2, y2 = wall_data[i]
            line = scene.visuals.Line(
                pos=np.array([[x1, y1], [x2, y2]], dtype=np.float32),
                color=(0.25, 0.25, 0.25, 1.0),
                parent=self._view.scene,
                width=2,
            )
            self._wall_lines.append(line)

    def clear_walls(self):
        for line in self._wall_lines:
            line.parent = None
        self._wall_lines.clear()

    def set_selection(self, x, y, radius, particle_id=None):
        self.clear_selection()
        if x is None:
            return
        r = float(radius)
        ring_r = r * 1.6
        ring_points = self._circle_points(x, y, ring_r, 48)
        ring_points = np.vstack([ring_points, ring_points[:1]])
        ring = scene.visuals.Line(
            pos=ring_points,
            color=(1.0, 0.15, 0.1, 1.0),
            parent=self._view.scene,
            width=2,
        )
        self._selection_markers.append(ring)
        cs = r * 1.8
        cross_h = scene.visuals.Line(
            pos=np.array([[x - cs, y], [x + cs, y]], dtype=np.float32),
            color=(1.0, 0.15, 0.1, 1.0),
            parent=self._view.scene,
            width=2,
        )
        self._selection_markers.append(cross_h)
        cross_v = scene.visuals.Line(
            pos=np.array([[x, y - cs], [x, y + cs]], dtype=np.float32),
            color=(1.0, 0.15, 0.1, 1.0),
            parent=self._view.scene,
            width=2,
        )
        self._selection_markers.append(cross_v)
        if particle_id is not None:
            try:
                txt = scene.visuals.Text(
                    f"ID {int(particle_id)}",
                    color=(0.85, 0.1, 0.08, 1.0),
                    font_size=10,
                    pos=(float(x) + r * 2.2, float(y) + r * 2.2),
                    anchor_x="left",
                    anchor_y="bottom",
                    parent=self._view.scene,
                )
                self._selection_markers.append(txt)
            except Exception:
                pass

    def set_origin_marker(self, x, y, radius=None):
        """Mark trajectory zero-point (start of displacement)."""
        self.clear_origin_marker()
        if x is None or y is None:
            return
        r = float(radius) if radius is not None else 80.0
        r = max(r * 0.9, 40.0)
        pts = self._circle_points(float(x), float(y), r, 32)
        pts = np.vstack([pts, pts[:1]])
        ring = scene.visuals.Line(
            pos=pts,
            color=(0.1, 0.35, 0.85, 0.95),
            parent=self._view.scene,
            width=2,
        )
        self._origin_markers.append(ring)
        try:
            txt = scene.visuals.Text(
                "起点",
                color=(0.1, 0.35, 0.85, 1.0),
                font_size=9,
                pos=(float(x) + r * 1.3, float(y) + r * 1.3),
                anchor_x="left",
                anchor_y="bottom",
                parent=self._view.scene,
            )
            self._origin_markers.append(txt)
        except Exception:
            pass

    def clear_origin_marker(self):
        for m in getattr(self, "_origin_markers", []) or []:
            try:
                m.parent = None
            except Exception:
                pass
        self._origin_markers = []

    def clear_selection(self):
        for m in self._selection_markers:
            m.parent = None
        self._selection_markers.clear()

    def set_trajectory_path(self, xs, ys):
        self.clear_trajectory_path()
        if len(xs) < 2:
            return
        self._traj_line = scene.visuals.Line(
            pos=np.column_stack([xs, ys]).astype(np.float32),
            color=(0.35, 0.35, 0.38, 0.95),
            parent=self._view.scene,
            width=2,
            method="gl",
        )

    def clear_trajectory_path(self):
        if self._traj_line is not None:
            self._traj_line.parent = None
            self._traj_line = None

    def render(self):
        self._canvas.update()

    def render_to_array(self, alpha: bool = True) -> np.ndarray | None:
        """Capture the current scene as (H, W, 3|4) uint8.

        Returns None if OpenGL context is unavailable (e.g. Qt offscreen
        without GL). Prefer this for automated pixel tests.
        """
        if self._canvas is None:
            return None
        try:
            # Force a draw before readback
            try:
                self._canvas.update()
            except Exception:
                pass
            img = self._canvas.render(alpha=alpha)
            if img is None:
                return None
            arr = np.asarray(img)
            if arr.ndim != 3 or arr.shape[2] < 3:
                return None
            if arr.dtype != np.uint8:
                # vispy may return float 0–1
                if arr.dtype.kind == "f" and arr.max() <= 1.0 + 1e-6:
                    arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
                else:
                    arr = np.clip(arr, 0, 255).astype(np.uint8)
            return arr
        except Exception:
            return None

    def clear_all(self):
        self.clear_walls()
        self.clear_selection()
        self.clear_origin_marker()
        self.clear_trajectory_path()
        if self._mesh is not None:
            self._mesh.parent = None
            self._mesh = None
        self._last_n = 0
        self._canvas.update()

    @staticmethod
    def _circle_points(cx, cy, r, n=32):
        angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
        pts = np.column_stack([cx + r * np.cos(angles), cy + r * np.sin(angles)])
        return pts.astype(np.float32)
