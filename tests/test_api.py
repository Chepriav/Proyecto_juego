import json

from fastapi.testclient import TestClient

from app import main
from app.almacen import Memoria
from app.main import app

cliente = TestClient(app)


def entrar(codigo: str | None, nombre: str) -> tuple[str, dict]:
    if codigo is None:
        r = cliente.post("/api/salas", json={"nombre": nombre})
    else:
        r = cliente.post(f"/api/salas/{codigo}/entrar", json={"nombre": nombre})
    assert r.status_code == 200, r.text
    datos = r.json()
    return datos["codigo"], {"X-Token": datos["token"]}


def test_una_partida_de_principio_a_fin_por_la_api():
    codigo, ana = entrar(None, "Ana")
    _, bea = entrar(codigo, "Bea")
    cliente.post(
        f"/api/salas/{codigo}/ajustes", json={"rondas": 4, "del_grupo": False}, headers=ana
    )
    estado = cliente.post(f"/api/salas/{codigo}/empezar", headers=ana).json()
    assert estado["fase"] == "jugando"

    tokens = {}
    for cabecera in (ana, bea):
        tokens[cliente.get(f"/api/salas/{codigo}", headers=cabecera).json()["yo"]] = cabecera
    for numero in range(1, 5):
        ronda = cliente.get(f"/api/salas/{codigo}", headers=ana).json()["ronda"]
        assert ronda["respuesta"] is None
        abre = tokens[ronda["abre"]]
        otro = bea if abre is ana else ana
        cliente.post(
            f"/api/salas/{codigo}/jugada", json={"accion": "abrir", "cifra": 0}, headers=abre
        )
        r = cliente.post(f"/api/salas/{codigo}/jugada", json={"accion": "quedarse"}, headers=otro)
        assert r.json()["ronda"]["revelada"]
        cliente.post(f"/api/salas/{codigo}/siguiente", json={"desde": numero}, headers=ana)

    assert cliente.get(f"/api/salas/{codigo}", headers=ana).json()["fase"] == "fin"


def test_los_errores_llegan_en_español_para_el_jugador():
    codigo, ana = entrar(None, "Ana")
    r = cliente.post(f"/api/salas/{codigo}/empezar", headers=ana)
    assert r.status_code == 400
    assert "Pásale el enlace" in r.json()["detail"]


def test_sin_token_no_se_ve_la_partida():
    codigo, _ = entrar(None, "Ana")
    assert cliente.get(f"/api/salas/{codigo}").status_code == 400


def test_una_sala_que_no_existe_es_un_404():
    assert cliente.get("/api/salas/ZZZZ", headers={"X-Token": "x"}).status_code == 404


def test_el_codigo_vale_en_minusculas():
    codigo, ana = entrar(None, "Ana")
    entrar(codigo.lower(), "Bea")
    estado = cliente.get(f"/api/salas/{codigo}", headers=ana).json()
    assert len(estado["jugadores"]) == 2


class Espia(Memoria):
    """Cuenta las escrituras y, si se le pide, simula que otro se adelanta."""

    def __init__(self):
        super().__init__()
        self.escrituras = 0
        self.adelantos = 0

    def guardar_si(self, codigo, antes, despues):
        self.escrituras += 1
        if self.adelantos:
            self.adelantos -= 1
            # Otro jugador entra justo entre la lectura y la escritura.
            sala = json.loads(antes)
            sala["rondas_total"] = 12
            super().guardar_si(codigo, antes, json.dumps(sala))
        return super().guardar_si(codigo, antes, despues)


def test_mirar_la_partida_no_escribe_si_no_cambia_nada(monkeypatch):
    espia = Espia()
    monkeypatch.setattr(main, "almacen", espia)
    codigo, ana = entrar(None, "Ana")
    for _ in range(5):
        cliente.get(f"/api/salas/{codigo}", headers=ana)
    assert espia.escrituras == 0


def test_si_otro_se_adelanta_se_reintenta_sin_perder_nada(monkeypatch):
    espia = Espia()
    monkeypatch.setattr(main, "almacen", espia)
    codigo, ana = entrar(None, "Ana")
    espia.adelantos = 2
    _, bea = entrar(codigo, "Bea")
    estado = cliente.get(f"/api/salas/{codigo}", headers=bea).json()
    assert [j["nombre"] for j in estado["jugadores"]] == ["Ana", "Bea"]
    assert estado["rondas_total"] == 12


def test_sin_base_de_datos_en_vercel_lo_dice_claro(monkeypatch):
    monkeypatch.setattr(main, "almacen", None)
    r = cliente.post("/api/salas", json={"nombre": "Ana"})
    assert r.status_code == 503
    assert "Upstash" in r.json()["detail"]


def test_el_enlace_de_la_sala_sirve_la_pagina():
    r = cliente.get("/s/ABCD")
    assert r.status_code == 200
    assert "Paren la nave" in r.text


def test_una_ruta_de_api_que_no_existe_no_es_la_pagina():
    assert cliente.get("/api/nada").status_code == 404


def test_cada_respuesta_dice_que_version_hay_publicada():
    assert cliente.get("/api/opciones").headers["x-version"] == main.VERSION


def test_la_app_se_puede_instalar_con_su_icono():
    manifiesto = cliente.get("/estaticos/manifest.webmanifest").json()
    assert manifiesto["display"] == "standalone"
    for icono in manifiesto["icons"]:
        assert cliente.get(icono["src"]).status_code == 200
    pagina = cliente.get("/nave").text
    assert "apple-touch-icon" in pagina and "manifest.webmanifest" in pagina
    assert cliente.get("/estaticos/iconos/apple-touch-icon.png").status_code == 200
