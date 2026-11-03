"""Las preguntas: el banco general (en banco.py, por categoría y dificultad) y las del
alien, sobre sí mismo.

Todas las respuestas son números enteros. `año` marca las que se responden con un
año: ahí «acercarse» se mide en años, no en porcentaje (un 10 % de 1969 son dos
siglos).
"""

from dataclasses import dataclass

from .banco import POR_CATEGORIA

CATEGORIAS = {
    "historia": "Historia",
    "geografia": "Geografía",
    "ciencia": "Ciencia y espacio",
    "deportes": "Deportes",
    "ocio": "Cine, series y juegos",
    "cotidiano": "Día a día",
    "picantes": "Picantes 🌶️",
    "infantil": "Infantil",
}
# Las picantes y la infantil hay que pedirlas: no salen si no se eligen.
CATEGORIAS_POR_DEFECTO = [c for c in CATEGORIAS if c not in ("picantes", "infantil")]

DIFICULTADES = {"facil": "Fácil", "media": "Media", "dificil": "Difícil"}


@dataclass(frozen=True)
class Pregunta:
    texto: str
    respuesta: int
    año: bool = False
    categoria: str = ""
    dificultad: str = ""


GENERALES: list[Pregunta] = [
    Pregunta(texto, respuesta, bool(resto and resto[0]), categoria, dificultad)
    for categoria, filas in POR_CATEGORIA.items()
    for dificultad, texto, respuesta, *resto in filas
]


@dataclass(frozen=True)
class PreguntaAlien:
    clave: str
    # Lo que ve el alien, y lo que ven los demás en su ronda
    para_alien: str
    para_otros: str
    año: bool = False
    picante: bool = False
    # Se puede contestar sin móvil propio: vale para quien juega en el de otro.
    sin_movil: bool = False


# Datos que nadie más sabe, ni la pareja, y que el alien puede mirar en el móvil en
# ese momento: nada de edad, altura o hermanos, que se los saben todos.
PREGUNTAS_ALIEN: list[PreguntaAlien] = [
    PreguntaAlien(
        "fotos", "¿Cuántas fotos tienes en el móvil?", "¿Cuántas fotos tiene {n} en el móvil?"
    ),
    PreguntaAlien(
        "capturas",
        "¿Cuántas capturas de pantalla tienes en el móvil?",
        "¿Cuántas capturas de pantalla tiene {n} en el móvil?",
    ),
    PreguntaAlien(
        "foto_antigua",
        "¿De qué año es la foto más antigua de tu móvil?",
        "¿De qué año es la foto más antigua del móvil de {n}?",
        año=True,
    ),
    PreguntaAlien(
        "sin_leer",
        "¿Cuántos chats de WhatsApp tienes sin leer ahora mismo?",
        "¿Cuántos chats de WhatsApp tiene {n} sin leer ahora mismo?",
    ),
    PreguntaAlien(
        "grupos",
        "¿En cuántos grupos de WhatsApp estás?",
        "¿En cuántos grupos de WhatsApp está {n}?",
    ),
    PreguntaAlien(
        "correos",
        "¿Cuántos correos sin leer tienes?",
        "¿Cuántos correos sin leer tiene {n}?",
    ),
    PreguntaAlien(
        "apps",
        "¿Cuántas apps tienes instaladas en el móvil?",
        "¿Cuántas apps tiene {n} instaladas en el móvil?",
    ),
    PreguntaAlien(
        "contactos",
        "¿Cuántos contactos tienes en el móvil?",
        "¿Cuántos contactos tiene {n} en el móvil?",
    ),
    PreguntaAlien(
        "bateria",
        "¿Qué porcentaje de batería te queda ahora mismo?",
        "¿Qué porcentaje de batería le queda a {n} ahora mismo?",
    ),
    PreguntaAlien(
        "pestañas",
        "¿Cuántas pestañas tienes abiertas en el navegador del móvil?",
        "¿Cuántas pestañas tiene {n} abiertas en el navegador del móvil?",
    ),
    PreguntaAlien(
        "alarmas",
        "¿Cuántas alarmas tienes guardadas en el móvil?",
        "¿Cuántas alarmas tiene {n} guardadas en el móvil?",
    ),
    PreguntaAlien(
        "pantalla",
        "¿Cuántos minutos de pantalla llevas hoy en el móvil?",
        "¿Cuántos minutos de pantalla lleva {n} hoy en el móvil?",
    ),
    PreguntaAlien("pasos", "¿Cuántos pasos llevas hoy?", "¿Cuántos pasos lleva {n} hoy?"),
    PreguntaAlien(
        "notas",
        "¿Cuántas notas tienes en la app de notas?",
        "¿Cuántas notas tiene {n} en la app de notas?",
    ),
    PreguntaAlien(
        "efectivo",
        "¿Cuántos euros llevas encima en efectivo?",
        "¿Cuántos euros lleva {n} encima en efectivo?",
        sin_movil=True,
    ),
    PreguntaAlien(
        "seguidos",
        "¿A cuántas cuentas sigues en Instagram?",
        "¿A cuántas cuentas sigue {n} en Instagram?",
    ),
    PreguntaAlien(
        "eventos",
        "¿Cuántos eventos tienes en el calendario este mes?",
        "¿Cuántos eventos tiene {n} en el calendario este mes?",
    ),
    PreguntaAlien(
        "llamadas",
        "¿Cuántas llamadas has hecho o recibido esta semana?",
        "¿Cuántas llamadas ha hecho o recibido {n} esta semana?",
    ),
]


# Para quien juega en el móvil de otro (y valen para todos): cosas que lleva encima o
# que solo sabe él, comprobables sin móvil.
PREGUNTAS_ALIEN += [
    PreguntaAlien(clave, para_alien, para_otros, sin_movil=True)
    for clave, para_alien, para_otros in [
        (
            "monedas",
            "¿Cuántas monedas llevas encima?",
            "¿Cuántas monedas lleva {n} encima?",
        ),
        (
            "llaves",
            "¿Cuántas llaves llevas en el llavero?",
            "¿Cuántas llaves lleva {n} en el llavero?",
        ),
        (
            "tarjetas",
            "¿Cuántas tarjetas llevas en la cartera?",
            "¿Cuántas tarjetas lleva {n} en la cartera?",
        ),
        (
            "bolsillos",
            "¿Cuántas cosas llevas ahora mismo en los bolsillos?",
            "¿Cuántas cosas lleva {n} ahora mismo en los bolsillos?",
        ),
        (
            "agua",
            "¿Cuántos vasos de agua has bebido hoy?",
            "¿Cuántos vasos de agua ha bebido {n} hoy?",
        ),
        (
            "baño",
            "¿Cuántas veces has ido hoy al baño?",
            "¿Cuántas veces ha ido {n} hoy al baño?",
        ),
        (
            "pulso",
            "¿Cuántas pulsaciones tienes en 15 segundos? Cuéntalas ahora en la muñeca",
            "¿Cuántas pulsaciones tiene {n} en 15 segundos, ahora mismo?",
        ),
        (
            "parpadeos",
            "¿Cuántas veces parpadeas en 30 segundos? Cuéntalo ahora",
            "¿Cuántas veces parpadea {n} en 30 segundos, ahora mismo?",
        ),
        (
            "botones",
            "¿Cuántos botones llevas en la ropa ahora mismo?",
            "¿Cuántos botones lleva {n} en la ropa ahora mismo?",
        ),
        (
            "libros",
            "¿Cuántos libros has leído este año?",
            "¿Cuántos libros ha leído {n} este año?",
        ),
        (
            "sueños",
            "¿Cuántas horas dormiste anoche, redondeando?",
            "¿Cuántas horas durmió {n} anoche, redondeando?",
        ),
        (
            "peluches",
            "¿Cuántos peluches tienes en casa?",
            "¿Cuántos peluches tiene {n} en casa?",
        ),
    ]
]


# Las picantes que no piden mirar el móvil valen también para quien no lo tiene.
SIN_MOVIL_PICANTES = {"bloqueados", "ex_instagram"}


def _picante(clave: str, para_alien: str, para_otros: str) -> PreguntaAlien:
    return PreguntaAlien(
        clave, para_alien, para_otros, picante=True, sin_movil=clave not in SIN_MOVIL_PICANTES
    )


# Solo salen si se eligen las picantes. Estas no se pueden mirar en el móvil: van a la
# honradez del alien.
PREGUNTAS_ALIEN += [
    _picante(
        "liados",
        "¿Con cuántas personas te has liado?",
        "¿Con cuántas personas se ha liado {n}?",
    ),
    _picante(
        "parejas",
        "¿Cuántas parejas formales has tenido?",
        "¿Cuántas parejas formales ha tenido {n}?",
    ),
    _picante(
        "besos_noche",
        "¿A cuántas personas has besado en una misma noche, como mucho?",
        "¿A cuántas personas ha besado {n} en una misma noche, como mucho?",
    ),
    _picante(
        "apps_ligar",
        "¿Cuántas apps de ligar has tenido instaladas?",
        "¿Cuántas apps de ligar ha tenido instaladas {n}?",
    ),
    _picante(
        "citas_apps",
        "¿A cuántas citas has ido por apps de ligar?",
        "¿A cuántas citas ha ido {n} por apps de ligar?",
    ),
    _picante(
        "enamorado",
        "¿Cuántas veces te has enamorado?",
        "¿Cuántas veces se ha enamorado {n}?",
    ),
    _picante(
        "ex_instagram",
        "¿A cuántos ex sigues teniendo en Instagram?",
        "¿A cuántos ex sigue teniendo {n} en Instagram?",
    ),
    _picante(
        "bloqueados",
        "¿Cuántos contactos tienes bloqueados en WhatsApp?",
        "¿Cuántos contactos tiene {n} bloqueados en WhatsApp?",
    ),
    _picante(
        "ghosting",
        "¿A cuántas personas les has hecho ghosting?",
        "¿A cuántas personas les ha hecho ghosting {n}?",
    ),
    _picante(
        "acostado",
        "¿Con cuántas personas te has acostado?",
        "¿Con cuántas personas se ha acostado {n}?",
    ),
    _picante(
        "una_noche",
        "¿Cuántos rollos de una noche has tenido?",
        "¿Cuántos rollos de una noche ha tenido {n}?",
    ),
    _picante(
        "publico",
        "¿Cuántas veces lo has hecho en un sitio público?",
        "¿Cuántas veces lo ha hecho {n} en un sitio público?",
    ),
    _picante(
        "coche",
        "¿Cuántas veces lo has hecho en un coche?",
        "¿Cuántas veces lo ha hecho {n} en un coche?",
    ),
    _picante(
        "record_noche",
        "¿Cuál es tu récord de veces en una misma noche?",
        "¿Cuál es el récord de veces de {n} en una misma noche?",
    ),
    _picante(
        "fingido",
        "¿Cuántas veces has fingido un orgasmo?",
        "¿Cuántas veces ha fingido {n} un orgasmo?",
    ),
    _picante(
        "juguetes",
        "¿Cuántos juguetes sexuales tienes?",
        "¿Cuántos juguetes sexuales tiene {n}?",
    ),
    _picante(
        "fotos_subidas",
        "¿Cuántas fotos subidas de tono has mandado en tu vida?",
        "¿Cuántas fotos subidas de tono ha mandado {n} en su vida?",
    ),
    _picante(
        "pillado",
        "¿Cuántas veces te han pillado en plena faena?",
        "¿Cuántas veces han pillado a {n} en plena faena?",
    ),
    _picante(
        "trabajo",
        "¿Con cuántas personas de tu trabajo o de clase te has liado?",
        "¿Con cuántas personas de su trabajo o de clase se ha liado {n}?",
    ),
    _picante(
        "resacas",
        "¿Cuántas resacas has tenido este año?",
        "¿Cuántas resacas ha tenido {n} este año?",
    ),
    _picante(
        "sin_saber",
        "¿Cuántas veces te has despertado sin saber muy bien dónde estabas?",
        "¿Cuántas veces se ha despertado {n} sin saber muy bien dónde estaba?",
    ),
    _picante(
        "copas_bailar",
        "¿Cuántas copas te hacen falta para salir a bailar?",
        "¿Cuántas copas le hacen falta a {n} para salir a bailar?",
    ),
]

ALIEN_POR_CLAVE = {p.clave: p for p in PREGUNTAS_ALIEN}
