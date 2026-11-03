import pytest

from app import main
from app.almacen import Memoria


@pytest.fixture(autouse=True)
def almacen_limpio(monkeypatch):
    # Cada test con su almacén: así los límites por IP de uno no frenan al siguiente.
    monkeypatch.setattr(main, "almacen", Memoria())
