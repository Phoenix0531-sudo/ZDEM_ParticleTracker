# ZDEM Particle Tracker — Full Code Review & Optimization Plan

## Issues Found (Manual Review)

### 🎨 Rendering (Critical — VisPy migration)
- **pyqtgraph ScatterPlotItem** ~30-50ms for 50k pts (OK), but zoom/pan is CPU-bound
- **VisPy** 50k pts in 56ms with GPU acceleration, smoother interaction
- **Plan**: Replace with VisPy Markers visual (GPU)

### ⚡ File Parsing (Performance bottleneck)
- **300ms per file × 21 files = 6.3s sequential**
- Current: background thread parses files one-by-one
- **Fix**: `concurrent.futures.ThreadPoolExecutor(max_workers=4)` parallel parsing
- **Fix**: Pre-cache all frames during trajectory extraction

### 💾 Memory 
- 21 frames × 50k particles × (id+i+x+y+rad+color) ≈ 50MB for all cached frames
- **Fix**: LRU cache with max 10 frames (add to `_frame_cache`)

### 🖥️ UI/UX
- **Plain QGroupBox styling** — needs macOS-like cards
- **Right panel labels overlap** — QHBoxLayout in 220px width causes text clipping
- **No loading indicator during track** — status bar message is subtle
- **No auto-scroll on table update** — scroll to bottom after tracking

### 🐛 Bugs
- **`_on_track` lambda captures pid by value** — OK, but `finfos` captures `self._frame_files` which could change
- **Track button doesn't disable during extraction** — user can click twice
- **Trajectory path overlay not cleared on frame change** — stays visible when switching frames

## VisPy Migration Plan
1. `rendering/vispy_renderer.py` — GPU-accelerated particle renderer
2. Embed via `vispy.app.Canvas` in QWidget
3. Markers for particles, Line for walls/selection
4. PanZoomCamera for 2D with aspect lock
5. Keep pyqtgraph as fallback for displacement plots
