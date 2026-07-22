"""Selection / start-frame gate unit tests (no GUI imports)."""
from __future__ import annotations

import unittest

from zdem_particle_tracker.widgets.selection_logic import id_allowed_at_session_start


class TestStartFrameGate(unittest.TestCase):
    def test_allowed(self):
        self.assertTrue(id_allowed_at_session_start({10, 20, 30}, 20))

    def test_rejected(self):
        self.assertFalse(id_allowed_at_session_start({10, 20}, 99))

    def test_none_set(self):
        self.assertFalse(id_allowed_at_session_start(None, 1))


if __name__ == "__main__":
    unittest.main()
