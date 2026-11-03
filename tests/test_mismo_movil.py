"""Quien no tiene móvil juega en el de otro, pasándoselo cuando le toca."""

import random

import pytest
from fastapi.testclient import TestClient

from app import juego
from app.juego import ErrorDeJuego, Sala
from app.main import app
from app.preguntas import PREGUNTAS_ALIEN

T = 1000.0
cliente = TestClient(app)


def sala_de(*nombres):
    sala = Sala(codigo="ABCDEF", creada=T, rng=random.Random(1))
    return sala, [sala.unirse(n, T) for n in nombres]


def test_se_puede_jugar_en_el_movil_de_otro_y_entra_en_los_turnos():
    sala, (ana, bea) = sala_de("Ana", "Bea")
    lucia = sala.acompanar(ana, "Lucía", T)
    assert lucia.movil == ana.id
    sala.configurar(8, False)
    sala.empezar(T)
    assert lucia.id in sala.ronda.orden


def test_mientras_el_movil_siga_abierto_quien_juega_en_el_no_se_da_por_ido():
    r = cliente.post("/api/salas", json={"nombre": "Ana"}).json()
    sala = f"/api/salas/{r['codigo']}"
    ana = {"X-Token": r["token"]}
    lucia = cliente.post(f"{sala}/acompanante", headers=ana, json={"nombre": "Lucía"}).json()
    assert lucia["nombre"] == "Lucía"
    estado = cliente.get(sala, headers=ana).json()
    suya = next(j for j in estado["jugadores"] if j["nombre"] == "Lucía")
    assert suya["movil"] == estado["yo"] and suya["conectado"]
    # Su token vale para jugar su turno
    assert cliente.get(sala, headers={"X-Token": lucia["token"]}).json()["yo"] == lucia["id"]


def test_presencia_compartida():
    sala, (ana, bea) = sala_de("Ana", "Bea")
    lucia = sala.acompanar(ana, "Lucía", T)
    assert [j.nombre for j in sala.mismo_movil(lucia)] == ["Ana", "Lucía"]
    assert [j.nombre for j in sala.mismo_movil(ana)] == ["Ana", "Lucía"]


def test_todos_en_un_movil_el_alien_rota_y_sin_preguntas_de_movil():
    sala, (ana,) = sala_de("Ana")
    sala.categorias = ["picantes"]
    lucia = sala.acompanar(ana, "Lucía", T)
    pablo = sala.acompanar(ana, "Pablo", T)
    activos = [ana, lucia, pablo]
    textos_sin_movil = {p.para_alien for p in PREGUNTAS_ALIEN if p.sin_movil}
    aliens = []
    for numero in range(2, 38, 2):
        sala._ronda_alien(numero, activos, T)
        aliens.append(sala.ronda.alien)
        if sala.ronda.alien != ana.id:
            assert sala.ronda.texto_alien in textos_sin_movil
    # A cada uno le toca las mismas veces: ya no siempre al dueño del móvil.
    assert sorted(aliens.count(j.id) for j in activos) == [6, 6, 6]


def test_hay_preguntas_del_alien_para_quien_no_tiene_movil():
    sin_movil = [p for p in PREGUNTAS_ALIEN if p.sin_movil]
    assert len([p for p in sin_movil if not p.picante]) >= 10
    assert any(p.picante for p in sin_movil)


def test_quien_juega_en_el_movil_de_otro_no_hereda_el_mando():
    sala, (ana, bea) = sala_de("Ana", "Bea")
    sala.acompanar(ana, "Lucía", T)
    sala.salir(ana, T)
    sala.revisar_anfitrion(T)
    assert sala.anfitrion == bea.id


def test_no_se_anade_desde_un_movil_prestado_ni_sin_limite():
    sala, (ana,) = sala_de("Ana")
    lucia = sala.acompanar(ana, "Lucía", T)
    with pytest.raises(ErrorDeJuego):
        sala.acompanar(lucia, "Pablo", T)
    for n in range(juego.MAX_POR_MOVIL - 2):
        sala.acompanar(ana, f"Niño {n}", T)
    with pytest.raises(ErrorDeJuego):
        sala.acompanar(ana, "Uno más", T)
