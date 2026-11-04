"""Entrada de Vercel: una función que atiende todo lo de /api con la misma app."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402, F401
