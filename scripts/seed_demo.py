"""Launch the demo seeder from the repository root.

Thin wrapper around apps/backend/scripts/seed_demo.py. The canonical seeder
lives with the backend package so it also runs inside the API container
(`docker compose exec backend python -m scripts.seed_demo`).
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "backend"))

if __name__ == "__main__":
    runpy.run_module("scripts.seed_demo", run_name="__main__")
