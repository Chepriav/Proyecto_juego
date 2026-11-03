import random

import pytest

from app import juego, preguntas
from app.juego import ErrorDeJuego, Sala, puntuar
from app.preguntas import Pregunta

T = 1000.0


def sala_con(*nombres: str, del_grupo: bool = False) -> tuple[Sala, list]:
    sala = Sala(codigo="ABCD", creada=T, rng=random.Random(1))
    jugadores = [sala.unirse(n, T) for n in nombres]
    sala.configurar(8, del_grupo)
    return sala, jugadores


def con_pregunta(sala: Sala, respuesta: int, año: bool = False) -> None:
    sala.ronda.pregunta = Pregunta("¿Cuántos?", respuesta, año)


# --- Puntuación ------------------------------------------------------------------


def test_si_la_nave_llega_puntuan_capitan_y_tripulacion():
    puntos, llega, cerca = puntuar(100, False, "a", 50, ["a", "b"], ["c"])
    assert llega and not cerca
    assert puntos == {"a": juego.PUNTOS_CAPITAN, "b": juego.PUNTOS_TRIPULANTE, "c": 0}


def test_si_se_estrella_puntuan_los_que_se_bajaron():
    puntos, llega, _ = puntuar(100, False, "a", 101, ["a", "b"], ["c"])
    assert not llega
    assert puntos == {"a": 0, "b": 0, "c": juego.PUNTOS_BAJADO}


def test_acertar_justo_llega():
    _, llega, cerca = puntuar(100, False, "a", 100, ["a"], [])
    assert llega and cerca


def test_el_capitan_que_se_queda_cerca_suma_mas():
    puntos, _, cerca = puntuar(100, False, "a", 91, ["a"], [])
    assert cerca
    assert puntos["a"] == juego.PUNTOS_CAPITAN + juego.PUNTOS_CERCA


def test_en_los_años_cerca_se_mide_en_años_no_en_porcentaje():
    # Un 10 % de 1969 serían dos siglos.
    assert juego.es_cerca(1965, 1969, año=True)
    assert not juego.es_cerca(1900, 1969, año=True)


# --- Turnos ----------------------------------------------------------------------


def test_abre_dice_la_cifra_y_se_sienta_de_capitan():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos")
    sala.empezar(T)
    r = sala.ronda
    assert r.turno == ana.id
    sala.jugar(ana, "abrir", 10, T)
    assert r.capitan == ana.id and r.cifra == 10
    assert r.turno == bea.id


def test_solo_juega_a_quien_le_toca():
    sala, (ana, bea) = sala_con("Ana", "Bea")
    sala.empezar(T)
    with pytest.raises(ErrorDeJuego):
        sala.jugar(bea, "abrir", 10, T)


def test_subir_tiene_que_pasar_de_la_cifra():
    sala, (ana, bea) = sala_con("Ana", "Bea")
    sala.empezar(T)
    sala.jugar(ana, "abrir", 10, T)
    with pytest.raises(ErrorDeJuego):
        sala.jugar(bea, "subir", 10, T)


def test_tras_subir_los_demas_vuelven_a_tener_turno():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos")
    sala.empezar(T)
    r = sala.ronda
    sala.jugar(ana, "abrir", 10, T)
    sala.jugar(bea, "quedarse", None, T)
    sala.jugar(carlos, "subir", 20, T)
    # Ana y Bea, que ya habían pasado, tienen que decidir otra vez.
    assert r.pendientes == [ana.id, bea.id]
    assert r.capitan == carlos.id


def test_cuando_nadie_sube_se_revela_y_se_reparten_los_puntos():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos")
    sala.empezar(T)
    con_pregunta(sala, 100)
    sala.jugar(ana, "abrir", 50, T)
    sala.jugar(bea, "bajarse", None, T)
    sala.jugar(carlos, "quedarse", None, T)
    r = sala.ronda
    assert r.revelada and r.llega
    assert (ana.puntos, bea.puntos, carlos.puntos) == (
        juego.PUNTOS_CAPITAN,
        0,
        juego.PUNTOS_TRIPULANTE,
    )


def test_quien_se_baja_ya_no_vuelve_a_jugar_la_ronda():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos")
    sala.empezar(T)
    con_pregunta(sala, 100)
    sala.jugar(ana, "abrir", 50, T)
    sala.jugar(bea, "bajarse", None, T)
    sala.jugar(carlos, "subir", 200, T)
    assert sala.ronda.pendientes == [ana.id]
    sala.jugar(ana, "quedarse", None, T)
    assert sala.ronda.revelada and not sala.ronda.llega
    assert bea.puntos == juego.PUNTOS_BAJADO


def test_si_se_bajan_todos_menos_el_capitan_se_acaba():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos")
    sala.empezar(T)
    sala.jugar(ana, "abrir", 50, T)
    sala.jugar(bea, "bajarse", None, T)
    sala.jugar(carlos, "bajarse", None, T)
    assert sala.ronda.revelada


def test_quien_abre_va_rotando():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos")
    sala.empezar(T)
    sala.jugar(ana, "abrir", 0, T)
    sala.jugar(bea, "quedarse", None, T)
    sala.jugar(carlos, "quedarse", None, T)
    sala.siguiente(T, desde=1)
    assert sala.ronda.abre == bea.id


def test_pasar_de_ronda_dos_veces_a_la_vez_pasa_una_sola():
    sala, (ana, bea) = sala_con("Ana", "Bea")
    sala.empezar(T)
    sala.jugar(ana, "abrir", 0, T)
    sala.jugar(bea, "quedarse", None, T)
    sala.siguiente(T, desde=1)
    sala.siguiente(T, desde=1)
    assert sala.ronda.numero == 2


def test_tras_la_ultima_ronda_se_acaba_la_partida():
    sala, (ana, bea) = sala_con("Ana", "Bea")
    sala.configurar(4, False)
    sala.empezar(T)
    for n in range(1, 5):
        abre = sala.por_id(sala.ronda.abre)
        otro = bea if abre is ana else ana
        sala.jugar(abre, "abrir", 0, T)
        sala.jugar(otro, "quedarse", None, T)
        sala.siguiente(T, desde=n)
    assert sala.fase == "fin"


def test_volver_a_jugar_pone_los_puntos_a_cero():
    sala, (ana, bea) = sala_con("Ana", "Bea")
    ana.puntos = 7
    sala.fase = "fin"
    sala.empezar(T)
    assert ana.puntos == 0


def test_hace_falta_otro_jugador_para_despegar():
    sala, _ = sala_con("Ana")
    with pytest.raises(ErrorDeJuego):
        sala.empezar(T)


# --- Quien no contesta -----------------------------------------------------------


def test_si_se_agota_el_tiempo_se_queda():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos")
    sala.empezar(T)
    sala.jugar(ana, "abrir", 10, T)
    luego = T + juego.SEGUNDOS_TURNO + 1
    for j in (ana, bea, carlos):
        j.visto = luego
    sala.comprobar_tiempo(luego)
    assert sala.ronda.turno == carlos.id
    assert bea.id in sala.ronda.a_bordo


def test_quien_cierra_la_app_no_deja_la_nave_parada():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos")
    sala.empezar(T)
    luego = T + juego.SEGUNDOS_AUSENTE + 1
    bea.visto = carlos.visto = luego
    sala.comprobar_tiempo(luego)
    # Ana no aparece: abre la siguiente.
    assert sala.ronda.abre == bea.id


def test_la_ronda_siguiente_empieza_sin_quien_se_fue():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos")
    sala.empezar(T)
    sala.jugar(ana, "abrir", 0, T)
    sala.jugar(bea, "quedarse", None, T)
    sala.jugar(carlos, "quedarse", None, T)
    luego = T + juego.SEGUNDOS_FUERA + 1
    ana.visto = bea.visto = luego
    sala.siguiente(luego, desde=1)
    assert carlos.id not in sala.ronda.orden


# --- Rondas del alien ------------------------------------------------------------


def a_la_ronda_2(sala, ana, bea, carlos):
    sala.empezar(T)
    sala.jugar(ana, "abrir", 0, T)
    sala.jugar(bea, "quedarse", None, T)
    sala.jugar(carlos, "quedarse", None, T)
    sala.siguiente(T, desde=1)
    return sala.ronda


def jugar_la_ronda(sala, r, cifra):
    """El que abre dice `cifra` y los demás se quedan."""
    sala.jugar(sala.por_id(r.abre), "abrir", cifra, T)
    while not r.revelada:
        sala.jugar(sala.por_id(r.turno), "quedarse", None, T)


def test_las_rondas_pares_son_de_un_alien_que_no_juega():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos", del_grupo=True)
    r = a_la_ronda_2(sala, ana, bea, carlos)
    assert r.alien is not None
    assert r.alien not in r.orden
    nombre = sala.por_id(r.alien).nombre
    assert nombre in r.pregunta.texto


def test_el_alien_escribe_su_respuesta_antes_de_que_jueguen_los_demas():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos", del_grupo=True)
    r = a_la_ronda_2(sala, ana, bea, carlos)
    alien = sala.por_id(r.alien)
    otro = sala.por_id(r.abre)
    assert r.turno == alien.id
    with pytest.raises(ErrorDeJuego):
        sala.jugar(otro, "abrir", 5, T)
    sala.jugar(alien, "secreto", 1234, T)
    assert r.pregunta.respuesta == 1234
    assert r.turno == otro.id


def test_el_alien_ve_la_pregunta_sobre_si_y_su_respuesta_los_demas_no():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos", del_grupo=True)
    r = a_la_ronda_2(sala, ana, bea, carlos)
    alien = sala.por_id(r.alien)
    otro = sala.por_id(r.abre)
    sala.jugar(alien, "secreto", 77, T)
    suya, ajena = sala.vista(alien, T)["ronda"], sala.vista(otro, T)["ronda"]
    assert suya["pregunta"] == r.texto_alien
    assert alien.nombre not in suya["pregunta"]
    assert alien.nombre in ajena["pregunta"]
    assert suya["respuesta"] == 77
    assert ajena["respuesta"] is None


def test_si_la_aciertan_el_alien_pierde_puntos():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos", del_grupo=True)
    r = a_la_ronda_2(sala, ana, bea, carlos)
    alien = sala.por_id(r.alien)
    alien.puntos = 5
    sala.jugar(alien, "secreto", 100, T)
    jugar_la_ronda(sala, r, 95)
    assert r.llega and r.cerca
    assert alien.puntos == 5 - juego.PUNTOS_ALIEN


def test_si_fallan_el_alien_gana_puntos():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos", del_grupo=True)
    r = a_la_ronda_2(sala, ana, bea, carlos)
    alien = sala.por_id(r.alien)
    antes = alien.puntos
    sala.jugar(alien, "secreto", 100, T)
    jugar_la_ronda(sala, r, 500)
    assert not r.llega
    assert alien.puntos == antes + juego.PUNTOS_ALIEN


def test_quedarse_corto_tambien_es_fallar():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos", del_grupo=True)
    r = a_la_ronda_2(sala, ana, bea, carlos)
    alien = sala.por_id(r.alien)
    antes = alien.puntos
    sala.jugar(alien, "secreto", 100, T)
    jugar_la_ronda(sala, r, 10)
    assert r.llega and not r.cerca
    assert alien.puntos == antes + juego.PUNTOS_ALIEN


def test_el_alien_no_baja_de_cero():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos", del_grupo=True)
    r = a_la_ronda_2(sala, ana, bea, carlos)
    alien = sala.por_id(r.alien)
    alien.puntos = 1
    sala.jugar(alien, "secreto", 100, T)
    jugar_la_ronda(sala, r, 100)
    assert alien.puntos == 0


def test_si_el_alien_no_escribe_la_ronda_sigue_con_una_pregunta_normal():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos", del_grupo=True)
    r = a_la_ronda_2(sala, ana, bea, carlos)
    alien = r.alien
    luego = T + juego.SEGUNDOS_ALIEN + 1
    for j in (ana, bea, carlos):
        j.visto = luego
    sala.comprobar_tiempo(luego)
    assert r.alien is None and not r.escribiendo
    assert alien in r.orden and alien in r.a_bordo
    assert r.turno == r.abre


def test_el_alien_va_rotando_y_no_repite_pregunta():
    sala, jugadores = sala_con("Ana", "Bea", "Carlos", del_grupo=True)
    aliens, preguntas = set(), set()
    for numero in (2, 4, 6):
        sala._ronda_alien(numero, jugadores, T)
        aliens.add(sala.ronda.alien)
        preguntas.add(sala.ronda.texto_alien)
    assert len(aliens) == 3
    assert len(preguntas) == 3


def test_con_dos_no_hay_alien():
    sala, (ana, bea) = sala_con("Ana", "Bea", del_grupo=True)
    sala.empezar(T)
    sala.jugar(ana, "abrir", 0, T)
    sala.jugar(bea, "quedarse", None, T)
    sala.siguiente(T, desde=1)
    assert sala.ronda.alien is None


def test_sin_rondas_del_grupo_no_hay_alien():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos", del_grupo=False)
    assert a_la_ronda_2(sala, ana, bea, carlos).alien is None


def test_las_preguntas_del_alien_no_son_de_las_que_se_sabe_la_pareja():
    textos = " ".join(p.para_alien for p in preguntas.PREGUNTAS_ALIEN).lower()
    for conocido in ("naciste", "edad", "mides", "hermanos", "pie"):
        assert conocido not in textos


# --- Entrar ----------------------------------------------------------------------


def test_no_se_repiten_nombres():
    sala, _ = sala_con("Ana")
    with pytest.raises(ErrorDeJuego):
        sala.unirse(" ana ", T)


def test_el_primero_en_entrar_es_el_anfitrion():
    sala, (ana, bea) = sala_con("Ana", "Bea")
    assert sala.anfitrion == ana.id


def test_un_token_que_no_es_de_la_sala_no_entra():
    sala, _ = sala_con("Ana")
    with pytest.raises(ErrorDeJuego):
        sala.por_token("otro")


def test_una_partida_a_medias_se_guarda_y_se_recupera_igual():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos", del_grupo=True)
    sala.empezar(T)
    sala.jugar(ana, "abrir", 10, T)
    sala.jugar(bea, "bajarse", None, T)
    copia = Sala.desde_dict(sala.a_dict())
    assert copia.a_dict() == sala.a_dict()
    copia.jugar(copia.por_id(carlos.id), "subir", 20, T)
    assert copia.ronda.capitan == carlos.id


# --- Salir -----------------------------------------------------------------------


def test_salir_antes_de_empezar_te_quita_de_la_lista():
    sala, (ana, bea) = sala_con("Ana", "Bea")
    sala.salir(ana, T)
    assert [j.nombre for j in sala.jugadores] == ["Bea"]
    assert sala.anfitrion == bea.id


def test_salir_en_tu_turno_no_deja_la_nave_parada():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos")
    sala.empezar(T)
    sala.jugar(ana, "abrir", 10, T)
    sala.salir(bea, T)
    assert sala.ronda.turno == carlos.id


def test_quien_sale_sigue_en_la_clasificacion_pero_no_juega_la_siguiente():
    sala, (ana, bea, carlos) = sala_con("Ana", "Bea", "Carlos")
    sala.empezar(T)
    bea.puntos = 3
    sala.salir(bea, T)
    sala.jugar(ana, "abrir", 0, T)
    # Como hace la API antes de cada jugada: el turno de Bea pasa solo.
    sala.comprobar_tiempo(T)
    sala.jugar(carlos, "quedarse", None, T)
    sala.siguiente(T, desde=1)
    assert bea.id not in sala.ronda.orden
    assert bea in sala.jugadores and bea.puntos == 3


def test_su_enlace_ya_no_vale_pero_si_vuelve_con_su_nombre_recupera_sus_puntos():
    sala, (ana, bea) = sala_con("Ana", "Bea")
    sala.empezar(T)
    bea.puntos = 3
    viejo = bea.token
    sala.salir(bea, T)
    with pytest.raises(ErrorDeJuego):
        sala.por_token(viejo)
    vuelve = sala.unirse("bea", T)
    assert vuelve is bea and bea.puntos == 3 and not bea.se_fue


# --- Categorías y dificultad -----------------------------------------------------


def test_solo_salen_preguntas_de_las_categorias_y_dificultades_elegidas():
    sala, _ = sala_con("Ana", "Bea")
    sala.configurar(8, False, ["deportes", "historia"], ["facil"])
    for _ in range(30):
        p = sala._pregunta_general()
        assert p.categoria in ("deportes", "historia")
        assert p.dificultad == "facil"


def test_se_pueden_elegir_varias_categorias_y_salen_todas():
    sala, _ = sala_con("Ana", "Bea")
    sala.configurar(8, False, ["deportes", "ciencia"], ["facil", "media", "dificil"])
    vistas = {sala._pregunta_general().categoria for _ in range(60)}
    assert vistas == {"deportes", "ciencia"}


def test_las_picantes_no_salen_si_no_se_eligen():
    sala, _ = sala_con("Ana", "Bea")
    assert "picantes" not in sala.categorias
    assert all(sala._pregunta_general().categoria != "picantes" for _ in range(200))


def test_sin_categorias_o_sin_dificultad_no_se_puede_jugar():
    sala, _ = sala_con("Ana", "Bea")
    with pytest.raises(ErrorDeJuego):
        sala.configurar(8, False, [], ["facil"])
    with pytest.raises(ErrorDeJuego):
        sala.configurar(8, False, ["deportes"], [])


def test_no_se_repite_ninguna_pregunta_hasta_que_se_acaban():
    sala, _ = sala_con("Ana", "Bea")
    sala.configurar(8, False, ["picantes"], ["facil"])
    cuantas = sum(
        p.categoria == "picantes" and p.dificultad == "facil" for p in preguntas.GENERALES
    )
    textos = [sala._pregunta_general().texto for _ in range(cuantas)]
    assert len(set(textos)) == cuantas


def test_las_picantes_del_alien_solo_con_picantes():
    sala, jugadores = sala_con("Ana", "Bea", "Carlos", del_grupo=True)
    for numero in range(2, 60, 2):
        sala._ronda_alien(numero, jugadores, T)
        assert not preguntas.ALIEN_POR_CLAVE[_clave(sala.ronda.texto_alien)].picante
    sala.configurar(8, True, ["picantes"], ["media"])
    vistas = set()
    for numero in range(2, 80, 2):
        sala._ronda_alien(numero, jugadores, T)
        vistas.add(preguntas.ALIEN_POR_CLAVE[_clave(sala.ronda.texto_alien)].picante)
    assert vistas == {True, False}


def _clave(texto_alien):
    return next(p.clave for p in preguntas.PREGUNTAS_ALIEN if p.para_alien == texto_alien)


def test_el_banco_es_grande_y_no_repite_preguntas():
    textos = [p.texto for p in preguntas.GENERALES]
    assert len(textos) >= 400
    assert len(set(textos)) == len(textos)
    for categoria in preguntas.CATEGORIAS:
        for dificultad in preguntas.DIFICULTADES:
            assert any(
                p.categoria == categoria and p.dificultad == dificultad for p in preguntas.GENERALES
            ), (categoria, dificultad)


def test_con_varias_categorias_se_mezclan_aunque_una_tenga_muchas_mas():
    sala, _ = sala_con("Ana", "Bea")
    sala.configurar(8, False, ["deportes", "picantes"], ["facil"])
    vistas = [sala._pregunta_general().categoria for _ in range(200)]
    assert 70 <= vistas.count("picantes") <= 130


def test_la_infantil_no_sale_si_no_se_elige_y_sola_solo_da_infantiles():
    sala, _ = sala_con("Ana", "Bea")
    assert "infantil" not in sala.categorias
    assert all(sala._pregunta_general().categoria != "infantil" for _ in range(200))
    sala.configurar(8, False, ["infantil"], ["facil", "media", "dificil"])
    assert all(sala._pregunta_general().categoria == "infantil" for _ in range(60))
