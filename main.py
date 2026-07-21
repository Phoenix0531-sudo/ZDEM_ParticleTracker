#!/usr/bin/env python3
"""ZDEM Particle Tracker - 2D particle tracking application."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from zdem_particle_tracker.app import main

if __name__ == "__main__":
    sys.exit(main())
