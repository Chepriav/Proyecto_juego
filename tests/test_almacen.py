import json

import fakeredis
import httpx
import pytest

from app import almacen
from app.almacen import Memoria, Upstash


def upstash_de_pega() -> Upstash:
    """Un Upstash que habla su API REST contra un Redis en memoria."""
    redis = fakeredis.FakeRedis(decode_responses=True)

    def atender(peticion: httpx.Request) -> httpx.Response:
        assert peticion.headers["Authorization"] == "Bearer secreto"
        orden = json.loads(peticion.content)
        try:
            resultado = redis.execute_command(*orden)
            # Upstash contesta como Redis («OK»); redis-py lo traduce a True.
            if resultado is True:
                resultado = "OK"
            return httpx.Response(200, json={"result": resultado})
        except Exception as e:
            return httpx.Response(400, json={"error": str(e)})

    return Upstash("https://pega.upstash.io", "secreto", httpx.MockTransport(atender))


@pytest.fixture(params=["memoria", "upstash"])
def alm(request):
    return Memoria() if request.param == "memoria" else upstash_de_pega()


def test_crear_no_pisa_una_partida_que_ya_existe(alm):
    assert alm.crear("ABCD", "uno")
    assert not alm.crear("ABCD", "dos")
    assert alm.leer("ABCD") == "uno"


def test_guardar_solo_si_nadie_se_ha_adelantado(alm):
    alm.crear("ABCD", "uno")
    assert alm.guardar_si("ABCD", "uno", "dos")
    assert not alm.guardar_si("ABCD", "uno", "tres")
    assert alm.leer("ABCD") == "dos"


def test_una_partida_que_no_existe_no_se_lee(alm):
    assert alm.leer("ZZZZ") is None


def test_en_vercel_sin_base_de_datos_no_se_finge_con_memoria(monkeypatch):
    for v in ("KV_REST_API_URL", "KV_REST_API_TOKEN", "UPSTASH_REDIS_REST_URL"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("VERCEL", "1")
    assert almacen.desde_entorno() is None


def test_toma_las_variables_que_pone_vercel_al_conectar_upstash(monkeypatch):
    monkeypatch.setenv("KV_REST_API_URL", "https://x.upstash.io")
    monkeypatch.setenv("KV_REST_API_TOKEN", "t")
    assert isinstance(almacen.desde_entorno(), Upstash)
