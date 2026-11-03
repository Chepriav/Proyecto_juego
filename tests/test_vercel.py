import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def test_la_funcion_de_vercel_arranca_sin_la_carpeta_public(tmp_path):
    # Vercel sirve public/ por su CDN y no la mete en la función.
    for carpeta in ("app", "api"):
        shutil.copytree(RAIZ / carpeta, tmp_path / carpeta)
    programa = (
        "import runpy\n"
        "from starlette.testclient import TestClient\n"
        "app = runpy.run_path('api/index.py')['app']\n"
        "r = TestClient(app).get('/api/nada')\n"
        "assert r.status_code == 404, r.text\n"
    )
    resultado = subprocess.run(
        [sys.executable, "-c", programa],
        cwd=tmp_path,
        env={"VERCEL": "1", "KV_REST_API_URL": "https://x", "KV_REST_API_TOKEN": "t"},
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stderr
