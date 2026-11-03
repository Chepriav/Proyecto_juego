"use strict";

const raiz = document.getElementById("app");
const RONDAS = [4, 6, 8, 10, 12];
const PUNTOS_ALIEN = 3; // el mismo que en juego.py

// Quien hizo la app y dónde escribirle para proyectos. Sin correo, el bloque de
// proyectos no sale y la firma va sin enlace.
const AUTOR = "Charly";
const CORREO_PROYECTOS = "chepriapps@gmail.com";
// Cada consulta cuesta una orden de la base de datos: cada dos segundos va sobrado,
// y lo que hace uno se ve al momento porque la respuesta trae la partida.
const ESPERA_ENTRE_CONSULTAS = 2000;

const estado = {
  codigo: null,
  token: null,
  sala: null,
  recibida: 0,
  error: null,
  sinRed: false,
  ocupado: false,
  ultimoHtml: "",
  eraMiTurno: false,
  confirmarSalida: false,
  // Quienes juegan en este móvil sin tener uno ({id, token, nombre}), y si ahora mismo
  // tiene el móvil uno de ellos para jugar su turno.
  acompanantes: [],
  jugandoComo: null,
  // La versión del servidor la primera vez que contestó, y si ya hay otra publicada
  version: null,
  hayVersionNueva: false,
  confirmarEchar: null,
  opciones: { categorias: [], dificultades: [] },
};

// --- Utilidades ----------------------------------------------------------------

const almacen = {
  leer(clave) {
    try {
      return localStorage.getItem(clave);
    } catch {
      return null;
    }
  },
  poner(clave, valor) {
    try {
      if (valor == null) localStorage.removeItem(clave);
      else localStorage.setItem(clave, valor);
    } catch {
      // Sin almacenamiento se juega igual; solo no se recuerda al recargar.
    }
  },
};

function esc(texto) {
  return String(texto).replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
}

function fmt(n, año) {
  if (n == null) return "?";
  return año ? String(n) : n.toLocaleString("es-ES");
}

function leerNumero(texto) {
  const limpio = String(texto ?? "").replace(/\D/g, "");
  return limpio === "" ? null : Number(limpio);
}

let temporizadorTostada;
function tostada(mensaje) {
  const caja = document.getElementById("tostada");
  caja.textContent = mensaje;
  caja.hidden = false;
  clearTimeout(temporizadorTostada);
  temporizadorTostada = setTimeout(() => (caja.hidden = true), 2800);
}

async function api(ruta, { metodo = "GET", cuerpo } = {}) {
  let respuesta;
  try {
    respuesta = await fetch(`/api${ruta}`, {
      method: metodo,
      headers: {
        "Content-Type": "application/json",
        ...(tokenActivo() ? { "X-Token": tokenActivo() } : {}),
      },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
    });
  } catch {
    const error = new Error("Sin conexión. Mira si tienes cobertura.");
    error.sinRed = true;
    throw error;
  }
  vigilarVersion(respuesta.headers.get("X-Version"));
  let datos = null;
  try {
    datos = await respuesta.json();
  } catch {
    // Sin cuerpo: se queda en null.
  }
  if (!respuesta.ok) {
    const detalle = typeof datos?.detail === "string" ? datos.detail : null;
    // El código ayuda a saber qué ha pasado si alguien manda una captura.
    const error = new Error(detalle ?? `Algo ha fallado (${respuesta.status}). Prueba otra vez.`);
    error.estado = respuesta.status;
    throw error;
  }
  return datos;
}

// Si el servidor ya va por otra versión, se ofrece actualizar. Instalada en el móvil la
// app puede quedarse abierta días sin recargarse.
function vigilarVersion(version) {
  if (!version) return;
  if (estado.version === null) {
    estado.version = version;
    return;
  }
  if (version !== estado.version && !estado.hayVersionNueva) {
    estado.hayVersionNueva = true;
    pintarAvisoVersion();
  }
}

function pintarAvisoVersion() {
  if (document.getElementById("version-nueva")) return;
  const aviso = document.createElement("div");
  aviso.id = "version-nueva";
  aviso.setAttribute("role", "status");
  aviso.innerHTML = `<span><b>Hay una versión nueva</b>Tu partida sigue donde estaba.</span>
    <button type="button" class="boton principal">Actualizar</button>`;
  aviso.querySelector("button").addEventListener("click", () => location.reload());
  document.body.append(aviso);
}

// --- Entrar y salir --------------------------------------------------------------

function codigoDeLaDireccion() {
  const m = location.pathname.match(/^\/s\/([A-Za-z]{4,6})\/?$/);
  return m ? m[1].toUpperCase() : null;
}

// --- Varios en el mismo móvil -------------------------------------------------------

function tokenActivo() {
  return estado.jugandoComo?.token ?? estado.token;
}

function cargarAcompanantes() {
  try {
    estado.acompanantes = JSON.parse(almacen.leer(`nave:${estado.codigo}:acomp`) ?? "[]");
  } catch {
    estado.acompanantes = [];
  }
}

function guardarAcompanantes() {
  almacen.poner(
    `nave:${estado.codigo}:acomp`,
    estado.acompanantes.length ? JSON.stringify(estado.acompanantes) : null,
  );
}

function acompananteDe(id) {
  return estado.acompanantes.find((a) => a.id === id);
}

async function anadirAcompanante(nombreNuevo) {
  const nuevo = await api(`/salas/${estado.codigo}/acompanante`, {
    metodo: "POST",
    cuerpo: { nombre: nombreNuevo },
  });
  estado.acompanantes.push(nuevo);
  guardarAcompanantes();
  tostada(`${nuevo.nombre} jugará en este móvil.`);
  consultar();
}

// Quien no tiene móvil coge este para su turno; al acabar vuelve solo al dueño.
function cogerMovil(id) {
  estado.jugandoComo = acompananteDe(id) ?? null;
  consultar();
}

function devolverMovil(aviso = true) {
  const quien = estado.jugandoComo;
  estado.jugandoComo = null;
  if (quien && aviso) tostada(`Hecho, ${quien.nombre}. Devuelve el móvil.`);
  consultar();
}

function abordar(codigo, token) {
  estado.codigo = codigo;
  estado.token = token;
  estado.error = null;
  cargarAcompanantes();
  almacen.poner(`nave:${codigo}`, token);
  if (location.pathname !== `/s/${codigo}`) history.replaceState(null, "", `/s/${codigo}`);
  consultar();
}

function olvidarSesion() {
  almacen.poner(`nave:${estado.codigo}`, null);
  almacen.poner(`nave:${estado.codigo}:acomp`, null);
  estado.token = null;
  estado.sala = null;
  estado.acompanantes = [];
  estado.jugandoComo = null;
}

async function crear(nombre) {
  const { codigo, token } = await api("/salas", { metodo: "POST", cuerpo: { nombre } });
  abordar(codigo, token);
}

async function entrar(codigo, nombre) {
  const datos = await api(`/salas/${codigo}/entrar`, { metodo: "POST", cuerpo: { nombre } });
  abordar(datos.codigo, datos.token);
}

// --- Consultar la partida ----------------------------------------------------------

let siguienteConsulta;
async function consultar() {
  clearTimeout(siguienteConsulta);
  if (!estado.codigo || !estado.token) return;
  try {
    const sala = await api(`/salas/${estado.codigo}`);
    const r = sala.ronda;
    if (estado.jugandoComo && !(sala.fase === "jugando" && r && !r.revelada && r.turno === sala.yo)) {
      // Ya no le toca (se le acabó el tiempo): el móvil vuelve a su dueño.
      devolverMovil(false);
      return;
    }
    recibir(sala);
    if (!estado.jugandoComo) {
      // Los que jugaban aquí y ya no están en la partida (echados o fuera)
      const ids = new Set(sala.jugadores.map((j) => j.id));
      const antes = estado.acompanantes.length;
      estado.acompanantes = estado.acompanantes.filter((a) => ids.has(a.id));
      if (estado.acompanantes.length !== antes) guardarAcompanantes();
    }
    estado.sinRed = false;
  } catch (e) {
    if (estado.jugandoComo && e.estado === 400) {
      devolverMovil(false);
      return;
    }
    if (e.estado === 404) {
      estado.error = e.message;
      olvidarSesion();
    } else if (e.estado === 400) {
      olvidarSesion();
      tostada(e.message);
    } else {
      estado.sinRed = true;
    }
  }
  pintar();
  if (estado.token) siguienteConsulta = setTimeout(consultar, ESPERA_ENTRE_CONSULTAS);
}

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible") return;
  if (estado.token) consultar();
  // Sin partida no se consulta nada: se mira la versión al volver a la app.
  else api("/opciones").catch(() => {});
});

function recibir(sala) {
  estado.sala = sala;
  estado.recibida = Date.now();
}

// Los segundos que quedan, contados en el móvil desde que llegó la partida.
function segundosQuedan(r) {
  return Math.max(0, r.segundos - Math.floor((Date.now() - estado.recibida) / 1000));
}

async function accion(ruta, cuerpo) {
  if (estado.ocupado) return;
  estado.ocupado = true;
  try {
    const sala = await api(`/salas/${estado.codigo}${ruta}`, { metodo: "POST", cuerpo });
    if (estado.jugandoComo) {
      devolverMovil();
      return true;
    }
    recibir(sala);
    pintar();
    return true;
  } catch (e) {
    tostada(e.message);
    return false;
  } finally {
    estado.ocupado = false;
  }
}

// --- Piezas -------------------------------------------------------------------------

function jugador(id) {
  return estado.sala.jugadores.find((j) => j.id === id);
}

function nombre(id) {
  return esc(jugador(id)?.nombre ?? "Alguien");
}

// La insignia de cada uno: su inicial sobre su color.
function cara(id, tam = "") {
  const j = jugador(id);
  const inicial = esc((j?.nombre ?? "?").charAt(0).toUpperCase());
  const clase = tam === true ? "peque" : tam;
  return `<span class="cara ${clase}" style="--c:${j?.color ?? "#888"}" aria-hidden="true">${inicial}</span>`;
}

// Iconos propios: un trazo, sin relleno, del mismo grosor que las líneas de la app.
const ICONOS = {
  salir: '<path d="M9 4H5v16h4M15 8l4 4-4 4M19 12H9"/>',
  compartir: '<path d="M12 3v12M7 8l5-5 5 5M5 13v7h14v-7"/>',
  alien:
    '<path d="M12 3c-4.4 0-8 3.2-8 7.6C4 15.7 8.6 21 12 21s8-5.3 8-10.4C20 6.2 16.4 3 12 3z"/><path d="M7.5 10.5c1.6 0 3 1 3.2 2.6-1.7.3-3.4-.6-3.2-2.6zM16.5 10.5c-1.6 0-3 1-3.2 2.6 1.7.3 3.4-.6 3.2-2.6z"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
};

function icono(nombreIcono, clase = "") {
  return `<svg class="ico ${clase}" viewBox="0 0 24 24" aria-hidden="true">${ICONOS[nombreIcono]}</svg>`;
}

// El platillo, en SVG. `clase` elige el tamaño y la animación. Si lleva `piloto`
// ({color, inicial}), va sentado dentro de la cúpula: recortado por ella y con el
// cristal por delante, no pegado encima. `entra` lo hace subir desde dentro.
function platillo(clase = "", piloto = null, entra = false, vacia = false) {
  const cupula = "M92 76a58 56 0 0 1 116 0z";
  const interior = piloto
    ? `<g class="piloto ${entra ? "entra" : ""}" style="--c:${esc(piloto.color)}">
        <ellipse cx="150" cy="70" rx="30" ry="13" fill="${esc(piloto.color)}" fill-opacity=".55"/>
        <circle cx="150" cy="42" r="15" fill="#10141d" stroke="${esc(piloto.color)}" stroke-width="2.5"/>
        <text x="150" y="48.5" text-anchor="middle" font-family="Hombros, sans-serif" font-weight="900"
          font-size="19" fill="${esc(piloto.color)}">${esc(piloto.inicial)}</text>
        <path class="gorra" d="M136.5 30.5c3-7 24-7 27 0l3 2.5h-33z"/>
      </g>`
    : vacia
      ? `<text x="150" y="52" text-anchor="middle" font-family="Plex Mono, monospace" font-weight="600"
        font-size="26" fill="#cfeeff" fill-opacity=".35">?</text>`
      : "";
  const luces = [44, 78, 114, 150, 186, 222, 256]
    .map((x, i) => {
      const y = 96 - Math.round(Math.sin((Math.PI * (x - 20)) / 260) * 6);
      return `<circle class="luz l${i % 2}" cx="${x}" cy="${y}" r="4"/>`;
    })
    .join("");
  return `<svg class="platillo ${clase}" viewBox="0 0 300 140" aria-hidden="true">
    <defs>
      <linearGradient id="g-metal" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#e9ecf2"/><stop offset=".45" stop-color="#9aa3b5"/>
        <stop offset=".7" stop-color="#4b5366"/><stop offset="1" stop-color="#232836"/>
      </linearGradient>
      <linearGradient id="g-cristal" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#cfeeff" stop-opacity=".32"/>
        <stop offset=".6" stop-color="#5aa9e6" stop-opacity=".08"/>
        <stop offset="1" stop-color="#5aa9e6" stop-opacity=".2"/>
      </linearGradient>
      <clipPath id="g-cupula"><path d="${cupula}"/></clipPath>
      <radialGradient id="g-motor" cx=".5" cy=".5" r=".5">
        <stop offset="0" stop-color="#ffb37a"/><stop offset="1" stop-color="#ff5a1f" stop-opacity="0"/>
      </radialGradient>
    </defs>
    <ellipse class="motor" cx="150" cy="112" rx="58" ry="12" fill="url(#g-motor)"/>
    <path d="${cupula}" fill="#0b111c"/>
    <g clip-path="url(#g-cupula)">${interior}</g>
    <path class="cristal" d="${cupula}" fill="url(#g-cristal)" stroke="#cfeeff" stroke-opacity=".6" stroke-width="1.5"/>
    <path d="M110 46a42 32 0 0 1 26-16" fill="none" stroke="#fff" stroke-opacity=".5" stroke-width="3" stroke-linecap="round"/>
    <ellipse cx="150" cy="86" rx="140" ry="24" fill="url(#g-metal)"/>
    <ellipse cx="150" cy="79" rx="118" ry="10" fill="#fff" fill-opacity=".22"/>
    <path d="M10 86c18 14 74 24 140 24s122-10 140-24" fill="none" stroke="#1a1e29" stroke-width="2"/>
    ${luces}
  </svg>`;
}

function cabecera(s, izquierda) {
  const yo = jugador(s.yo);
  const prestado = estado.jugandoComo
    ? `<p class="prestado">Juega <b>${esc(estado.jugandoComo.nombre)}</b> con el móvil de ${nombre(yo.movil)}</p>`
    : "";
  const puntos =
    s.fase === "espera" ? "" : `<span class="marcador-propio">${String(yo.puntos).padStart(2, "0")}</span>`;
  return `<header class="barra">
    <div class="barra-izq"><span class="marca">Paren la nave</span><span class="mision">${izquierda}</span></div>
    <div class="barra-der">${estado.jugandoComo ? "" : `<span class="quien">${esc(yo.nombre)}</span>`}${puntos}
      ${
        estado.jugandoComo
          ? `<button class="boton-salir" type="button" data-accion="devolver">Devolver</button>`
          : `<button class="boton-salir ${estado.confirmarSalida ? "confirmar" : ""}" type="button" data-accion="salir"
        aria-label="Salir de la partida">${estado.confirmarSalida ? "¿Seguro?" : icono("salir")}</button>`
      }
    </div>
  </header>${prestado}`;
}

const REGLAS = `
  <details class="panel reglas">
    <summary>Cómo se juega</summary>
    <ol>
      <li>Sale una pregunta cuya respuesta es un número.</li>
      <li>Quien abre dice una cifra y se sienta al mando.</li>
      <li>Por turnos, cada uno <b>sube</b> la cifra y se queda el mando, <b>se queda</b> a bordo
        o grita <b>«¡Paren la nave!»</b> y se baja.</li>
      <li>Cuando nadie sube, se revela la respuesta.</li>
      <li>Si la cifra no se pasa, la nave aterriza: el capitán gana 2 puntos (4 si se queda
        muy cerca) y cada uno de los que siguen a bordo, 1.</li>
      <li>Si se pasa, se estrella: los que se bajaron a tiempo ganan 2.</li>
      <li>Una ronda de cada dos, uno es el <b>alien</b>: la pregunta es sobre él, la contesta en
        secreto y esa ronda no juega. Si la aciertan, pierde ${PUNTOS_ALIEN}; si no, gana ${PUNTOS_ALIEN}.</li>
    </ol>
  </details>`;

function clasificacion(s, conEchar = false) {
  const orden = [...s.jugadores].sort((a, b) => b.puntos - a.puntos);
  return `<ol class="tabla">${orden
    .map(
      (j, i) => `<li class="${j.conectado ? "" : "fuera"} ${j.id === s.yo ? "soy-yo" : ""}">
        <span class="puesto">${String(i + 1).padStart(2, "0")}</span>${cara(j.id, true)}
        <span class="nombre">${esc(j.nombre)}</span>${conEchar ? botonEchar(s, j) : ""}<span class="cifra-tabla">${j.puntos}</span></li>`,
    )
    .join("")}</ol>`;
}

// Solo quien creó la partida ve el botón, y nunca junto a su propio nombre.
function botonEchar(s, j) {
  if (s.anfitrion !== s.yo || j.id === s.yo || !j.conectado) return "";
  const seguro = estado.confirmarEchar === j.id;
  return `<button type="button" class="echar ${seguro ? "confirmar" : ""}" data-accion="echar" data-valor="${j.id}"
    aria-label="Echar a ${esc(j.nombre)}">${seguro ? "¿Echar?" : "Echar"}</button>`;
}

function marcaManda(s, j) {
  return j.id === s.anfitrion ? `<span class="manda">Manda</span>` : "";
}

// --- Firma y proyectos -----------------------------------------------------------------

function enlaceProyecto() {
  const asunto = "Tengo un proyecto en mente";
  const cuerpo = "Hola, Charly:\n\nHe jugado a ¡Paren la nave! y quería contarte algo.\n\nLo que necesito: \n";
  return `mailto:${CORREO_PROYECTOS}?subject=${encodeURIComponent(asunto)}&body=${encodeURIComponent(cuerpo)}`;
}

function firma() {
  return `<footer class="firma">
    <span class="monograma" aria-hidden="true">${esc(AUTOR.charAt(0))}</span>
    <span class="firma-texto"><span class="rotulo">Diseño y desarrollo</span><b>${esc(AUTOR)}</b></span>
    ${CORREO_PROYECTOS ? `<a class="firma-enlace" href="${enlaceProyecto()}">¿Tienes un proyecto en mente?</a>` : ""}
  </footer>`;
}

// Al acabar, cuando el grupo se lo ha pasado bien: sin ventanas que salten. Abierto a
// cualquier encargo, no solo a juegos: lo pidió el dueño.
function bloqueProyecto() {
  if (!CORREO_PROYECTOS) return "";
  return `<section class="proyecto">
    <p class="rotulo">Hecho por ${esc(AUTOR)}</p>
    <h2>¿Tienes algo en mente?</h2>
    <p>Apps, webs, juegos como este, proyectos con inteligencia artificial o ese problema
      informático que se te resiste. Cuéntame qué necesitas y lo vemos.</p>
    <a class="boton" href="${enlaceProyecto()}">Escríbeme</a>
  </section>`;
}

// Cuanto más larga la cifra, más pequeña, para que quepa en una línea.
function talla(valor, año) {
  const largo = fmt(valor, año).length;
  return largo > 11 ? "talla-s" : largo > 7 ? "talla-m" : "";
}

// Un número que rueda hasta su valor la primera vez que se ve (ver efectos()).
function contador(clave, valor, año) {
  return `<span class="contador" data-clave="${clave}" data-valor="${valor ?? ""}" data-año="${año ? 1 : 0}">${fmt(valor, año)}</span>`;
}

// Las animaciones de entrada, una sola vez por cosa: la página se vuelve a pintar a
// menudo y no puede repetirlas cada vez.
const yaVisto = new Set();
function primeraVez(clave) {
  if (yaVisto.has(clave)) return false;
  yaVisto.add(clave);
  return true;
}

// --- Pantallas ------------------------------------------------------------------------

function vistaInicio() {
  const nombreGuardado = esc(almacen.leer("nave:nombre") ?? "");
  const portada = `
    <header class="portada">
      ${platillo("flota")}
      <h1><span>¡Paren</span><span>la nave!</span></h1>
      <p class="lema">Acércate a la respuesta. Sin pasarte.</p>
    </header>`;
  const aviso = estado.error ? `<p class="panel aviso">${esc(estado.error)}</p>` : "";
  if (estado.codigo && !estado.error) {
    return `${portada}
      <form class="panel" data-form="entrar">
        <p class="rotulo">Te esperan en la misión <b>${esc(estado.codigo)}</b></p>
        <label for="nombre">Tu nombre</label>
        <input id="nombre" data-conservar maxlength="20" autocomplete="nickname" value="${nombreGuardado}" required />
        <button class="boton principal">Subir a bordo</button>
      </form>
      <button class="enlace" type="button" data-accion="nueva">Prefiero crear otra partida</button>
      ${REGLAS}
      ${firma()}`;
  }
  return `${portada}${aviso}
    <form class="panel" data-form="crear">
      <p class="rotulo">Nueva partida</p>
      <label for="nombre">Tu nombre</label>
      <input id="nombre" data-conservar maxlength="20" autocomplete="nickname" value="${nombreGuardado}" required />
      <button class="boton principal">Crear partida</button>
      <p class="nota">Te da un enlace para el grupo. Cada uno juega desde su móvil.</p>
    </form>
    <form class="panel" data-form="unirse">
      <p class="rotulo">Tengo un código</p>
      <div class="fila">
        <div><label for="codigo">Código</label>
          <input id="codigo" class="mono" data-conservar maxlength="6" autocapitalize="characters" autocomplete="off" placeholder="ABCDEF" required /></div>
        <div><label for="nombre2">Tu nombre</label>
          <input id="nombre2" data-conservar maxlength="20" autocomplete="nickname" value="${nombreGuardado}" required /></div>
      </div>
      <button class="boton">Entrar</button>
    </form>
    ${REGLAS}
    ${firma()}`;
}

function ajustesPartida(s) {
  const manda = s.anfitrion === s.yo;
  const bloqueo = manda ? "" : "disabled";
  const fichas = (lista, elegidas, accionFicha) =>
    lista
      .map(
        (o) => `<button type="button" class="ficha" data-accion="${accionFicha}" data-valor="${o.clave}" ${bloqueo}
          aria-pressed="${elegidas.includes(o.clave)}">${icono("check", "marca-ficha")}<span>${esc(
            o.nombre.replace(" 🌶️", ""),
          )}</span>${o.cuantas ? `<span class="cuantas">${o.cuantas}</span>` : ""}</button>`,
      )
      .join("");
  return `<section class="panel ${manda ? "" : "solo-lectura"}">
      <p class="rotulo">Plan de vuelo${manda ? "" : `<span class="cuenta">lo elige ${nombre(s.anfitrion)}</span>`}</p>
      <label>Categorías <span class="tenue">una o varias</span></label>
      <div class="fichas">${fichas(estado.opciones.categorias, s.categorias, "categoria")}</div>
      <label>Dificultad <span class="tenue">una o varias</span></label>
      <div class="fichas">${fichas(estado.opciones.dificultades, s.dificultades, "dificultad")}</div>
      <label>Rondas</label>
      <div class="segmentado">${RONDAS.map(
        (n) =>
          `<button type="button" data-accion="rondas" data-valor="${n}" aria-pressed="${n === s.rondas_total}" ${bloqueo}>${n}</button>`,
      ).join("")}</div>
      <label class="interruptor"><input type="checkbox" data-accion="del-grupo" ${s.del_grupo ? "checked" : ""} ${bloqueo} />
        <span>Rondas del alien<small>Una de cada dos, la pregunta es sobre uno de vosotros, que la
        contesta en secreto. Hacen falta tres.</small></span></label>
    </section>`;
}

function guardarAjustes(cambios) {
  const s = estado.sala;
  return accion("/ajustes", {
    rondas: s.rondas_total,
    del_grupo: s.del_grupo,
    categorias: s.categorias,
    dificultades: s.dificultades,
    ...cambios,
  });
}

// Marca o desmarca una ficha; siempre tiene que quedar al menos una.
function alternar(lista, clave, que) {
  const nueva = lista.includes(clave) ? lista.filter((c) => c !== clave) : [...lista, clave];
  if (!nueva.length) {
    tostada(`Elige al menos una ${que}.`);
    return null;
  }
  return nueva;
}

function vistaEspera(s) {
  const conectados = s.jugadores.filter((j) => j.conectado).length;
  const letras = [...s.codigo].map((l) => `<span>${esc(l)}</span>`).join("");
  return `
    ${cabecera(s, "En la plataforma")}
    <section class="billete">
      <p class="rotulo">Código de misión</p>
      <div class="codigo">${letras}</div>
      <button class="boton principal" data-accion="compartir">${icono("compartir")}Pasar el enlace</button>
    </section>
    <section class="panel">
      <p class="rotulo">Tripulación <span class="cuenta">${String(s.jugadores.length).padStart(2, "0")}/12</span></p>
      <ol class="tabla">${s.jugadores
        .map(
          (j, i) => `<li class="${j.conectado ? "" : "fuera"} ${j.id === s.yo ? "soy-yo" : ""}">
            <span class="puesto">${String(i + 1).padStart(2, "0")}</span>${cara(j.id, true)}
            <span class="nombre">${esc(j.nombre)}${
              j.movil ? `<small class="movil-de">en el móvil de ${nombre(j.movil)}</small>` : ""
            }</span>${marcaManda(s, j)}
            ${botonEchar(s, j) || `<span class="estado-linea">${j.conectado ? "a bordo" : "sin señal"}</span>`}</li>`,
        )
        .join("")}</ol>
      ${
        jugador(s.yo).movil
          ? ""
          : `<form class="sin-movil" data-form="acompanante">
        <label for="acomp">¿Alguien sin móvil? Juega en este</label>
        <div class="fila"><input id="acomp" data-conservar maxlength="20" autocomplete="off" placeholder="Su nombre" required />
          <button class="boton">Añadir</button></div>
        <p class="nota">Cuando le toque, le pasas el móvil.</p>
      </form>`
      }
    </section>
    ${ajustesPartida(s)}
    ${
      s.anfitrion === s.yo
        ? `<button class="boton principal grande" data-accion="empezar" ${conectados < 2 ? "disabled" : ""}>Despegar</button>
           ${conectados < 2 ? `<p class="nota centro">Hace falta al menos otro tripulante. Pásale el enlace.</p>` : ""}`
        : `<p class="espera-despegue">Esperando a que <b>${nombre(s.anfitrion)}</b> despegue</p>`
    }
    ${REGLAS}`;
}

function textoEvento(e, año) {
  const quien = `<b>${nombre(e.jugador)}</b>`;
  switch (e.accion) {
    case "abrir":
      return `${quien} abre con <span class="mono">${fmt(e.cifra, año)}</span>`;
    case "subir":
      return `${quien} sube a <span class="mono">${fmt(e.cifra, año)}</span>`;
    case "quedarse":
      return e.auto ? `${quien} no contesta y se queda` : `${quien} se queda`;
    case "bajarse":
      return `${quien} grita «¡Paren la nave!» y se baja`;
    case "secreto":
      return `${quien} ha escrito su respuesta secreta`;
    case "no_escribe":
      return `${quien} no escribió su respuesta: va una pregunta normal`;
    case "pasa":
      return `${quien} no abre; pasa el turno`;
    default:
      return "";
  }
}

// La cuenta atrás: un anillo que se vacía y los segundos (los pone actualizarReloj).
function reloj(total) {
  return `<span class="reloj" data-total="${total}" aria-label="Segundos que quedan">
    <svg viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="15.5"/><circle class="resto" cx="18" cy="18" r="15.5" data-anillo/></svg>
    <span data-reloj></span></span>`;
}

function controles(s, r) {
  const suyo = !estado.jugandoComo && acompananteDe(r.turno);
  if (suyo) {
    return `<section class="mando mi-turno pasar ${primeraVez(`pasar-${r.numero}-${r.eventos.length}`) ? "entra" : ""}">
      <div class="mando-cab"><span class="rotulo">Pásale el móvil</span>${reloj(r.escribiendo ? 60 : 45)}</div>
      <p class="pasar-a">Le toca a <b>${esc(suyo.nombre)}</b></p>
      <button class="boton principal" type="button" data-accion="coger" data-valor="${suyo.id}">Soy ${esc(suyo.nombre)}, jugar</button>
    </section>`;
  }
  const aviso = (clave) => (primeraVez(clave) ? "entra" : "");
  if (r.escribiendo) {
    if (r.alien === s.yo) {
      return `<form class="mando alien-mando ${aviso(`alien-${r.numero}`)}" data-form="secreto">
        <div class="mando-cab"><span class="rotulo">${icono("alien")}Transmisión secreta</span>${reloj(60)}</div>
        <p>Eres el alien. ${estado.jugandoComo ? "Que no mire nadie: escribe" : "Mira el móvil y escribe"} la respuesta de verdad: nadie más la verá
          hasta el final. Si la aciertan, pierdes ${PUNTOS_ALIEN}; si fallan, ganas ${PUNTOS_ALIEN}.</p>
        <input id="cifra" class="cifra" data-conservar inputmode="numeric" autocomplete="off" aria-label="Tu respuesta secreta" />
        <button class="boton principal">Enviar y que empiecen</button></form>`;
    }
    return `<section class="mando espera-mando">
      <div class="mando-cab"><span class="rotulo">${icono("alien")}Señal alienígena</span>${reloj(60)}</div>
      <p><b>${nombre(r.alien)}</b> está escribiendo su respuesta secreta.</p></section>`;
  }
  if (r.turno === s.yo && r.cifra == null) {
    return `<form class="mando mi-turno ${aviso(`abre-${r.numero}`)}" data-form="abrir">
      <div class="mando-cab"><span class="rotulo">Te toca abrir</span>${reloj(45)}</div>
      <p>Di una cifra y te sientas al mando.</p>
      <input id="cifra" class="cifra" data-conservar inputmode="numeric" autocomplete="off" aria-label="Tu cifra" />
      <button class="boton principal">Abrir con esta cifra</button></form>`;
  }
  if (r.turno === s.yo) {
    const atajos = r.año
      ? [["+1", "mas1"], ["+5", "mas5"], ["+10", "mas10"]]
      : [["+1", "mas1"], ["+10 %", "porciento"], ["×2", "doble"]];
    return `<form class="mando mi-turno ${aviso(`turno-${r.numero}-${r.eventos.length}`)}" data-form="subir">
      <div class="mando-cab"><span class="rotulo">Tu turno</span>${reloj(45)}</div>
      <div class="subida">
        <input id="cifra" class="cifra" data-conservar inputmode="numeric" autocomplete="off"
          placeholder="más de ${fmt(r.cifra, r.año)}" aria-label="Subir a" />
        <div class="atajos">${atajos
          .map(([t, a]) => `<button type="button" data-accion="atajo" data-valor="${a}">${t}</button>`)
          .join("")}</div>
      </div>
      <button class="boton principal">Subir y tomar el mando</button>
      <div class="fila">
        <button type="button" class="boton" data-accion="quedarse">Me quedo</button>
        <button type="button" class="boton peligro" data-accion="bajarse">¡Paren la nave!</button>
      </div></form>`;
  }
  let texto = `Le toca a <b>${nombre(r.turno)}</b>`;
  if (r.bajados[s.yo] != null) texto = `Te has bajado. ${texto}`;
  else if (r.alien === s.yo) texto = `Eres el alien: a ver si fallan. ${texto}`;
  else if (!r.orden.includes(s.yo)) texto = `Entras en la ronda que viene. ${texto}`;
  return `<section class="mando espera-mando"><div class="mando-cab"><span class="rotulo">En espera</span>${reloj(45)}</div>
    <p>${texto}</p></section>`;
}

function resultadoAlien(r) {
  if (!r.alien) return "";
  const p = r.puntos[r.alien] ?? 0;
  const acertada = r.llega && r.cerca;
  const que = acertada ? "Habéis cazado al alien." : "El alien se sale con la suya.";
  const puntos = p > 0 ? `gana ${p}` : p < 0 ? `pierde ${-p}` : "se queda igual";
  return `<p class="linea-alien">${icono("alien")}${que} <b>${nombre(r.alien)}</b> ${puntos}.</p>`;
}

function revelacion(s, r) {
  const conPuntos = Object.entries(r.puntos).sort((a, b) => b[1] - a[1]);
  const nueva = primeraVez(`revela-${r.numero}`) ? "nueva" : "";
  const sello = r.llega ? (r.cerca ? "Aterrizaje perfecto" : "Aterrizaje") : "Se estrella";
  return `<section class="revelacion ${r.llega ? "llega" : "estrella"} ${nueva}">
      <div class="escena" aria-hidden="true">${platillo("viajero")}<span class="suelo"></span></div>
      <p class="rotulo">La respuesta era</p>
      <div class="respuesta ${talla(r.respuesta, r.año)}">${contador(`respuesta-${r.numero}`, r.respuesta, r.año)}</div>
      <p class="sello">${sello}</p>
      <p class="detalle"><b>${nombre(r.capitan)}</b> la dejó en <span class="mono">${fmt(r.cifra, r.año)}</span></p>
      ${resultadoAlien(r)}
      <ol class="tabla puntos-ronda">${conPuntos
        .map(
          ([id, p]) => `<li>${cara(id, true)}<span class="nombre">${nombre(id)}</span>
          <span class="${p > 0 ? "mas" : p < 0 ? "menos" : "cero"}">${p > 0 ? `+${p}` : p < 0 ? `−${-p}` : "0"}</span></li>`,
        )
        .join("")}</ol>
      <button class="boton principal" data-accion="siguiente">${r.ultima ? "Ver la clasificación final" : "Siguiente ronda"}</button>
    </section>`;
}

function vistaRonda(s) {
  const r = s.ronda;
  const barra = cabecera(s, `Ronda ${String(r.numero).padStart(2, "0")}/${String(s.rondas_total).padStart(2, "0")}`);
  const etiqueta = r.alien
    ? `<span class="etiqueta alien">${icono("alien")}Ronda alien · ${nombre(r.alien)}</span>`
    : r.categoria
      ? `<span class="etiqueta">${esc(r.categoria.replace(" 🌶️", ""))}<i></i>${esc(r.dificultad)}</span>`
      : "";
  const pregunta = `<section class="pregunta-caja">
      ${etiqueta}
      <h2 class="pregunta">${esc(r.pregunta)}</h2>
      ${
        r.alien === s.yo && !r.revelada && !r.escribiendo
          ? estado.acompanantes.length
            ? `<p class="secreto"><span class="rotulo">Respuesta guardada</span><span>Este móvil lo compartís: no se enseña.</span></p>`
            : `<p class="secreto"><span class="rotulo">Tu respuesta secreta</span><b>${fmt(r.respuesta, r.año)}</b></p>`
          : ""
      }
    </section>`;
  if (r.revelada) {
    return `${barra}${pregunta}${revelacion(s, r)}
      <section class="panel"><p class="rotulo">Clasificación</p>${clasificacion(s)}</section>`;
  }
  const bajados = Object.entries(r.bajados);
  const eventos = [...r.eventos].reverse();
  const tripulacion = r.a_bordo.filter((id) => id !== r.capitan);
  const cambioMando = r.capitan && primeraVez(`mando-${r.numero}-${r.capitan}-${r.cifra}`) ? "entra" : "";
  return `${barra}${pregunta}
    <section class="nave" aria-label="La nave">
      <div class="nave-cuerpo">
        ${platillo(
          "flota",
          r.capitan
            ? { color: jugador(r.capitan)?.color ?? "#888", inicial: (jugador(r.capitan)?.nombre ?? "?").charAt(0).toUpperCase() }
            : null,
          Boolean(cambioMando),
          true,
        )}
      </div>
      <div class="lectura">
        <div><span class="rotulo">Cifra</span>
          <span class="cifra-grande ${r.cifra == null ? "vacia" : talla(r.cifra, r.año)}">${
            r.cifra == null ? "—" : contador(`cifra-${r.numero}`, r.cifra, r.año)
          }</span></div>
        <div class="al-mando"><span class="rotulo">${r.capitan ? "Al mando" : "Abre"}</span>
          <b>${r.capitan ? nombre(r.capitan) : nombre(r.abre)}${(r.capitan ?? r.abre) === s.yo ? " (tú)" : ""}</b></div>
      </div>
      ${
        tripulacion.length
          ? `<div class="rayo"><ul class="tripulacion">${tripulacion
              .map(
                (id) =>
                  `<li class="${id === r.turno ? "turno" : ""}">${cara(id)}<span>${nombre(id)}</span></li>`,
              )
              .join("")}</ul></div>`
          : ""
      }
      ${
        bajados.length
          ? `<div class="bajados"><span class="rotulo">Fuera de la nave</span><ul>${bajados
              .map(
                ([id, c]) =>
                  `<li>${cara(id, true)}<span class="nombre">${nombre(id)}</span><span class="mono">${fmt(c, r.año)}</span></li>`,
              )
              .join("")}</ul></div>`
          : ""
      }
    </section>
    ${controles(s, r)}
    ${
      eventos.length
        ? `<section class="panel bitacora"><p class="rotulo">Bitácora</p><ul>${eventos
            .map((e) => `<li>${textoEvento(e, r.año)}</li>`)
            .join("")}</ul></section>`
        : ""
    }
    <details class="panel"><summary>Clasificación</summary>${clasificacion(s, true)}</details>`;
}

function vistaFin(s) {
  const orden = [...s.jugadores].sort((a, b) => b.puntos - a.puntos);
  const alturas = { 1: 132, 2: 96, 3: 70 };
  const podio = [orden[1], orden[0], orden[2]]
    .map((j, i) => {
      if (!j) return "";
      const puesto = [2, 1, 3][i];
      return `<div class="escalon p${puesto}">${cara(j.id, "grande")}<span class="nombre">${esc(j.nombre)}</span>
        <div class="peana" style="height:${alturas[puesto]}px"><span class="mono">${j.puntos} PTS</span><b>${puesto}º</b></div></div>`;
    })
    .join("");
  const empatados = orden.filter((j) => j.puntos === orden[0].puntos);
  const titular =
    empatados.length > 1
      ? `Empate arriba: ${empatados.map((j) => esc(j.nombre)).join(" y ")}`
      : `${esc(orden[0].nombre)} pilota la nave`;
  return `${cabecera(s, "Final")}
    <header class="portada fin"><p class="rotulo">Fin de la misión</p><h1><span>${titular}</span></h1></header>
    <div class="podio ${primeraVez("podio-" + orden.map((j) => j.puntos).join()) ? "nueva" : ""}">${podio}</div>
    <section class="panel"><p class="rotulo">Clasificación</p>${clasificacion(s)}</section>
    ${bloqueProyecto()}
    ${ajustesPartida(s)}
    ${
      s.anfitrion === s.yo
        ? `<button class="boton principal grande" data-accion="empezar">Otra partida</button>`
        : `<p class="espera-despegue">Esperando a que <b>${nombre(s.anfitrion)}</b> lance otra partida</p>`
    }
    <button class="enlace" data-accion="compartir">Pasar el enlace a alguien más</button>
    ${firma()}`;
}

// --- Pintar sin perder lo que uno está escribiendo ---------------------------------

function pintar() {
  let html;
  const s = estado.sala;
  if (!estado.token || estado.error) html = vistaInicio();
  else if (!s) html = `<div class="conectando">${platillo("flota")}<p class="rotulo">Conectando con la nave</p></div>`;
  else if (s.fase === "espera") html = vistaEspera(s);
  else if (s.fase === "jugando") html = vistaRonda(s);
  else html = vistaFin(s);
  if (estado.sinRed) html = `<p class="sin-red">Sin señal · reintentando</p>${html}`;

  // La pantalla del alien se pone verde mientras dura su ronda.
  const soyAlien = s?.fase === "jugando" && s.ronda?.alien === s.yo && !s.ronda.revelada;
  document.documentElement.classList.toggle("alien", Boolean(soyAlien));
  const miTurno =
    s?.fase === "jugando" && (s.ronda?.turno === s.yo || Boolean(acompananteDe(s.ronda?.turno)));
  if (miTurno && !estado.eraMiTurno) navigator.vibrate?.(150);
  estado.eraMiTurno = miTurno;

  if (html === estado.ultimoHtml) {
    actualizarReloj();
    return;
  }
  const activo = document.activeElement;
  const foco = activo?.id && raiz.contains(activo) ? activo.id : null;
  const seleccion = foco ? [activo.selectionStart, activo.selectionEnd] : null;
  const valores = {};
  for (const input of raiz.querySelectorAll("input[data-conservar]")) valores[input.id] = input.value;
  const abiertos = new Set(
    [...raiz.querySelectorAll("details")].map((d, i) => (d.open ? i : -1)).filter((i) => i >= 0),
  );

  raiz.innerHTML = html;
  estado.ultimoHtml = html;

  for (const [id, valor] of Object.entries(valores)) {
    const input = document.getElementById(id);
    if (input?.dataset.conservar !== undefined) input.value = valor;
  }
  raiz.querySelectorAll("details").forEach((d, i) => {
    if (abiertos.has(i)) d.open = true;
  });
  const enfocar = foco && document.getElementById(foco);
  if (enfocar) {
    enfocar.focus({ preventScroll: true });
    try {
      enfocar.setSelectionRange(...seleccion);
    } catch {
      // Hay inputs que no admiten selección.
    }
  }
  actualizarReloj();
  efectos();
}

function actualizarReloj() {
  const r = estado.sala?.ronda;
  if (!r?.turno) return;
  const quedan = segundosQuedan(r);
  for (const caja of raiz.querySelectorAll(".reloj")) {
    caja.querySelector("[data-reloj]").textContent = String(Math.min(quedan, 99)).padStart(2, "0");
    const anillo = caja.querySelector("[data-anillo]");
    const parte = Math.min(1, quedan / Number(caja.dataset.total));
    anillo.style.strokeDashoffset = String(97.4 * (1 - parte));
    caja.classList.toggle("apurado", quedan <= 10);
  }
}

// Los números que cambian ruedan desde el valor anterior, como un contador mecánico.
const valoresVistos = new Map();
const sinMovimiento = matchMedia("(prefers-reduced-motion: reduce)").matches;
function efectos() {
  for (const el of raiz.querySelectorAll(".contador")) {
    const clave = el.dataset.clave;
    const final = Number(el.dataset.valor);
    const año = el.dataset.año === "1";
    if (el.dataset.valor === "" || !Number.isFinite(final)) continue;
    const previo = valoresVistos.get(clave);
    valoresVistos.set(clave, final);
    if (previo === final || sinMovimiento) continue;
    // La respuesta rueda desde cero, con más suspense; la cifra, desde la anterior.
    const desde = previo ?? (clave.startsWith("respuesta") ? (año ? final - 60 : 0) : final);
    if (desde === final) continue;
    const dura = clave.startsWith("respuesta") ? 1400 : 500;
    const inicio = performance.now();
    const paso = (ahora) => {
      const t = Math.min(1, (ahora - inicio) / dura);
      const suave = 1 - Math.pow(1 - t, 3);
      el.textContent = fmt(Math.round(desde + (final - desde) * suave), año);
      if (t < 1 && el.isConnected) requestAnimationFrame(paso);
    };
    requestAnimationFrame(paso);
  }
}

// --- Lo que se toca ------------------------------------------------------------------

function compartir() {
  const url = `${location.origin}/s/${estado.codigo}`;
  if (navigator.share) {
    navigator.share({ title: "¡Paren la nave!", text: "Súbete a la nave:", url }).catch(() => {});
    return;
  }
  navigator.clipboard?.writeText(url).then(
    () => tostada("Enlace copiado. Pégalo en el grupo."),
    () => tostada(url),
  );
}

// Dos toques: un toque sin querer no te saca de la partida.
let temporizadorSalida;
async function salir() {
  if (!estado.confirmarSalida) {
    estado.confirmarSalida = true;
    pintar();
    clearTimeout(temporizadorSalida);
    temporizadorSalida = setTimeout(() => {
      estado.confirmarSalida = false;
      pintar();
    }, 4000);
    return;
  }
  clearTimeout(temporizadorSalida);
  estado.confirmarSalida = false;
  try {
    // Primero los que jugaban en este móvil: sin él no pueden seguir.
    for (const a of estado.acompanantes) {
      estado.jugandoComo = a;
      await api(`/salas/${estado.codigo}/salir`, { metodo: "POST" }).catch(() => {});
    }
    estado.jugandoComo = null;
    await api(`/salas/${estado.codigo}/salir`, { metodo: "POST" });
  } catch {
    // Aunque no llegue, en este móvil se sale igual; el turno pasará solo.
  }
  olvidarSesion();
  estado.codigo = null;
  history.replaceState(null, "", "/");
  pintar();
  tostada("Has salido de la nave.");
}

let temporizadorEchar;
function echar(id) {
  clearTimeout(temporizadorEchar);
  if (estado.confirmarEchar !== id) {
    estado.confirmarEchar = id;
    pintar();
    temporizadorEchar = setTimeout(() => {
      estado.confirmarEchar = null;
      pintar();
    }, 4000);
    return;
  }
  estado.confirmarEchar = null;
  accion("/echar", { jugador: id });
}

function atajo(tipo) {
  const r = estado.sala.ronda;
  const base = r.cifra ?? 0;
  const nuevas = {
    mas1: base + 1,
    mas5: base + 5,
    mas10: base + 10,
    porciento: Math.max(base + 1, Math.ceil(base * 1.1)),
    doble: Math.max(base + 1, base * 2),
  };
  const input = document.getElementById("cifra");
  input.value = String(nuevas[tipo]);
}

raiz.addEventListener("click", async (evento) => {
  const boton = evento.target.closest("[data-accion]");
  if (!boton || boton.type === "checkbox") return;
  const s = estado.sala;
  switch (boton.dataset.accion) {
    case "nueva":
      estado.codigo = null;
      history.replaceState(null, "", "/");
      pintar();
      break;
    case "compartir":
      compartir();
      break;
    case "salir":
      salir();
      break;
    case "coger":
      cogerMovil(boton.dataset.valor);
      break;
    case "devolver":
      devolverMovil(false);
      break;
    case "echar":
      echar(boton.dataset.valor);
      break;
    case "rondas":
      guardarAjustes({ rondas: Number(boton.dataset.valor) });
      break;
    case "categoria": {
      const categorias = alternar(s.categorias, boton.dataset.valor, "categoría");
      if (categorias) guardarAjustes({ categorias });
      break;
    }
    case "dificultad": {
      const dificultades = alternar(s.dificultades, boton.dataset.valor, "dificultad");
      if (dificultades) guardarAjustes({ dificultades });
      break;
    }
    case "empezar":
      accion("/empezar");
      break;
    case "atajo":
      atajo(boton.dataset.valor);
      break;
    case "quedarse":
      accion("/jugada", { accion: "quedarse" });
      break;
    case "bajarse":
      accion("/jugada", { accion: "bajarse" });
      break;
    case "siguiente":
      accion("/siguiente", { desde: s.ronda.numero });
      break;
  }
});

raiz.addEventListener("change", (evento) => {
  if (evento.target.dataset.accion === "del-grupo") {
    guardarAjustes({ del_grupo: evento.target.checked });
  }
});

raiz.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const formulario = evento.target.dataset.form;
  const valor = (id) => document.getElementById(id)?.value.trim() ?? "";
  try {
    if (formulario === "crear" || formulario === "entrar") {
      almacen.poner("nave:nombre", valor("nombre"));
      if (formulario === "crear") await crear(valor("nombre"));
      else await entrar(estado.codigo, valor("nombre"));
    } else if (formulario === "unirse") {
      almacen.poner("nave:nombre", valor("nombre2"));
      const codigo = valor("codigo").toUpperCase();
      if (!/^[A-Z]{4,6}$/.test(codigo)) {
        tostada("El código son letras, como ABCDEF.");
        return;
      }
      await entrar(codigo, valor("nombre2"));
    } else if (formulario === "acompanante") {
      const quien = valor("acomp");
      await anadirAcompanante(quien);
      const input = document.getElementById("acomp");
      if (input) input.value = "";
    } else if (formulario === "abrir" || formulario === "subir" || formulario === "secreto") {
      const cifra = leerNumero(valor("cifra"));
      if (cifra == null) {
        tostada("Escribe un número.");
        return;
      }
      await accion("/jugada", { accion: formulario, cifra });
    }
  } catch (e) {
    tostada(e.message);
  }
});

// --- Arranque ---------------------------------------------------------------------------

async function arrancar() {
  estado.codigo = codigoDeLaDireccion();
  if (estado.codigo) {
    estado.token = almacen.leer(`nave:${estado.codigo}`);
    cargarAcompanantes();
  }
  pintar();
  try {
    estado.opciones = await api("/opciones");
  } catch {
    // Sin ellas no se pueden cambiar las categorías, pero se juega con las de siempre.
  }
  if (estado.token) consultar();
}

arrancar();
setInterval(actualizarReloj, 1000);
