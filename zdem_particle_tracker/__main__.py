"""Entry point for `python -m zdem_particle_tracker` — same as app.main."""
from __future__ import annotations

import sys

from .app import main

if __name__ == "__main__":
    sys.exit(main())
