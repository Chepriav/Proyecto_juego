"""Quien crea la partida manda: con el enlace circulando, nadie más puede estropearla."""

import random

import pytest
from fastapi.testclient import TestClient

from app import juego
from app.juego import ErrorDeJuego, Sala
from app.main import app

T = 1000.0
cliente = TestClient(app)


def sala_de(*nombres):
    sala = Sala(codigo="ABCDEF", creada=T, rng=random.Random(1))
    return sala, [sala.unirse(n, T) for n in nombres]


def test_solo_quien_crea_la_partida_la_configura_y_la_empieza():
    r = cliente.post("/api/salas", json={"nombre": "Ana"}).json()
    sala = f"/api/salas/{r['codigo']}"
    ana = {"X-Token": r["token"]}
    bea = {"X-Token": cliente.post(f"{sala}/entrar", json={"nombre": "Bea"}).json()["token"]}
    ajustes = {"rondas": 4, "del_grupo": False}
    assert cliente.post(f"{sala}/ajustes", headers=bea, json=ajustes).status_code == 400
    assert cliente.post(f"{sala}/empezar", headers=bea).status_code == 400
    assert cliente.post(f"{sala}/ajustes", headers=ana, json=ajustes).status_code == 200
    assert cliente.post(f"{sala}/empezar", headers=ana).status_code == 200


def test_quien_manda_puede_echar_y_el_echado_no_vuelve_con_su_nombre():
    sala, (ana, bea, carlos) = sala_de("Ana", "Bea", "Carlos")
    sala.echar(ana, carlos.id, T)
    assert [j.nombre for j in sala.jugadores] == ["Ana", "Bea"]
    with pytest.raises(ErrorDeJuego):
        sala.unirse("carlos", T)


def test_nadie_mas_puede_echar():
    sala, (ana, bea, carlos) = sala_de("Ana", "Bea", "Carlos")
    with pytest.raises(ErrorDeJuego):
        sala.echar(bea, carlos.id, T)


def test_echar_a_alguien_en_plena_partida_no_para_la_nave():
    sala, (ana, bea, carlos) = sala_de("Ana", "Bea", "Carlos")
    sala.configurar(8, False)
    sala.empezar(T)
    sala.jugar(ana, "abrir", 10, T)
    assert sala.ronda.turno == bea.id
    sala.echar(ana, bea.id, T)
    assert sala.ronda.turno == carlos.id


def test_si_quien_manda_se_va_manda_el_siguiente():
    sala, (ana, bea, carlos) = sala_de("Ana", "Bea", "Carlos")
    sala.configurar(8, False)
    sala.empezar(T)
    sala.salir(ana, T)
    sala.revisar_anfitrion(T)
    assert sala.anfitrion == bea.id


def test_si_quien_manda_desaparece_manda_el_siguiente_conectado():
    sala, (ana, bea, carlos) = sala_de("Ana", "Bea", "Carlos")
    luego = T + juego.SEGUNDOS_FUERA + 1
    carlos.visto = luego
    sala.revisar_anfitrion(luego)
    assert sala.anfitrion == carlos.id


def test_al_echado_se_le_dice_que_le_han_echado():
    sala, (ana, bea, carlos) = sala_de("Ana", "Bea", "Carlos")
    sala.configurar(8, False)
    sala.empezar(T)
    sala.echar(ana, carlos.id, T)
    with pytest.raises(ErrorDeJuego, match="echado"):
        sala.por_token(carlos.token)
