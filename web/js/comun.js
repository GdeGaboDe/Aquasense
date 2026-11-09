// Utilidades compartidas por las pantallas con sesión: navegación, fechas y creación de nodos.

import { pedir } from "/js/api.js";

export const MS_POR_SEGUNDO = 1000;

const SEVERIDADES = {
  critica: { texto: "Crítica", icono: "!!", clases: "bg-red-100 text-red-900" },
  advertencia: { texto: "Advertencia", icono: "!", clases: "bg-amber-100 text-amber-900" },
  info: { texto: "Info", icono: "i", clases: "bg-sky-100 text-sky-900" },
};

const MOTIVOS = {
  MINIMO_NO_MENOR_QUE_MAXIMO: "el mínimo debe ser menor que el máximo",
  HISTERESIS_DEMASIADO_GRANDE: "la histéresis debe ser menor que la mitad del rango",
  HISTERESIS_NEGATIVA: "la histéresis no puede ser negativa",
  FUERA_DE_RANGO_FISICO: "está fuera de lo que el sensor puede medir",
  VARIABLE_NO_NUMERICA: "esta variable no admite umbral",
  VALOR_INVALIDO: "valor fuera del rango permitido",
  MODULO_NO_DISPONIBLE: "el nodo no tiene el módulo de este parámetro",
  PARAMETRO_DESCONOCIDO: "parámetro desconocido",
};

function explicarMotivo(motivo) {
  if (MOTIVOS[motivo]) return MOTIVOS[motivo];
  const menor = /^DEBE_SER_MENOR_QUE_(.+)$/.exec(motivo ?? "");
  return menor ? `debe ser menor que ${menor[1]}` : String(motivo ?? "");
}

/** Crea un elemento. El texto siempre va con textContent: nunca se interpreta como HTML. */
export function crear(etiqueta, clases, texto) {
  const elemento = document.createElement(etiqueta);
  if (clases) elemento.className = clases;
  if (texto !== undefined && texto !== null) elemento.textContent = texto;
  return elemento;
}

export function insignia(texto, icono, clases) {
  const caja = crear("span", `inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded px-2 py-1 text-sm font-semibold ${clases}`);
  const simbolo = crear("span", "", icono);
  simbolo.setAttribute("aria-hidden", "true");
  caja.append(simbolo, crear("span", "", texto));
  return caja;
}

export function insigniaSeveridad(severidad) {
  const { texto, icono, clases } = SEVERIDADES[severidad] ?? SEVERIDADES.info;
  return insignia(texto, icono, clases);
}

export function formatearValor(valor, unidad, tipo) {
  if (valor === null || valor === undefined) return "—";
  if (tipo === "booleano") return valor === 1 ? "Sí" : "No";
  return unidad ? `${valor} ${unidad}` : String(valor);
}

/** Muestra un aviso accesible; tipo "error" o "exito". */
export function avisar(elemento, mensaje, tipo = "error", detalles = null) {
  elemento.replaceChildren(crear("p", "", mensaje));
  if (Array.isArray(detalles) && detalles.length > 0) {
    const lista = crear("ul", "mt-1 list-disc pl-5");
    for (const detalle of detalles) {
      const quien = detalle.parametro ?? detalle.variable ?? "";
      const motivo = explicarMotivo(detalle.motivo);
      lista.append(crear("li", "", quien ? `${quien}: ${motivo}` : motivo));
    }
    elemento.append(lista);
  }
  elemento.className = `mb-3 rounded p-3 ${tipo === "error" ? "bg-red-100 text-red-900" : "bg-green-100 text-green-900"}`;
  elemento.hidden = false;
}

export function ocultar(elemento) {
  elemento.hidden = true;
}

function marcarNavegacion() {
  for (const enlace of document.querySelectorAll("nav a")) {
    if (enlace.getAttribute("href") === window.location.pathname) {
      enlace.setAttribute("aria-current", "page");
      enlace.classList.add("underline", "decoration-2", "underline-offset-4");
    }
  }
}

function activarSalida() {
  document.getElementById("salir")?.addEventListener("click", async () => {
    try {
      await pedir("/api/v1/auth/logout", { metodo: "POST" });
    } finally {
      window.location.assign("/login.html");
    }
  });
}

/**
 * Prepara una pantalla con sesión. Devuelve la configuración del usuario y un formateador de fecha
 * en la zona horaria del servidor. Redirige al login si la sesión no es válida.
 */
export async function iniciarPagina() {
  // Al volver con "Atrás" el navegador puede restaurar la página desde su caché, con datos viejos y
  // aunque la sesión ya se cerró. Recargar obliga a pedir los datos otra vez: sin sesión, va al login.
  window.addEventListener("pageshow", (evento) => {
    if (evento.persisted) window.location.reload();
  });
  marcarNavegacion();
  activarSalida();
  const yo = await pedir("/api/v1/auth/yo");
  const formatoFecha = new Intl.DateTimeFormat("es-MX", {
    timeZone: yo.zona_horaria,
    dateStyle: "short",
    timeStyle: "medium",
  });
  return { yo, fecha: (iso) => (iso ? formatoFecha.format(new Date(iso)) : "—") };
}

/**
 * Repite una tarea cada `intervaloMs` solo mientras la pestaña está visible.
 * Al volver a la pestaña solo consulta si ya pasó el intervalo: cambiar de app o de pestaña
 * seguido no debe multiplicar las peticiones ni agotar el límite del servidor.
 */
export function repetirMientrasVisible(tarea, intervaloMs) {
  let temporizador = null;
  let ultimaEjecucion = 0;
  let enCurso = false;
  const programar = (esperaMs) => {
    clearTimeout(temporizador);
    if (document.visibilityState === "visible") temporizador = setTimeout(ejecutar, esperaMs);
  };
  const ejecutar = async () => {
    if (enCurso) return;
    enCurso = true;
    ultimaEjecucion = Date.now();
    try {
      await tarea();
    } finally {
      enCurso = false;
    }
    programar(intervaloMs);
  };
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") {
      clearTimeout(temporizador);
      return;
    }
    programar(Math.max(0, intervaloMs - (Date.now() - ultimaEjecucion)));
  });
  return { iniciar: ejecutar, detener: () => clearTimeout(temporizador) };
}

/** Llena un <select> de tanques; `filtro` decide cuáles aparecen. Devuelve los tanques mostrados. */
export async function llenarSelectorTanques(selector, filtro = () => true) {
  const tanques = (await pedir("/api/v1/tanques")).filter(filtro);
  selector.replaceChildren(
    ...tanques.map((tanque) => {
      const opcion = crear("option", "", tanque.nombre);
      opcion.value = String(tanque.id);
      return opcion;
    }),
  );
  return tanques;
}

/** Campo de formulario para un parámetro del catálogo, con su etiqueta y sus límites. */
export function campoParametro(parametro) {
  const contenedor = crear("div", "mb-3");
  const id = `param-${parametro.codigo}`;
  const etiqueta = crear("label", "mb-1 block font-medium", parametro.descripcion);
  etiqueta.htmlFor = id;
  let control;
  if (parametro.tipo === "opcion") {
    control = crear("select", "w-full rounded border border-slate-500 p-2 text-base");
    for (const opcion of parametro.opciones) {
      const elemento = crear("option", "", opcion);
      elemento.value = opcion;
      control.append(elemento);
    }
  } else {
    control = crear("input", "w-full rounded border border-slate-500 p-2 text-base");
    control.type = "number";
    control.step = parametro.tipo === "entero" ? "1" : "any";
    if (parametro.minimo !== null) control.min = String(parametro.minimo);
    if (parametro.maximo !== null) control.max = String(parametro.maximo);
    control.required = true;
  }
  control.id = id;
  control.name = parametro.codigo;
  control.value = String(parametro.valor);
  const ayuda = crear("p", "mt-1 text-sm text-slate-700", textoAyuda(parametro));
  ayuda.id = `${id}-ayuda`;
  control.setAttribute("aria-describedby", ayuda.id);
  contenedor.append(etiqueta, control, ayuda);
  return contenedor;
}

function textoAyuda(parametro) {
  const unidad = parametro.unidad ? ` ${parametro.unidad}` : "";
  const rango =
    parametro.tipo === "opcion"
      ? `Opciones: ${parametro.opciones.join(", ")}`
      : `Entre ${parametro.minimo} y ${parametro.maximo}${unidad}`;
  return `${rango}. De fábrica: ${parametro.valor_defecto}${parametro.tipo === "opcion" ? "" : unidad}.`;
}

/** Lee los valores de los campos de parámetros de un formulario, con el tipo que espera la API. */
export function leerParametros(formulario, parametros) {
  const valores = {};
  for (const parametro of parametros) {
    const control = formulario.elements.namedItem(parametro.codigo);
    if (!control) continue;
    valores[parametro.codigo] = parametro.tipo === "opcion" ? control.value : Number(control.value);
  }
  return valores;
}
