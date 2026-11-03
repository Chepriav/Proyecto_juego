"""Lo que no puede pasar aunque cualquiera tenga el enlace."""

import random

from fastapi.testclient import TestClient

from app import main
from app.juego import Sala
from app.main import app

cliente = TestClient(app)


def crear(nombre="Ana"):
    r = cliente.post("/api/salas", json={"nombre": nombre})
    return r.json()["codigo"], {"X-Token": r.json()["token"]}


def entrar(codigo, nombre):
    r = cliente.post(f"/api/salas/{codigo}/entrar", json={"nombre": nombre})
    return {"X-Token": r.json()["token"]}


def test_nadie_ve_el_token_de_otro():
    codigo, ana = crear()
    bea = entrar(codigo, "Bea")
    texto = cliente.get(f"/api/salas/{codigo}", headers=bea).text
    assert ana["X-Token"] not in texto
    assert bea["X-Token"] not in texto


def test_los_codigos_nuevos_son_de_seis_letras():
    codigo, _ = crear()
    assert len(codigo) == 6 and codigo.isalpha() and codigo.isupper()


def test_un_codigo_con_otro_formato_ni_se_busca():
    _, ana = crear()
    for raro in ("ABCD:X", "SALA:ABCD", "A" * 30, "AB1234", "ab"):
        assert cliente.get(f"/api/salas/{raro}", headers=ana).status_code == 404


def test_crear_partidas_sin_parar_acaba_frenado():
    respuestas = [
        cliente.post("/api/salas", json={"nombre": "Spam"}).status_code
        for _ in range(main.LIMITES["crear"] + 1)
    ]
    assert respuestas[-1] == 429
    assert set(respuestas[:-1]) == {200}


def test_probar_codigos_para_colarse_acaba_frenado():
    codigos = (
        cliente.post("/api/salas/ZZZZZZ/entrar", json={"nombre": "Fisgón"}).status_code
        for _ in range(main.LIMITES["entrar"] + 1)
    )
    assert list(codigos)[-1] == 429


def test_el_freno_es_por_conexion_no_para_todos():
    for _ in range(main.LIMITES["crear"]):
        cliente.post("/api/salas", json={"nombre": "Spam"}, headers={"x-real-ip": "1.1.1.1"})
    r = cliente.post("/api/salas", json={"nombre": "Ana"}, headers={"x-real-ip": "2.2.2.2"})
    assert r.status_code == 200


def test_un_nombre_enorme_ni_se_procesa():
    r = cliente.post("/api/salas", json={"nombre": "x" * 5000})
    assert r.status_code == 422


def test_los_caracteres_invisibles_se_quitan_del_nombre():
    sala = Sala(codigo="ABCDEF", creada=0, rng=random.Random(1))
    # El de dar la vuelta al texto y el espacio de anchura cero
    jugador = sala.unirse("‮Ana​", 0)
    assert jugador.nombre == "Ana"


def test_no_se_puede_imitar_un_nombre_con_caracteres_invisibles():
    sala = Sala(codigo="ABCDEF", creada=0, rng=random.Random(1))
    sala.unirse("Ana", 0)
    try:
        sala.unirse("A​na", 0)
    except Exception as e:
        assert "ese nombre" in str(e)
    else:
        raise AssertionError("ha dejado entrar a una segunda Ana")


def test_las_respuestas_llevan_las_cabeceras_de_seguridad():
    for ruta in ("/", "/api/opciones"):
        cabeceras = cliente.get(ruta).headers
        assert "default-src 'self'" in cabeceras["content-security-policy"]
        assert cabeceras["x-frame-options"] == "DENY"
        assert cabeceras["x-content-type-options"] == "nosniff"
    assert cliente.get("/api/opciones").headers["cache-control"] == "no-store"


def test_no_se_publica_el_esquema_de_la_api():
    assert cliente.get("/openapi.json").headers["content-type"].startswith("text/html")
    assert cliente.get("/docs").headers["content-type"].startswith("text/html")
