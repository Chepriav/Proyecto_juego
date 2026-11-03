# ¡Paren la nave!

Juego de preguntas con respuesta numérica para un grupo de amigos, cada uno en su
móvil, basado en el juego de mesa «¡Paren la nave! Que me bajo». Reglas en el README.

## Comandos

```bash
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
pytest
ruff check . --fix && ruff format .
```

## Arquitectura

FastAPI sirve la API y una página sin compilar (HTML, CSS y JS a mano en `public/`).
En producción va en Vercel: `public/` por su CDN y la API como función de Python
(`api/index.py`, con las rutas en `vercel.json`); las partidas, en Upstash Redis.
Pasos del despliegue en el README.

```
app/juego.py      las reglas: salas, rondas, turnos y puntos. Lógica pura, sin red
app/banco.py      las preguntas generales, por categoría y dificultad
app/preguntas.py  categorías, dificultades, el banco ya montado y las del alien
app/almacen.py    dónde se guardan las partidas: memoria o Upstash (API REST)
app/main.py       la API (token en la cabecera X-Token) y la página en local
api/index.py      la entrada de Vercel
public/           la página: index.html y estaticos/app.js, que pinta según el estado
```

## Decisiones

- **Vercel y Upstash, no el VPS.** Lo pidió el dueño: que funcionara sin servidor
  propio. En Vercel cada petición puede caer en una función distinta, así que la
  partida entera se guarda como un JSON bajo `sala:CODIGO` (caduca a las 6 h) y cada
  petición la lee, la cambia y la guarda **solo si nadie se ha adelantado**
  (`guardar_si`, un script de Lua que compara y escribe); si se adelantó, vuelve a
  empezar. Sin variables de Upstash usa memoria (local, tests, un servidor de un
  proceso); en Vercel sin ellas se niega con un mensaje claro en vez de fallar a ratos.
- **Cada orden de Upstash cuenta para el plan gratis.** Mirar la partida es una
  lectura; solo se escribe si cambia algo. Que alguien sigue ahí (`visto`) se apunta
  cada 8 s como mucho (`REFRESCO_VISTO`), no en cada consulta; por eso
  `SEGUNDOS_AUSENTE` tiene que quedar holgado por encima.
- **Consulta cada 2 segundos en vez de WebSockets** (las funciones de Vercel no los
  mantienen). Pasa por cualquier proxy y se recupera solo cuando el móvil se bloquea
  o pierde cobertura. Lo que hace uno se ve al momento, porque la respuesta trae la
  partida, y la cuenta atrás corre en el móvil. La página solo vuelve a pintar si algo
  cambió, y conserva lo que uno está escribiendo.
- **Sin cuentas.** Al entrar se da un token que se guarda en el móvil por sala
  (`nave:CODIGO` en `localStorage`). El enlace que se pasa es solo el de la sala.
- **Categorías y dificultad las elige el grupo** antes de cada partida (una o varias
  de cada; lo pidió el dueño). Se sortea primero la categoría y luego la pregunta: si
  no, con Deportes (74) y Picantes (29) casi todo saldría de Deportes. Las picantes
  nunca salen por defecto y son de sexo de verdad (el dueño las quería así: «cuánto
  aguanta un hombre», «tamaño preferido»), pero con la fuente en la pregunta
  (Waldinger 2005, Veale y Prause 2015, Frappier 2013, Frederick 2018, encuesta Durex
  2005, Uloko 2022). Sin dato fiable no entran: la frecuencia en España no la hay; con ellas, el alien también tiene preguntas picantes (que
  no se pueden mirar en el móvil: van a su honradez). Además de las normales, cada
  categoría lleva muchas raras y curiosas (la guerra más corta, el tiburón más viejo…):
  lo pidió el dueño, para que llamen la atención. Si una combinación se queda sin
  preguntas, se abre la dificultad antes que la categoría.
- **Infantil** (lo pidió el dueño): para jugar con niños, cosas que saben o pueden
  deducir (animales, cuentos, dibujos, el cole). Como las picantes, no sale por
  defecto: mezclada con las de adultos se quedaría corta.
- **Preguntas de un banco propio, no de internet.** No hay una fuente gratis de
  preguntas con respuesta numérica en español; las de IA cuestan y a veces se
  equivocan. Van en `banco.py` como (dificultad, texto, respuesta[, AÑO]): que la
  respuesta sea un entero, comprobada y que no caduque (nada de «cuántas Champions
  tiene…»). Las de años llevan AÑO, porque «cerca» se mide en años (5) y no en
  porcentaje (10 %). **Fácil es que suene, no que se regale ni que se calcule**
  (el dueño, noviembre de 2026): cosas que uno ha visto u oído y sabe más o menos (el
  año de Colón, el de Chernóbil, las provincias de España). Fuera las que sabe todo
  el mundo al número (los planetas, las patas de una araña, la edad para votar),
  porque el que abre acierta, y las de echar cuentas (las patas de 3 vacas y 2
  gallinas), que las hace fáciles para todos. Nada de operaciones («cuánto es 7 por 8»,
  «cuántos huevos son 4 docenas»). Las de «más o menos» de consumo y cosas de casa
  sí valen (los litros de una ducha), **si tienen un valor estándar**: nada de lo que
  depende de cada uno (los grados del horno para una pizza, la ropa que cabe en una
  lavadora, lo que tarda un huevo duro; el dueño las tumbó por eso). Las fáciles de Infantil, igual, para niños de 7 u 8 años:
  de sus dibujos, pelis, Pokémon y monumentos conocidos (cuántos años tiene Bluey,
  cuánto mide la Estatua de la Libertad); ni de saberse ya (los cuernos de un
  unicornio) ni de hacer cuentas, que el dueño dijo que no era el juego. Las medias, lo mismo pero menos conocido: nada de
  cuentas (los minutos de un día) ni de lo que lo dice la pregunta (el dado de 20). Un test exige más de 400, sin repetir, y de todas las
  combinaciones de categoría y dificultad.
- **Las rondas pares son del alien** (lo pidió el dueño), si hay al menos tres: con
  dos jugaría uno solo. A quien le toca (rota entre los que menos lo han sido) se le
  pone la pantalla verde (`html.alien`) y escribe su respuesta secreta en ese momento
  (`escribiendo`, acción `secreto`, 60 s); hasta entonces nadie juega. No se rellena
  nada al entrar. Si los demás la aciertan, **la nave llega y el capitán queda cerca**
  (`es_cerca`), pierde `PUNTOS_ALIEN` sin bajar de cero; si no, los gana: quedarse
  corto también es fallar, o abrir con 0 bastaría para cazarlo. Si no escribe a
  tiempo o se va, la ronda sigue con una pregunta general y él juega.
- **Las preguntas del alien son de datos que no sabe nadie más**, ni la pareja, y que
  se pueden mirar en el móvil en ese momento (fotos, batería, chats sin leer…):
  nada de edad, altura o hermanos (`PREGUNTAS_ALIEN`, hay un test que lo vigila).
- **Nadie bloquea la nave.** Un turno dura 45 s; quien no se ve en 20 s (cerró la
  app) pasa al momento, y quien no se ve en 60 s no entra en la ronda siguiente.
- **Salir** (botón en la cabecera, con dos toques para que uno sin querer no te
  saque): antes de empezar te quita de la lista; con la partida en marcha sigues en
  la clasificación, sales de la nave (no puntúas esa ronda salvo que seas el capitán,
  cuya cifra es la que se juega) y tu turno pasa al momento. Tu enlace deja de valer,
  pero si vuelves a entrar con el mismo nombre recuperas tu sitio y tus puntos.
- **Varios en el mismo móvil** (lo pidió el dueño, para que juegue quien no tiene):
  en la sala de espera se añade a alguien «a este móvil» (`acompanar`, `Jugador.movil`
  con el id del dueño; hasta `MAX_POR_MOVIL`). Cuando le toca, el móvil enseña «Le
  toca a Lucía · Pásale el móvil»; con «Soy Lucía» juega con su token y, al jugar o si
  se le acaba el turno, vuelve solo al dueño. El servidor da por presentes a todos los
  del mismo móvil cuando consulta cualquiera de ellos (`mismo_movil`), o se les
  saltaría el turno a los 20 s. **También les toca ser alien**, por turno como a
  todos: al principio no les tocaba y, jugando todos en un móvil, el alien era siempre
  el dueño (se quejó él). A ellos solo les salen preguntas que se contestan sin móvil
  (`sin_movil`: llaves, monedas, lo que llevan encima…). No heredan el mando. En un móvil compartido el secreto del alien no se
  enseña en pantalla. Si el dueño sale, salen con él. Los tokens van en
  `nave:CODIGO:acomp`.
- **Quien crea la partida manda** (lo pidió el dueño al abrirla a desconocidos): solo
  él configura, despega y echa (`exigir_anfitrion`; echar pide dos toques). Al echado
  se le dice y su nombre queda vetado en esa sala (`vetados`). Si quien manda se va o
  no aparece en `SEGUNDOS_FUERA`, manda el siguiente conectado (`revisar_anfitrion`,
  en cada petición). Pasar de ronda lo puede cualquiera, para no esperar a nadie.
- **Firma y proyectos**: «Diseño y desarrollo · Charly», discreta, al pie de la
  portada y del final; nunca durante la partida. En el final, un bloque «¿Tienes algo en
  mente?» abierto a cualquier encargo (apps, webs, juegos, IA, problemas
  informáticos) que abre el correo con el asunto puesto. El enlace de la
  firma dice «¿Tienes un proyecto en mente?», sin atarlo a apps. Sin ventanas que
  salten. El correo va en `CORREO_PROYECTOS` (`app.js`): es uno dedicado, no el
  personal; vacío, ni el bloque ni el enlace de la firma salen.
- **Se instala como una app** (lo pidió el dueño): `manifest.webmanifest` e iconos en
  `public/estaticos/iconos` (el de Apple, 180 px; los de Android, y uno «maskable» con
  la nave en la zona segura, porque Android lo recorta). Los iconos salen de un SVG
  del platillo pasado a PNG. Sin service worker: cachear la página haría justo lo
  contrario de lo que se quiere al actualizar.
- **Botón de actualizar**: cada respuesta de `/api` lleva `X-Version` (el commit en
  Vercel). La página apunta la primera que ve y, si cambia, saca arriba «Hay una
  versión nueva · Actualizar», que recarga sin perder la partida. Instalada en el
  móvil la app puede quedarse abierta días: sin partida, la versión se mira al volver
  a ella.
- **La clasificación es de cada partida.** No hay ranking global: sin cuentas, lo
  único que une partidas es el nombre, y la app es pública.
- **El aspecto es una sala de control de misión de los 70** (lo pidió el dueño: «que
  no parezca hecho por IA»). Tinta casi negra, naranja de seguridad (`--acento`)
  como único color fuerte, verde para aterrizar y rojo para estrellarse; rótulos en
  Big Shoulders, texto en IBM Plex Sans y cifras en IBM Plex Mono, servidas desde
  `public/estaticos/fuentes` (la CSP no deja cargar nada de fuera; licencia OFL al
  lado). Esquinas casi rectas, líneas finas, etiquetas pequeñas en mayúsculas. **Nada
  de emojis en la interfaz ni de degradados en el texto**: los iconos son SVG propios
  (`ICONOS`) y la nave, un platillo en SVG (`platillo()`). **El capitán se dibuja
  dentro del SVG**, recortado por la cúpula y con el cristal por delante; pegado
  encima con HTML quedaba flotando sobre la nave («estilo chapuza», con razón).
  El resto de los de a bordo va en el rayo tractor.
- **Los efectos se ven una sola vez** (`primeraVez`): la página se vuelve a pintar a
  menudo y no puede repetirlos. Las cifras ruedan hasta su valor (`efectos()`), el
  sello de la respuesta cae, la nave tiembla al estrellarse y el podio crece. La
  cuenta atrás (un anillo) se escribe en su sitio con `actualizarReloj` para no
  redibujar. Con «reducir movimiento» del sistema no se anima nada.
- **El alien ve un monitor de fósforo verde**: `html.alien` cambia las variables de
  color y añade líneas de barrido.
- **Pulsar a la vez no da errores:** empezar y pasar de ronda (con el número de la
  ronda de la que se pasa) son idempotentes.

## Seguridad

Revisada en noviembre de 2026 atacándola en local (Redis real, tres procesos). Lo que
la sostiene, y no hay que quitar:

- **El enlace solo lleva el código de la sala**; el token de cada uno va en su móvil
  y en la cabecera `X-Token`, nunca en la dirección ni en lo que ven los demás. Lo
  secreto (la respuesta, la del alien) solo sale en `vista()` cuando toca.
- **Códigos de 6 letras** (191 millones) y **freno por IP** (`LIMITES`: 20 partidas y
  60 entradas por hora): así no se adivina un código a base de probar ni se llena la
  base de datos. Se cuenta en el almacén (`contar`, una orden de Lua), porque en
  Vercel la memoria no se comparte; de la IP solo se guarda un resumen que caduca en
  una hora. La IP sale de `x-real-ip` (Vercel; en Nginx hay que ponerla) o de la
  última de `x-forwarded-for`, que es la única que no inventa el cliente.
- **Nombres** sin caracteres de control ni invisibles y normalizados (NFKC), para que
  nadie imite a otro. Todo lo que escribe un jugador se pinta con `esc()`.
- **Cabeceras**: CSP sin scripts de fuera, sin marcos, sin caché en `/api`; en
  `vercel.json` y, para servidor propio, en el middleware de `main.py`. Sin
  `/docs` ni `/openapi.json`.
- **Muchos a la vez**: si se pisan al guardar, se reintenta hasta 15 veces con una
  espera al azar creciente. Sin ella, 11 entrando a la vez se llevaban errores.

## Convenciones

Todo en español: código, comentarios y mensajes. Los errores de la API los lee un
jugador. Los tests van por comportamiento.
