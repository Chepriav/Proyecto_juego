"""Las reglas de ¡Paren la nave!: lógica pura, sin red ni almacenamiento.

Cada ronda se lee una pregunta cuya respuesta es un número. Quien abre dice una
cifra y se sienta de capitán. Por turnos, cada uno de los que siguen a bordo sube
la cifra (y pasa a ser el capitán), se queda o se baja. Tras cada subida, todos los
demás a bordo vuelven a tener turno; cuando ninguno sube, se revela la respuesta.

Si la cifra no pasa de la respuesta, la nave llega: puntúan el capitán y quien siga
a bordo. Si se pasa, se estrella: puntúan los que se bajaron a tiempo.

Las rondas pares son del alien: le toca a uno del grupo, la pregunta es sobre él (un
dato que solo él sabe, como cuántas fotos tiene en el móvil) y la contesta en secreto
antes de que empiece la ronda. Esa ronda no juega. Si los demás la aciertan (la nave
llega y el capitán se queda cerca), el alien pierde puntos; si no, los gana.
"""

import random
import secrets
import unicodedata
from dataclasses import asdict, dataclass, field, fields, replace

from .preguntas import (
    ALIEN_POR_CLAVE,
    CATEGORIAS,
    CATEGORIAS_POR_DEFECTO,
    DIFICULTADES,
    GENERALES,
    PREGUNTAS_ALIEN,
    Pregunta,
)

RONDAS_POSIBLES = (4, 6, 8, 10, 12)
RONDAS_POR_DEFECTO = 8
MAX_JUGADORES = 12
MAX_NOMBRE = 20
MAX_POR_MOVIL = 6
MAX_CIFRA = 10**12

SEGUNDOS_TURNO = 45
# El alien tiene que mirar el móvil (las fotos, la batería…) antes de contestar.
SEGUNDOS_ALIEN = 60
# Quien cierra la app no deja la nave parada: si no se le ve en este tiempo, su turno
# se resuelve solo (se queda, o abre el siguiente). Tiene que quedar holgado sobre
# REFRESCO_VISTO más lo que tarda la app en volver a preguntar.
SEGUNDOS_AUSENTE = 20
# Y si no vuelve, la ronda siguiente empieza sin él.
SEGUNDOS_FUERA = 60

PUNTOS_CAPITAN = 2
PUNTOS_CERCA = 2
PUNTOS_TRIPULANTE = 1
PUNTOS_BAJADO = 2
PUNTOS_ALIEN = 3
MARGEN_AÑOS = 5
MARGEN_RELATIVO = 0.10

COLORES = [
    "#ff6b6b",
    "#ffd93d",
    "#6bcb77",
    "#4d96ff",
    "#c77dff",
    "#ff9f45",
    "#2ec4b6",
    "#f15bb5",
    "#00bbf9",
    "#e9c46a",
    "#a0c4ff",
    "#b5e48c",
]


class ErrorDeJuego(Exception):
    """Algo que el jugador no puede hacer. El mensaje lo lee él."""


def _campos(cls, d: dict) -> dict:
    """Solo los campos que existen: una partida guardada con una versión anterior
    se sigue pudiendo leer tras un despliegue."""
    nombres = {f.name for f in fields(cls)}
    return {k: v for k, v in d.items() if k in nombres}


def es_cerca(cifra: int, respuesta: int, año: bool) -> bool:
    if año:
        return abs(cifra - respuesta) <= MARGEN_AÑOS
    return abs(cifra - respuesta) <= MARGEN_RELATIVO * abs(respuesta)


def puntuar(
    respuesta: int, año: bool, capitan: str, cifra: int, a_bordo: list[str], bajados: list[str]
) -> tuple[dict[str, int], bool, bool]:
    """Puntos de cada uno en la ronda, si la nave llega y si el capitán quedó cerca."""
    puntos = {j: 0 for j in [*a_bordo, *bajados]}
    if cifra > respuesta:
        for j in bajados:
            puntos[j] = PUNTOS_BAJADO
        return puntos, False, False
    cerca = es_cerca(cifra, respuesta, año)
    for j in a_bordo:
        puntos[j] = PUNTOS_TRIPULANTE
    puntos[capitan] = PUNTOS_CAPITAN + (PUNTOS_CERCA if cerca else 0)
    return puntos, True, cerca


@dataclass
class Jugador:
    id: str
    nombre: str
    token: str
    color: str
    visto: float
    puntos: int = 0
    se_fue: bool = False
    # Si juega en el móvil de otro (no tiene móvil), el id de ese otro.
    movil: str | None = None


@dataclass
class Ronda:
    numero: int
    pregunta: Pregunta
    alien: str | None
    orden: list[str]
    abre: str
    turno_hasta: float
    cifra: int | None = None
    capitan: str | None = None
    a_bordo: list[str] = field(default_factory=list)
    bajados: dict[str, int] = field(default_factory=dict)
    pendientes: list[str] = field(default_factory=list)
    eventos: list[dict] = field(default_factory=list)
    revelada: bool = False
    puntos: dict[str, int] = field(default_factory=dict)
    llega: bool = False
    cerca: bool = False
    # La pregunta como la ve el alien («¿Cuántas fotos tienes…?»), y si aún la escribe
    texto_alien: str | None = None
    escribiendo: bool = False

    @property
    def turno(self) -> str | None:
        if self.revelada:
            return None
        if self.escribiendo:
            return self.alien
        if self.cifra is None:
            return self.abre
        return self.pendientes[0] if self.pendientes else None

    def siguientes(self, capitan: str) -> list[str]:
        """Los de a bordo, en orden desde el que va detrás del capitán."""
        i = self.orden.index(capitan)
        vuelta = self.orden[i + 1 :] + self.orden[:i]
        return [j for j in vuelta if j in self.a_bordo]


@dataclass
class Sala:
    codigo: str
    creada: float
    rng: random.Random = field(default_factory=random.Random)
    jugadores: list[Jugador] = field(default_factory=list)
    anfitrion: str | None = None
    # Nombres (en minúsculas) de los echados: no pueden volver a entrar con ellos.
    vetados: list[str] = field(default_factory=list)
    fase: str = "espera"  # espera, jugando, fin
    rondas_total: int = RONDAS_POR_DEFECTO
    del_grupo: bool = True
    categorias: list[str] = field(default_factory=lambda: list(CATEGORIAS_POR_DEFECTO))
    dificultades: list[str] = field(default_factory=lambda: list(DIFICULTADES))
    ronda: Ronda | None = None
    usadas: set[int] = field(default_factory=set)
    usadas_alien: set[str] = field(default_factory=set)
    veces_alien: dict[str, int] = field(default_factory=dict)

    # --- Guardar y recuperar ------------------------------------------------------

    def a_dict(self) -> dict:
        return {
            "codigo": self.codigo,
            "creada": self.creada,
            "jugadores": [asdict(j) for j in self.jugadores],
            "anfitrion": self.anfitrion,
            "vetados": self.vetados,
            "fase": self.fase,
            "rondas_total": self.rondas_total,
            "del_grupo": self.del_grupo,
            "categorias": self.categorias,
            "dificultades": self.dificultades,
            "ronda": asdict(self.ronda) if self.ronda else None,
            "usadas": sorted(self.usadas),
            "usadas_alien": sorted(self.usadas_alien),
            "veces_alien": self.veces_alien,
        }

    @classmethod
    def desde_dict(cls, d: dict) -> "Sala":
        ronda = None
        if d["ronda"]:
            ronda = Ronda(
                **{
                    **_campos(Ronda, d["ronda"]),
                    "pregunta": Pregunta(**d["ronda"]["pregunta"]),
                }
            )
        return cls(
            codigo=d["codigo"],
            creada=d["creada"],
            jugadores=[Jugador(**_campos(Jugador, j)) for j in d["jugadores"]],
            anfitrion=d["anfitrion"],
            vetados=d.get("vetados", []),
            fase=d["fase"],
            rondas_total=d["rondas_total"],
            del_grupo=d["del_grupo"],
            categorias=d.get("categorias", list(CATEGORIAS_POR_DEFECTO)),
            dificultades=d.get("dificultades", list(DIFICULTADES)),
            ronda=ronda,
            usadas=set(d["usadas"]),
            usadas_alien=set(d.get("usadas_alien", [])),
            veces_alien=d.get("veces_alien", {}),
        )

    # --- Jugadores ---------------------------------------------------------------

    def unirse(self, nombre: str, ahora: float, movil: str | None = None) -> Jugador:
        # Fuera los caracteres de control e invisibles (los que dan la vuelta al texto,
        # los de anchura cero…): con ellos se puede imitar el nombre de otro.
        nombre = unicodedata.normalize("NFKC", nombre)
        nombre = "".join(c for c in nombre if not unicodedata.category(c).startswith("C"))
        nombre = " ".join(nombre.split())
        if not nombre:
            raise ErrorDeJuego("Pon un nombre para que te reconozcan.")
        if len(nombre) > MAX_NOMBRE:
            raise ErrorDeJuego(f"El nombre no puede pasar de {MAX_NOMBRE} letras.")
        if nombre.casefold() in self.vetados:
            raise ErrorDeJuego("Te han echado de esta partida.")
        mismo = next((j for j in self.jugadores if j.nombre.casefold() == nombre.casefold()), None)
        if mismo and mismo.se_fue:
            # Quien salió y vuelve con su nombre recupera su sitio y sus puntos.
            mismo.se_fue = False
            mismo.token = secrets.token_urlsafe(16)
            mismo.visto = ahora
            mismo.movil = movil
            return mismo
        if mismo:
            raise ErrorDeJuego("Ya hay alguien con ese nombre. Prueba con otro.")
        if len(self.jugadores) >= MAX_JUGADORES:
            raise ErrorDeJuego(f"La nave está llena: caben {MAX_JUGADORES}.")
        usados = {j.color for j in self.jugadores}
        color = next(c for c in COLORES if c not in usados)
        jugador = Jugador(
            id=secrets.token_hex(4),
            nombre=nombre,
            token=secrets.token_urlsafe(16),
            color=color,
            visto=ahora,
            movil=movil,
        )
        self.jugadores.append(jugador)
        if self.anfitrion is None:
            self.anfitrion = jugador.id
        return jugador

    def acompanar(self, dueno: Jugador, nombre: str, ahora: float) -> Jugador:
        """Alguien sin móvil juega en el de `dueno`, pasándoselo cuando le toca."""
        if dueno.movil:
            raise ErrorDeJuego("Añádelo desde el móvil de quien lo trae.")
        if len(self.acompanantes(dueno)) >= MAX_POR_MOVIL - 1:
            raise ErrorDeJuego(f"En un mismo móvil caben {MAX_POR_MOVIL} como mucho.")
        return self.unirse(nombre, ahora, movil=dueno.id)

    def acompanantes(self, dueno: Jugador) -> list[Jugador]:
        return [j for j in self.jugadores if j.movil == dueno.id and not j.se_fue]

    def mismo_movil(self, jugador: Jugador) -> list[Jugador]:
        """Todos los que juegan en el móvil de `jugador`, él incluido."""
        dueno = self.por_id(jugador.movil) if jugador.movil else jugador
        return [dueno, *self.acompanantes(dueno)]

    def por_token(self, token: str | None) -> Jugador:
        for j in self.jugadores:
            if token and secrets.compare_digest(j.token, token):
                if not j.se_fue:
                    return j
                if j.nombre.casefold() in self.vetados:
                    raise ErrorDeJuego("Te han echado de esta partida.")
        raise ErrorDeJuego("No estás en esta partida. Entra con tu nombre.")

    def por_id(self, jugador_id: str) -> Jugador:
        return next(j for j in self.jugadores if j.id == jugador_id)

    def conectados(self, ahora: float) -> list[Jugador]:
        return [j for j in self.jugadores if not j.se_fue and ahora - j.visto <= SEGUNDOS_FUERA]

    def salir(self, jugador: Jugador, ahora: float) -> None:
        """Antes de empezar se le quita de la lista; con la partida en marcha se queda
        en la clasificación, y si le tocaba, su turno se resuelve ya."""
        if self.fase == "espera":
            self.jugadores.remove(jugador)
            if self.anfitrion == jugador.id:
                self.anfitrion = self.jugadores[0].id if self.jugadores else None
            return
        jugador.se_fue = True
        r = self.ronda
        if self.fase == "jugando" and r and not r.revelada and jugador.id != r.capitan:
            # Fuera de la nave: ni puntúa esta ronda ni hay que esperarle. El capitán
            # se queda, porque su cifra es la que se juega.
            if jugador.id in r.a_bordo:
                r.a_bordo.remove(jugador.id)
            if jugador.id in r.pendientes:
                r.pendientes.remove(jugador.id)
                if not r.pendientes:
                    self._revelar(r)
        self.comprobar_tiempo(ahora)

    # --- Quien manda -------------------------------------------------------------

    def exigir_anfitrion(self, jugador: Jugador) -> None:
        """Configurar, despegar y echar son cosa de quien creó la partida: con el enlace
        circulando, un desconocido no puede estropearla."""
        if jugador.id != self.anfitrion:
            raise ErrorDeJuego("Eso solo lo puede hacer quien creó la partida.")

    def revisar_anfitrion(self, ahora: float) -> None:
        """Si quien manda se ha ido o lleva rato sin aparecer, manda el siguiente que
        siga conectado (por orden de llegada). Si no, la partida se quedaría sin poder
        despegar."""
        actual = next((j for j in self.jugadores if j.id == self.anfitrion), None)
        if actual and not actual.se_fue and ahora - actual.visto <= SEGUNDOS_FUERA:
            return
        # Manda alguien con móvil propio: los que juegan en el de otro no pueden.
        conectados = [j for j in self.conectados(ahora) if not j.movil]
        if conectados:
            self.anfitrion = conectados[0].id

    def echar(self, quien: Jugador, echado_id: str, ahora: float) -> None:
        self.exigir_anfitrion(quien)
        echado = next((j for j in self.jugadores if j.id == echado_id and not j.se_fue), None)
        if echado is None:
            raise ErrorDeJuego("Esa persona ya no está en la partida.")
        if echado is quien:
            raise ErrorDeJuego("Para irte tú, usa Salir.")
        self.vetados.append(echado.nombre.casefold())
        self.salir(echado, ahora)

    # --- La partida --------------------------------------------------------------

    def configurar(
        self,
        rondas: int,
        del_grupo: bool,
        categorias: list[str] | None = None,
        dificultades: list[str] | None = None,
    ) -> None:
        if self.fase == "jugando":
            raise ErrorDeJuego("La partida ya ha empezado.")
        if rondas not in RONDAS_POSIBLES:
            raise ErrorDeJuego("Ese número de rondas no vale.")
        if categorias is not None:
            if not categorias:
                raise ErrorDeJuego("Elige al menos una categoría.")
            if any(c not in CATEGORIAS for c in categorias):
                raise ErrorDeJuego("Esa categoría no existe.")
            # En el orden de siempre, sin repetir
            self.categorias = [c for c in CATEGORIAS if c in categorias]
        if dificultades is not None:
            if not dificultades:
                raise ErrorDeJuego("Elige al menos una dificultad.")
            if any(d not in DIFICULTADES for d in dificultades):
                raise ErrorDeJuego("Esa dificultad no existe.")
            self.dificultades = [d for d in DIFICULTADES if d in dificultades]
        self.rondas_total = rondas
        self.del_grupo = del_grupo

    def empezar(self, ahora: float) -> None:
        # Si dos le dan a la vez, el segundo no tiene que ver un error.
        if self.fase == "jugando":
            return
        if len(self.conectados(ahora)) < 2:
            raise ErrorDeJuego("Hace falta al menos otro astronauta. Pásale el enlace.")
        for j in self.jugadores:
            j.puntos = 0
        self.fase = "jugando"
        self.ronda = None
        self._nueva_ronda(ahora)

    def siguiente(self, ahora: float, desde: int) -> None:
        """Pasa de la ronda `desde`. Si otro ya ha pasado, no hace nada."""
        r = self.ronda
        if self.fase != "jugando" or r is None or r.numero != desde:
            return
        if not r.revelada:
            raise ErrorDeJuego("Todavía no ha terminado la ronda.")
        if r.numero >= self.rondas_total:
            self.fase = "fin"
            return
        if len(self.conectados(ahora)) < 2:
            raise ErrorDeJuego("Te has quedado solo en la nave. Espera a que vuelva alguien.")
        self._nueva_ronda(ahora)

    def _nueva_ronda(self, ahora: float) -> None:
        numero = self.ronda.numero + 1 if self.ronda else 1
        activos = self.conectados(ahora)
        # Con dos no hay alien: jugaría uno solo.
        if self.del_grupo and numero % 2 == 0 and len(activos) >= 3:
            self._ronda_alien(numero, activos, ahora)
            return
        orden = [j.id for j in activos]
        self.ronda = Ronda(
            numero=numero,
            pregunta=self._pregunta_general(),
            alien=None,
            orden=orden,
            abre=orden[(numero - 1) % len(orden)],
            turno_hasta=ahora + SEGUNDOS_TURNO,
            a_bordo=list(orden),
        )

    def _ronda_alien(self, numero: int, activos: list[Jugador], ahora: float) -> None:
        # Le toca a quien menos veces lo ha sido, también a quien juega en el móvil de
        # otro: si todos juegan en uno, si no, siempre le tocaría al dueño.
        menos = min(self.veces_alien.get(j.id, 0) for j in activos)
        alien = self.rng.choice([j for j in activos if self.veces_alien.get(j.id, 0) == menos])
        self.veces_alien[alien.id] = menos + 1
        # Las picantes del alien, solo si se han pedido picantes; a quien no tiene móvil,
        # solo las que se contestan sin él.
        posibles = [
            p.clave
            for p in PREGUNTAS_ALIEN
            if (not p.picante or "picantes" in self.categorias) and (p.sin_movil or not alien.movil)
        ]
        libres = sorted(c for c in posibles if c not in self.usadas_alien)
        if not libres:
            self.usadas_alien.difference_update(posibles)
            libres = sorted(posibles)
        clave = self.rng.choice(libres)
        self.usadas_alien.add(clave)
        p = ALIEN_POR_CLAVE[clave]
        orden = [j.id for j in activos if j.id != alien.id]
        self.ronda = Ronda(
            numero=numero,
            # La respuesta la pone el alien al escribirla.
            pregunta=Pregunta(p.para_otros.format(n=alien.nombre), 0, p.año),
            alien=alien.id,
            orden=orden,
            abre=orden[(numero - 1) % len(orden)],
            turno_hasta=ahora + SEGUNDOS_ALIEN,
            a_bordo=list(orden),
            texto_alien=p.para_alien,
            escribiendo=True,
        )

    def _sin_alien(self, r: Ronda, ahora: float) -> None:
        """El alien no ha escrito su respuesta: la ronda sigue con una pregunta normal,
        y él juega como uno más si sigue ahí."""
        alien = self.por_id(r.alien)
        r.eventos.append({"jugador": alien.id, "accion": "no_escribe"})
        if not alien.se_fue:
            r.orden.append(alien.id)
            r.a_bordo.append(alien.id)
        r.pregunta = self._pregunta_general()
        r.alien = None
        r.texto_alien = None
        r.escribiendo = False
        r.turno_hasta = ahora + SEGUNDOS_TURNO

    def _pregunta_general(self) -> Pregunta:
        """Primero se sortea la categoría y luego la pregunta, para que con varias
        elegidas se mezclen aunque una tenga muchas más. No se repite ninguna hasta que
        se acaban las de esa categoría; si una combinación no tiene ninguna (picantes
        fáciles hay pocas), se abre la dificultad antes que la categoría."""
        por_categoria: dict[str, list[int]] = {}
        for i, p in enumerate(GENERALES):
            if p.categoria in self.categorias and p.dificultad in self.dificultades:
                por_categoria.setdefault(p.categoria, []).append(i)
        if not por_categoria:
            for i, p in enumerate(GENERALES):
                if p.categoria in self.categorias:
                    por_categoria.setdefault(p.categoria, []).append(i)
        categoria = self.rng.choice(sorted(por_categoria))
        candidatas = por_categoria[categoria]
        libres = [i for i in candidatas if i not in self.usadas]
        if not libres:
            self.usadas.difference_update(candidatas)
            libres = candidatas
        i = self.rng.choice(libres)
        self.usadas.add(i)
        return GENERALES[i]

    # --- Los turnos --------------------------------------------------------------

    def jugar(self, jugador: Jugador, accion: str, cifra: int | None, ahora: float) -> None:
        r = self.ronda
        if self.fase != "jugando" or r is None or r.revelada:
            raise ErrorDeJuego("Ahora no se puede jugar.")
        if r.turno != jugador.id:
            raise ErrorDeJuego("Espera, no es tu turno.")
        if cifra is not None and not 0 <= cifra <= MAX_CIFRA:
            raise ErrorDeJuego("Ese número no vale.")

        if r.escribiendo:
            if accion != "secreto" or cifra is None:
                raise ErrorDeJuego("Escribe tu respuesta secreta.")
            r.pregunta = replace(r.pregunta, respuesta=cifra)
            r.escribiendo = False
            r.eventos.append({"jugador": jugador.id, "accion": "secreto"})
            r.turno_hasta = ahora + SEGUNDOS_TURNO
            return
        if r.cifra is None:
            if accion != "abrir" or cifra is None:
                raise ErrorDeJuego("Te toca abrir: di una cifra.")
            self._nuevo_capitan(r, jugador.id, cifra)
        elif accion == "subir":
            if cifra is None or cifra <= r.cifra:
                raise ErrorDeJuego(f"Para subir tienes que decir más de {r.cifra}.")
            self._nuevo_capitan(r, jugador.id, cifra)
        elif accion == "quedarse":
            r.pendientes.pop(0)
            r.eventos.append({"jugador": jugador.id, "accion": "quedarse"})
        elif accion == "bajarse":
            r.pendientes.pop(0)
            r.a_bordo.remove(jugador.id)
            r.bajados[jugador.id] = r.cifra
            r.eventos.append({"jugador": jugador.id, "accion": "bajarse", "cifra": r.cifra})
        else:
            raise ErrorDeJuego("Eso no se puede hacer ahora.")

        r.turno_hasta = ahora + SEGUNDOS_TURNO
        if r.turno is None:
            self._revelar(r)

    def _nuevo_capitan(self, r: Ronda, jugador_id: str, cifra: int) -> None:
        accion = "abrir" if r.cifra is None else "subir"
        r.cifra = cifra
        r.capitan = jugador_id
        r.pendientes = r.siguientes(jugador_id)
        r.eventos.append({"jugador": jugador_id, "accion": accion, "cifra": cifra})

    def _revelar(self, r: Ronda) -> None:
        r.puntos, r.llega, r.cerca = puntuar(
            r.pregunta.respuesta,
            r.pregunta.año,
            r.capitan,
            r.cifra,
            r.a_bordo,
            list(r.bajados),
        )
        if r.alien:
            alien = self.por_id(r.alien)
            acertada = r.llega and r.cerca
            if not alien.se_fue:
                # Sin bajar de cero.
                r.puntos[alien.id] = max(-alien.puntos, -PUNTOS_ALIEN if acertada else PUNTOS_ALIEN)
        for jugador_id, puntos in r.puntos.items():
            self.por_id(jugador_id).puntos += puntos
        r.revelada = True

    def comprobar_tiempo(self, ahora: float) -> None:
        """Resuelve los turnos que se han agotado o de quien ya no está."""
        r = self.ronda
        if self.fase != "jugando" or r is None:
            return
        # Acotado: si se han ido todos, que no dé vueltas sin fin.
        for _ in range(len(r.orden) * 2):
            turno = r.turno
            if turno is None:
                return
            quien = self.por_id(turno)
            ausente = quien.se_fue or ahora - quien.visto > SEGUNDOS_AUSENTE
            if ahora < r.turno_hasta and not ausente:
                return
            if r.escribiendo:
                self._sin_alien(r, ahora)
            elif r.cifra is None:
                i = r.orden.index(r.abre)
                r.abre = r.orden[(i + 1) % len(r.orden)]
                r.eventos.append({"jugador": turno, "accion": "pasa"})
                r.turno_hasta = ahora + SEGUNDOS_TURNO
            else:
                self.jugar(self.por_id(turno), "quedarse", None, ahora)
                r.eventos[-1]["auto"] = True

    # --- Lo que ve cada uno ------------------------------------------------------

    def vista(self, jugador: Jugador, ahora: float) -> dict:
        r = self.ronda
        ronda = None
        if r is not None and self.fase == "jugando":
            es_alien = r.alien == jugador.id
            sabe = r.revelada or (es_alien and not r.escribiendo)
            ronda = {
                "numero": r.numero,
                "pregunta": r.texto_alien if es_alien else r.pregunta.texto,
                "año": r.pregunta.año,
                "categoria": CATEGORIAS.get(r.pregunta.categoria),
                "dificultad": DIFICULTADES.get(r.pregunta.dificultad),
                "alien": r.alien,
                "escribiendo": r.escribiendo,
                "orden": r.orden,
                "abre": r.abre,
                "cifra": r.cifra,
                "capitan": r.capitan,
                "a_bordo": r.a_bordo,
                "bajados": r.bajados,
                "turno": r.turno,
                "segundos": max(0, round(r.turno_hasta - ahora)) if r.turno else None,
                "eventos": r.eventos[-6:],
                "revelada": r.revelada,
                "respuesta": r.pregunta.respuesta if sabe else None,
                "llega": r.llega if r.revelada else None,
                "cerca": r.cerca if r.revelada else None,
                "puntos": r.puntos if r.revelada else {},
                "ultima": r.numero >= self.rondas_total,
            }
        return {
            "codigo": self.codigo,
            "fase": self.fase,
            "yo": jugador.id,
            "anfitrion": self.anfitrion,
            "rondas_total": self.rondas_total,
            "del_grupo": self.del_grupo,
            "categorias": self.categorias,
            "dificultades": self.dificultades,
            "jugadores": [
                {
                    "id": j.id,
                    "nombre": j.nombre,
                    "color": j.color,
                    "puntos": j.puntos,
                    "conectado": not j.se_fue and ahora - j.visto <= SEGUNDOS_FUERA,
                    "movil": j.movil,
                }
                for j in self.jugadores
            ],
            "ronda": ronda,
        }
