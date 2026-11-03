"""Dónde viven las partidas: en memoria (en local y en un servidor de un solo proceso)
o en Redis por la API REST de Upstash (en Vercel, donde cada petición puede caer en
una función distinta y la memoria no se comparte).

Cada partida es un texto JSON bajo una clave. Para que dos jugadas a la vez no se
pisen, se guarda solo si nadie la ha cambiado desde que se leyó (`guardar_si`).
"""

import os
import threading
import time
from typing import Protocol

import httpx

# Una partida que nadie toca en este tiempo se borra sola.
SEGUNDOS_VIDA = 6 * 3600


class Almacen(Protocol):
    def leer(self, codigo: str) -> str | None: ...

    def crear(self, codigo: str, texto: str) -> bool:
        """Guarda una partida nueva. False si el código ya estaba cogido."""

    def guardar_si(self, codigo: str, antes: str, despues: str) -> bool:
        """Guarda `despues` solo si sigue estando `antes`. False si otro se adelantó."""

    def contar(self, clave: str, segundos: int) -> int:
        """Suma uno a `clave` y dice cuántas lleva en la ventana de `segundos`."""


class SinAlmacen(Exception):
    """El almacén no responde."""


class Memoria:
    def __init__(self) -> None:
        self._datos: dict[str, tuple[str, float]] = {}
        self._contadores: dict[str, tuple[int, float]] = {}
        self._cerrojo = threading.Lock()

    def _vivo(self, codigo: str) -> str | None:
        texto, caduca = self._datos.get(codigo, (None, 0.0))
        if texto is not None and caduca < time.time():
            del self._datos[codigo]
            return None
        return texto

    def leer(self, codigo: str) -> str | None:
        with self._cerrojo:
            return self._vivo(codigo)

    def crear(self, codigo: str, texto: str) -> bool:
        with self._cerrojo:
            for c in list(self._datos):
                self._vivo(c)
            if self._vivo(codigo) is not None:
                return False
            self._datos[codigo] = (texto, time.time() + SEGUNDOS_VIDA)
            return True

    def guardar_si(self, codigo: str, antes: str, despues: str) -> bool:
        with self._cerrojo:
            if self._vivo(codigo) != antes:
                return False
            self._datos[codigo] = (despues, time.time() + SEGUNDOS_VIDA)
            return True

    def contar(self, clave: str, segundos: int) -> int:
        with self._cerrojo:
            ahora = time.time()
            n, caduca = self._contadores.get(clave, (0, 0.0))
            if caduca < ahora:
                n, caduca = 0, ahora + segundos
            self._contadores[clave] = (n + 1, caduca)
            if len(self._contadores) > 10000:
                self._contadores = {k: v for k, v in self._contadores.items() if v[1] >= ahora}
            return n + 1


# Compara y guarda en un solo paso dentro de Redis.
GUARDAR_SI = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
  return 1
end
return 0
"""

# Suma uno y, si es el primero, pone la caducidad: una sola orden.
CONTAR = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return n
"""


class Upstash:
    def __init__(self, url: str, token: str, transporte: httpx.BaseTransport | None = None):
        self._cliente = httpx.Client(
            base_url=url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=8,
            transport=transporte,
        )

    def _orden(self, *partes: str | int):
        try:
            r = self._cliente.post("/", json=[str(p) for p in partes])
            datos = r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise SinAlmacen(str(e)) from e
        if "error" in datos:
            raise SinAlmacen(datos["error"])
        return datos["result"]

    def leer(self, codigo: str) -> str | None:
        return self._orden("GET", f"sala:{codigo}")

    def crear(self, codigo: str, texto: str) -> bool:
        return self._orden("SET", f"sala:{codigo}", texto, "NX", "EX", SEGUNDOS_VIDA) == "OK"

    def guardar_si(self, codigo: str, antes: str, despues: str) -> bool:
        clave = f"sala:{codigo}"
        return self._orden("EVAL", GUARDAR_SI, 1, clave, antes, despues, SEGUNDOS_VIDA) == 1

    def contar(self, clave: str, segundos: int) -> int:
        return int(self._orden("EVAL", CONTAR, 1, f"limite:{clave}", segundos))


def desde_entorno() -> Almacen | None:
    """Upstash si está configurado; memoria si no. None en Vercel sin configurar:
    ahí la memoria no se comparte entre peticiones y el juego fallaría a ratos."""
    # Los nombres que pone Vercel al conectar Upstash, y los de Upstash a secas.
    url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if url and token:
        return Upstash(url, token)
    if os.environ.get("VERCEL"):
        return None
    return Memoria()
