"""La API y la página.

Cada petición lee la partida del almacén, la cambia y la guarda solo si ha cambiado
algo, y solo si nadie se ha adelantado; si se ha adelantado, vuelve a empezar. Así
funciona igual con un proceso que con una función de Vercel por petición.
"""

import hashlib
import json
import os
import random
import re
import secrets
import time
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .almacen import SinAlmacen, desde_entorno
from .juego import ErrorDeJuego, Jugador, Sala
from .preguntas import CATEGORIAS, DIFICULTADES, GENERALES

PUBLICO = Path(__file__).resolve().parent.parent / "public"
LETRAS_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ"
# 24⁶ son 191 millones de códigos: con el freno de abajo, adivinar el de una partida
# a base de probar no sale a cuenta. Con 4 letras eran 331.776.
LARGO_CODIGO = 6
# Las de 4 letras se siguen aceptando: puede haber partidas abiertas de antes.
FORMATO_CODIGO = re.compile(r"[A-Z]{4,6}")
# Si muchos cambian la partida a la vez (todos entrando con el enlace al mismo tiempo),
# se pisan y hay que reintentar; con una espera al azar creciente dejan de chocar.
INTENTOS = 15
# Que alguien sigue ahí se apunta como mucho cada tanto, no en cada consulta: cada
# escritura cuesta (en Upstash, una orden de las del plan gratis).
REFRESCO_VISTO = 8

# Cuántas veces por hora puede una misma conexión crear partidas o entrar en ellas.
# Sobra para jugar; corta a quien crea partidas sin parar (llenaría la base de datos)
# o prueba códigos para colarse.
LIMITES = {"crear": 20, "entrar": 60}

app = FastAPI(title="¡Paren la nave!", docs_url=None, redoc_url=None, openapi_url=None)
almacen = desde_entorno()

# Las mismas que pone vercel.json, para cuando se sirve desde un servidor propio.
CABECERAS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'self'"
    ),
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


# La versión publicada: en Vercel, el commit. La página la compara con la que vio al
# abrirse y, si cambia, ofrece actualizar (instalada en el móvil no se recarga sola).
VERSION = (
    os.environ.get("VERCEL_GIT_COMMIT_SHA") or os.environ.get("VERCEL_DEPLOYMENT_ID") or "local"
)[:12]


@app.middleware("http")
async def cabeceras_de_seguridad(request: Request, siguiente):
    respuesta = await siguiente(request)
    respuesta.headers.update(CABECERAS)
    if request.url.path.startswith("/api/"):
        respuesta.headers["Cache-Control"] = "no-store"
        respuesta.headers["X-Version"] = VERSION
    return respuesta


class Nombre(BaseModel):
    nombre: str = Field(max_length=100)


class Ajustes(BaseModel):
    rondas: int
    del_grupo: bool
    categorias: list[str] | None = Field(None, max_length=20)
    dificultades: list[str] | None = Field(None, max_length=5)


class Echar(BaseModel):
    jugador: str = Field(max_length=20)


class Siguiente(BaseModel):
    desde: int


class Jugada(BaseModel):
    accion: str = Field(max_length=20)
    cifra: int | None = None


def _almacen():
    if almacen is None:
        raise HTTPException(
            503,
            "Falta conectar la base de datos de las partidas. "
            "En Vercel: Storage → Upstash Redis → Connect, y volver a desplegar.",
        )
    return almacen


def _ip(request: Request) -> str:
    """La IP de quien llama. En Vercel la pone su proxy en x-real-ip; detrás de Nginx,
    la última de x-forwarded-for es la que vio Nginx (las anteriores las puede
    inventar el cliente)."""
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    reenviada = request.headers.get("x-forwarded-for")
    if reenviada:
        return reenviada.split(",")[-1].strip()
    return request.client.host if request.client else "?"


def _frenar(request: Request, accion: str) -> None:
    # La IP no se guarda tal cual: solo un resumen, y caduca en una hora.
    resumen = hashlib.sha256(_ip(request).encode()).hexdigest()[:16]
    try:
        veces = _almacen().contar(f"{accion}:{resumen}", 3600)
    except SinAlmacen:
        raise HTTPException(503, "No llego a la base de datos. Prueba otra vez.") from None
    if veces > LIMITES[accion]:
        raise HTTPException(429, "Demasiados intentos seguidos. Espera un rato y prueba otra vez.")


def _a_texto(sala: Sala) -> str:
    return json.dumps(sala.a_dict(), ensure_ascii=False, separators=(",", ":"))


def _con_sala(codigo: str, cambio: Callable[[Sala, float], dict]) -> dict:
    """Aplica `cambio` a la partida, la guarda si ha cambiado y devuelve lo que diga."""
    codigo = codigo.upper()
    if not FORMATO_CODIGO.fullmatch(codigo):
        raise HTTPException(404, "Esa partida no existe o ya ha terminado.")
    a = _almacen()
    try:
        for intento in range(INTENTOS):
            antes = a.leer(codigo)
            if antes is None:
                raise HTTPException(404, "Esa partida no existe o ya ha terminado.")
            sala = Sala.desde_dict(json.loads(antes))
            ahora = time.time()
            try:
                respuesta = cambio(sala, ahora)
            except ErrorDeJuego as e:
                raise HTTPException(400, str(e)) from None
            despues = _a_texto(sala)
            if despues == antes or a.guardar_si(codigo, antes, despues):
                return respuesta
            time.sleep(random.uniform(0.01, 0.04) * (intento + 1))
    except SinAlmacen:
        raise HTTPException(503, "No llego a la base de datos. Prueba otra vez.") from None
    raise HTTPException(503, "Hay mucho movimiento en la nave. Prueba otra vez.")


def _con_jugador(codigo: str, token: str | None, accion: Callable[[Sala, Jugador, float], None]):
    def cambio(sala: Sala, ahora: float) -> dict:
        jugador = sala.por_token(token)
        # Quien juega en el móvil de otro sigue ahí mientras ese móvil siga abierto.
        for j in sala.mismo_movil(jugador):
            if ahora - j.visto > REFRESCO_VISTO:
                j.visto = ahora
        sala.revisar_anfitrion(ahora)
        sala.comprobar_tiempo(ahora)
        accion(sala, jugador, ahora)
        return sala.vista(jugador, ahora)

    return _con_sala(codigo, cambio)


@app.get("/api/opciones")
def opciones() -> dict:
    """Las categorías y dificultades que se pueden elegir, con cuántas preguntas hay."""
    return {
        "categorias": [
            {
                "clave": c,
                "nombre": nombre,
                "cuantas": sum(p.categoria == c for p in GENERALES),
            }
            for c, nombre in CATEGORIAS.items()
        ],
        "dificultades": [{"clave": d, "nombre": nombre} for d, nombre in DIFICULTADES.items()],
    }


@app.post("/api/salas")
def crear(cuerpo: Nombre, request: Request) -> dict:
    a = _almacen()
    _frenar(request, "crear")
    ahora = time.time()
    try:
        for _ in range(INTENTOS):
            codigo = "".join(secrets.choice(LETRAS_CODIGO) for _ in range(LARGO_CODIGO))
            sala = Sala(codigo=codigo, creada=ahora)
            try:
                jugador = sala.unirse(cuerpo.nombre, ahora)
            except ErrorDeJuego as e:
                raise HTTPException(400, str(e)) from None
            if a.crear(codigo, _a_texto(sala)):
                return {"codigo": codigo, "token": jugador.token}
    except SinAlmacen:
        raise HTTPException(503, "No llego a la base de datos. Prueba otra vez.") from None
    raise HTTPException(503, "No he podido crear la partida. Prueba otra vez.")


@app.post("/api/salas/{codigo}/entrar")
def entrar(codigo: str, cuerpo: Nombre, request: Request) -> dict:
    _frenar(request, "entrar")

    def cambio(sala: Sala, ahora: float) -> dict:
        jugador = sala.unirse(cuerpo.nombre, ahora)
        return {"codigo": sala.codigo, "token": jugador.token}

    return _con_sala(codigo, cambio)


@app.get("/api/salas/{codigo}")
def ver(codigo: str, x_token: str | None = Header(None)) -> dict:
    return _con_jugador(codigo, x_token, lambda *_: None)


@app.post("/api/salas/{codigo}/ajustes")
def ajustes(codigo: str, cuerpo: Ajustes, x_token: str | None = Header(None)) -> dict:
    return _con_jugador(
        codigo,
        x_token,
        lambda s, j, _: (
            s.exigir_anfitrion(j),
            s.configurar(cuerpo.rondas, cuerpo.del_grupo, cuerpo.categorias, cuerpo.dificultades),
        ),
    )


@app.post("/api/salas/{codigo}/empezar")
def empezar(codigo: str, x_token: str | None = Header(None)) -> dict:
    return _con_jugador(
        codigo, x_token, lambda s, j, ahora: (s.exigir_anfitrion(j), s.empezar(ahora))
    )


@app.post("/api/salas/{codigo}/jugada")
def jugada(codigo: str, cuerpo: Jugada, x_token: str | None = Header(None)) -> dict:
    return _con_jugador(
        codigo, x_token, lambda s, j, ahora: s.jugar(j, cuerpo.accion, cuerpo.cifra, ahora)
    )


@app.post("/api/salas/{codigo}/siguiente")
def siguiente(codigo: str, cuerpo: Siguiente, x_token: str | None = Header(None)) -> dict:
    return _con_jugador(codigo, x_token, lambda s, _, ahora: s.siguiente(ahora, cuerpo.desde))


@app.post("/api/salas/{codigo}/acompanante")
def acompanante(
    codigo: str, cuerpo: Nombre, request: Request, x_token: str | None = Header(None)
) -> dict:
    _frenar(request, "entrar")

    def cambio(sala: Sala, ahora: float) -> dict:
        nuevo = sala.acompanar(sala.por_token(x_token), cuerpo.nombre, ahora)
        return {"id": nuevo.id, "token": nuevo.token, "nombre": nuevo.nombre}

    return _con_sala(codigo, cambio)


@app.post("/api/salas/{codigo}/echar")
def echar(codigo: str, cuerpo: Echar, x_token: str | None = Header(None)) -> dict:
    return _con_jugador(codigo, x_token, lambda s, j, ahora: s.echar(j, cuerpo.jugador, ahora))


@app.post("/api/salas/{codigo}/salir")
def salir(codigo: str, x_token: str | None = Header(None)) -> dict:
    def cambio(sala: Sala, ahora: float) -> dict:
        sala.salir(sala.por_token(x_token), ahora)
        return {"ok": True}

    return _con_sala(codigo, cambio)


@app.get("/api/{resto:path}", include_in_schema=False)
def no_existe(resto: str):
    raise HTTPException(404, "No existe.")


# En Vercel la página y lo de /estaticos los sirve su CDN desde public/, y la función
# no lleva esa carpeta: sin `check_dir=False` la app no arranca. Esto es para local y
# para un servidor propio.
app.mount(
    "/estaticos",
    StaticFiles(directory=PUBLICO / "estaticos", check_dir=False),
    name="estaticos",
)


@app.get("/{resto:path}", include_in_schema=False)
def pagina(resto: str) -> FileResponse:
    # La misma página para / y para /s/CODIGO: el enlace que se pasa al grupo.
    return FileResponse(PUBLICO / "index.html")
