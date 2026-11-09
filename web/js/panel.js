import { pedir } from "/js/api.js";
import {
  MS_POR_SEGUNDO,
  crear,
  formatearValor,
  iniciarPagina,
  insignia,
  insigniaSeveridad,
  repetirMientrasVisible,
} from "/js/comun.js";

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

let fecha = null;

function crearLecturas(lecturas) {
  const lista = crear("dl", "grid grid-cols-2 gap-x-3 gap-y-2");
  for (const lectura of lecturas) {
    const fila = crear("div", "rounded bg-slate-100 p-2");
    fila.append(
      crear("dt", "text-sm text-slate-700", lectura.nombre),
      crear("dd", "text-lg font-semibold", formatearValor(lectura.valor, lectura.unidad, lectura.tipo)),
    );
    lista.append(fila);
  }
  return lista;
}

function crearAlertas(alertas) {
  const seccion = crear("section", "mb-3");
  seccion.setAttribute("aria-label", "Alertas activas");
  const lista = crear("ul", "space-y-2");
  for (const alerta of alertas) {
    const elemento = crear("li", "flex flex-wrap items-center gap-2 rounded border border-slate-300 p-2");
    const valor = alerta.valor !== null ? ` (${formatearValor(alerta.valor, alerta.unidad)})` : "";
    const texto = alerta.variable_nombre ? `${alerta.variable_nombre}${valor}` : alerta.descripcion;
    elemento.append(insigniaSeveridad(alerta.severidad), crear("span", "", texto));
    lista.append(elemento);
  }
  seccion.append(lista);
  return seccion;
}

function textoUltimoDato(tanque) {
  if (!tanque.nodo) return "Este tanque aún no tiene un nodo asignado.";
  if (!tanque.nodo.ultimo_contacto) return "El nodo todavía no ha reportado.";
  return `Último dato: ${fecha(tanque.nodo.ultimo_contacto)}`;
}

function crearTarjeta(tanque) {
  const tarjeta = crear("article", "rounded-lg bg-white p-4 shadow");
  const encabezado = crear("div", "mb-3 flex items-start justify-between gap-2");
  const { texto, icono, clases } = ESTADOS[tanque.estado];
  const titulo = crear("h2", "text-xl font-bold break-words");
  const enlace = crear("a", "underline decoration-sky-700 underline-offset-4 hover:text-sky-900", tanque.nombre);
  enlace.href = `/tanque.html?id=${encodeURIComponent(tanque.id)}`;
  titulo.append(enlace);
  encabezado.append(titulo, insignia(texto, icono, clases));
  tarjeta.append(encabezado);
  if (tanque.alertas.length > 0) tarjeta.append(crearAlertas(tanque.alertas));
  if (tanque.lecturas.length > 0) {
    tarjeta.append(crearLecturas(tanque.lecturas));
  } else if (tanque.nodo) {
    tarjeta.append(crear("p", "text-slate-700", "Sin lecturas todavía."));
  }
  tarjeta.append(crear("p", "mt-3 text-sm text-slate-700", textoUltimoDato(tanque)));
  return tarjeta;
}

async function cargarTanques() {
  try {
    const tanques = await pedir("/api/v1/tanques");
    contenedor.replaceChildren(...tanques.map(crearTarjeta));
    vacio.hidden = tanques.length > 0;
    cajaError.hidden = true;
    actualizado.textContent = `Actualizado: ${fecha(new Date().toISOString())}`;
  } catch (fallo) {
    // Se conservan los datos anteriores: el aviso indica que pueden estar desactualizados.
    mensajeError.textContent = `${fallo.message} Los datos mostrados pueden estar desactualizados.`;
    cajaError.hidden = false;
    if (contenedor.childElementCount === 0) actualizado.textContent = "No se pudieron cargar los tanques.";
  }
}

async function iniciar() {
  try {
    const pagina = await iniciarPagina();
    fecha = pagina.fecha;
    const sondeo = repetirMientrasVisible(cargarTanques, pagina.yo.polling_panel_s * MS_POR_SEGUNDO);
    document.getElementById("reintentar").addEventListener("click", cargarTanques);
    await sondeo.iniciar();
  } catch (fallo) {
    mensajeError.textContent = fallo.message;
    cajaError.hidden = false;
    actualizado.textContent = "No se pudo cargar el panel.";
  }
}

iniciar();
