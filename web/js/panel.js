import { pedir } from "/js/api.js";

const MS_POR_SEGUNDO = 1000;
const ESTADOS = {
  en_linea: { texto: "En línea", icono: "✓", clases: "bg-green-100 text-green-900" },
  sin_conexion: { texto: "Sin conexión", icono: "!", clases: "bg-red-100 text-red-900" },
  sin_nodo: { texto: "Sin nodo", icono: "–", clases: "bg-slate-200 text-slate-900" },
};

const contenedor = document.getElementById("tanques");
const actualizado = document.getElementById("actualizado");
const vacio = document.getElementById("vacio");
const cajaError = document.getElementById("error");
const mensajeError = document.getElementById("error-mensaje");

let intervaloMs = null;
let temporizador = null;
let formatoFecha = null;

function crear(etiqueta, clases, texto) {
  const elemento = document.createElement(etiqueta);
  if (clases) elemento.className = clases;
  // Siempre textContent: los datos del servidor nunca se interpretan como HTML.
  if (texto !== undefined) elemento.textContent = texto;
  return elemento;
}

function formatearValor(lectura) {
  if (lectura.tipo === "booleano") return lectura.valor === 1 ? "Sí" : "No";
  return lectura.unidad ? `${lectura.valor} ${lectura.unidad}` : String(lectura.valor);
}

function crearInsignia(estado) {
  const { texto, icono, clases } = ESTADOS[estado];
  const insignia = crear("p", `inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded px-2 py-1 text-sm font-semibold ${clases}`);
  const simbolo = crear("span", "", icono);
  simbolo.setAttribute("aria-hidden", "true");
  insignia.append(simbolo, crear("span", "", texto));
  return insignia;
}

function crearLecturas(lecturas) {
  const lista = crear("dl", "grid grid-cols-2 gap-x-3 gap-y-2");
  for (const lectura of lecturas) {
    const fila = crear("div", "rounded bg-slate-100 p-2");
    fila.append(
      crear("dt", "text-sm text-slate-700", lectura.nombre),
      crear("dd", "text-lg font-semibold", formatearValor(lectura)),
    );
    lista.append(fila);
  }
  return lista;
}

function textoUltimoDato(tanque) {
  if (!tanque.nodo) return "Este tanque aún no tiene un nodo asignado.";
  if (!tanque.nodo.ultimo_contacto) return "El nodo todavía no ha reportado.";
  return `Último dato: ${formatoFecha.format(new Date(tanque.nodo.ultimo_contacto))}`;
}

function crearTarjeta(tanque) {
  const tarjeta = crear("article", "rounded-lg bg-white p-4 shadow");
  const encabezado = crear("div", "mb-3 flex items-start justify-between gap-2");
  encabezado.append(crear("h2", "text-xl font-bold break-words", tanque.nombre), crearInsignia(tanque.estado));
  tarjeta.append(encabezado);
  if (tanque.lecturas.length > 0) {
    tarjeta.append(crearLecturas(tanque.lecturas));
  } else if (tanque.nodo) {
    tarjeta.append(crear("p", "text-slate-700", "Sin lecturas todavía."));
  }
  tarjeta.append(crear("p", "mt-3 text-sm text-slate-700", textoUltimoDato(tanque)));
  return tarjeta;
}

function pintar(tanques) {
  contenedor.replaceChildren(...tanques.map(crearTarjeta));
  vacio.classList.toggle("hidden", tanques.length > 0);
  cajaError.classList.add("hidden");
  actualizado.textContent = `Actualizado: ${formatoFecha.format(new Date())}`;
}

function detenerPolling() {
  clearTimeout(temporizador);
  temporizador = null;
}

function programarSiguiente() {
  detenerPolling();
  if (document.visibilityState === "visible" && intervaloMs !== null) {
    temporizador = setTimeout(cargarTanques, intervaloMs);
  }
}

async function cargarTanques() {
  try {
    pintar(await pedir("/api/v1/tanques"));
  } catch (fallo) {
    // Los datos anteriores se conservan: el aviso indica que pueden estar desactualizados.
    mensajeError.textContent = `${fallo.message} Los datos mostrados pueden estar desactualizados.`;
    cajaError.classList.remove("hidden");
    if (contenedor.childElementCount === 0) actualizado.textContent = "No se pudieron cargar los tanques.";
  }
  programarSiguiente();
}

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    cargarTanques();
  } else {
    detenerPolling();
  }
});

document.getElementById("reintentar").addEventListener("click", cargarTanques);

document.getElementById("salir").addEventListener("click", async () => {
  detenerPolling();
  try {
    await pedir("/api/v1/auth/logout", { metodo: "POST" });
  } finally {
    window.location.assign("/login.html");
  }
});

async function iniciar() {
  try {
    const yo = await pedir("/api/v1/auth/yo");
    intervaloMs = yo.polling_panel_s * MS_POR_SEGUNDO;
    formatoFecha = new Intl.DateTimeFormat("es-MX", {
      timeZone: yo.zona_horaria,
      dateStyle: "short",
      timeStyle: "medium",
    });
    await cargarTanques();
  } catch (fallo) {
    mensajeError.textContent = fallo.message;
    cajaError.classList.remove("hidden");
    actualizado.textContent = "No se pudo cargar el panel.";
  }
}

iniciar();
