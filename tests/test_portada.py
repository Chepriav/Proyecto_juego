import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)
RAIZ = Path(__file__).resolve().parent.parent


def test_en_la_raiz_esta_la_sala_de_juegos():
    r = cliente.get("/")
    assert r.status_code == 200
    assert "Sala de juegos" in r.text
    assert 'href="/nave"' in r.text


def test_la_nave_tiene_su_direccion_y_sus_enlaces_de_sala():
    for ruta in ("/nave", "/nave/", "/s/ABCDEF"):
        r = cliente.get(ruta)
        assert r.status_code == 200, ruta
        assert "<title>¡Paren la nave!</title>" in r.text, ruta


def test_cada_juego_de_la_portada_abre_su_pagina():
    pagina = cliente.get("/").text
    enlaces = re.findall(r'class="ficha" href="([^"]+)"', pagina)
    assert enlaces
    for enlace in enlaces:
        assert "Sala de juegos" not in cliente.get(enlace).text, enlace


def test_lo_que_pide_la_portada_existe():
    pagina = cliente.get("/").text
    for recurso in re.findall(r'(?:href|src)="(/(?:estaticos|portada)/[^"]+)"', pagina):
        assert cliente.get(recurso).status_code == 200, recurso
    hoja = cliente.get("/portada/portada.css").text
    for fuente in re.findall(r'url\("([^"]+)"\)', hoja):
        assert cliente.get(fuente).status_code == 200, fuente


def test_vercel_lleva_la_nave_y_sus_salas_a_su_pagina():
    config = json.loads((RAIZ / "vercel.json").read_text())
    reglas = {r["source"]: r["destination"] for r in config["rewrites"]}
    assert reglas["/nave"] == "/nave/index.html"
    assert reglas["/s/(.*)"] == "/nave/index.html"
    assert (RAIZ / "public" / "nave" / "index.html").exists()


def test_desde_la_nave_se_vuelve_a_la_sala():
    assert 'class="volver-sala" href="/"' in cliente.get("/estaticos/app.js").text
