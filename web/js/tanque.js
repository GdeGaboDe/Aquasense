/* global Chart */
import { pedir } from "/js/api.js";
import { MS_POR_SEGUNDO, avisar, crear, iniciarPagina, insignia, ocultar, repetirMientrasVisible } from "/js/comun.js";

const HORA_MS = 3600 * MS_POR_SEGUNDO;
// Intervalo de agregación por rango: siempre por debajo del máximo de 2,000 puntos del servidor.
const RANGOS = {
  "6h": { duracionMs: 6 * HORA_MS, intervalo: "1m", texto: "últimas 6 horas" },
  "24h": { duracionMs: 24 * HORA_MS, intervalo: "5m", texto: "últimas 24 horas" },
  "7d": { duracionMs: 7 * 24 * HORA_MS, intervalo: "1h", texto: "últimos 7 días" },
};
const ESTADOS = {
  en_linea: ["En línea", "✓", "bg-green-100 text-green-900"],
  sin_conexion: ["Sin conexión", "!", "bg-red-100 text-red-900"],
  sin_nodo: ["Sin nodo", "–", "bg-slate-200 text-slate-900"],
};
const MOTIVOS = {
  DATOS_INSUFICIENTES: "Estimación aún no confiable: hacen falta al menos 24 horas y 50 lecturas de TDS desde el último cambio.",
  PENDIENTE_NO_POSITIVA: "Estimación aún no confiable: el TDS no está subiendo, así que no hay tendencia que extrapolar.",
  SIN_UMBRAL_TDS: "Define el máximo de TDS en Ajustes → Umbrales para poder estimar.",
  SIN_SENSOR_TDS: "Este tanque no tiene sensor de TDS: no se puede estimar.",
};

const id = new URLSearchParams(window.location.search).get("id");
const carga = document.getElementById("estado-carga");
const aviso = document.getElementById("aviso");

let fecha = null;
let zonaHoraria = "America/Mexico_City";
let rango = "24h";
let variables = [];
let umbrales = {};
const graficas = new Map();

function fechaSinSegundos(iso) {
  return new Intl.DateTimeFormat("es-MX", { timeZone: zonaHoraria, dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
}

function dias(valor) {
  const redondeado = Math.round(valor * 10) / 10;
  return `${redondeado} ${redondeado === 1 ? "día" : "días"}`;
}

function pintarPrediccion(p) {
  const principal = document.getElementById("prediccion-principal");
  if (p.estado === "confiable") {
    principal.textContent =
      p.dias_restantes === 0
        ? "El TDS ya alcanzó el límite: toca cambiar el agua."
        : `En ${dias(p.dias_restantes)} (aprox. el ${fechaSinSegundos(p.fecha_estimada)})`;
  } else {
    principal.textContent = MOTIVOS[p.motivo] ?? "Estimación aún no confiable.";
  }
  const baseline = document.getElementById("prediccion-baseline");
  baseline.textContent =
    p.baseline_dias === null
      ? "Sin historial suficiente para una referencia: se necesita al menos un ciclo completo."
      : `Referencia por historial: los ciclos duran ${dias(p.baseline_dias)} en promedio (quedarían ${dias(p.baseline_dias_restantes)}).`;

  const filas = [
    ["Ciclo iniciado", fecha(p.ciclo_iniciado_en)],
    ["Días transcurridos", String(p.dias_transcurridos)],
    ["Límite de TDS", p.limite_tds === null ? "Sin definir" : `${p.limite_tds} ppm`],
    ["Tendencia", p.pendiente_ppm_por_dia === null ? "—" : `${p.pendiente_ppm_por_dia} ppm/día`],
    ["Ajuste (R²)", p.r2 === null ? "—" : String(p.r2)],
    ["Lecturas usadas", `${p.n_muestras} (${p.horas_de_datos} h)`],
    ["Modelo", p.modelo_version],
  ];
  if (p.evaluacion) {
    const { mae_modelo_dias: modelo, mae_baseline_dias: base, predicciones_evaluadas: n } = p.evaluacion;
    filas.push(["Error del modelo (MAE)", `${modelo} días en ${n} predicciones del último ciclo`]);
    filas.push(["Error del historial (MAE)", base === null ? "—" : `${base} días`]);
  }
  document.getElementById("prediccion-detalles").replaceChildren(
    ...filas.flatMap(([etiqueta, valor]) => [crear("dt", "font-medium", etiqueta), crear("dd", "", valor)]),
  );
}

async function cargarPrediccion() {
  pintarPrediccion(await pedir(`/api/v1/tanques/${id}/prediccion`));
}

async function cargarCambios() {
  const datos = await pedir(`/api/v1/tanques/${id}/cambios-agua?tamano=5`);
  document.getElementById("cambios").replaceChildren(
    ...datos.elementos.map((c) => crear("li", "py-1", `${fecha(c.realizado_en)} · ${c.porcentaje}%`)),
  );
}

async function registrarCambio(evento) {
  evento.preventDefault();
  const formulario = evento.target;
  const avisoCambio = document.getElementById("aviso-cambio");
  if (!formulario.reportValidity()) return;
  try {
    await pedir(`/api/v1/tanques/${id}/cambios-agua`, {
      metodo: "POST",
      cuerpo: { porcentaje: Number(document.getElementById("porcentaje").value) },
    });
    avisar(avisoCambio, "Cambio registrado. Empieza un ciclo nuevo para la predicción.", "exito");
    await Promise.all([cargarCambios(), cargarPrediccion()]);
  } catch (fallo) {
    avisar(avisoCambio, fallo.message, "error", fallo.detalles);
  }
}

function formatoEje(valorMs) {
  const opciones = rango === "7d" ? { day: "2-digit", month: "2-digit", hour: "2-digit" } : { hour: "2-digit", minute: "2-digit" };
  return new Intl.DateTimeFormat("es-MX", { timeZone: zonaHoraria, ...opciones }).format(new Date(valorMs));
}

function lineaDeUmbral(etiqueta, valor, desde, hasta) {
  return { label: etiqueta, data: [{ x: desde, y: valor }, { x: hasta, y: valor }], borderColor: "#b45309", borderDash: [6, 4], borderWidth: 1.5, pointRadius: 0 };
}

function crearTarjetaGrafica(variable) {
  const tarjeta = crear("figure", "rounded border border-slate-200 p-3");
  const titulo = crear("figcaption", "mb-1 font-semibold", variable.unidad ? `${variable.nombre} (${variable.unidad})` : variable.nombre);
  const resumen = crear("p", "mb-2 text-sm text-slate-700", "Cargando…");
  const lienzo = crear("canvas");
  lienzo.setAttribute("role", "img");
  lienzo.setAttribute("aria-label", `Gráfica de ${variable.nombre}`);
  const contenedor = crear("div", "relative h-56");
  contenedor.append(lienzo);
  tarjeta.append(titulo, resumen, contenedor);
  const grafica = new Chart(lienzo, {
    type: "line",
    data: { datasets: [] },
    options: {
      maintainAspectRatio: false,
      animation: false,
      parsing: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { title: (items) => fecha(new Date(items[0].parsed.x).toISOString()) } } },
      scales: { x: { type: "linear", ticks: { callback: formatoEje, maxTicksLimit: 6 } } },
    },
  });
  graficas.set(variable.variable, { grafica, resumen, lienzo });
  return tarjeta;
}

async function actualizarGrafica(variable) {
  const { grafica, resumen, lienzo } = graficas.get(variable.variable);
  const { duracionMs, intervalo, texto } = RANGOS[rango];
  const hasta = new Date();
  const desde = new Date(hasta.getTime() - duracionMs);
  const parametros = new URLSearchParams({ variable: variable.variable, desde: desde.toISOString(), hasta: hasta.toISOString(), intervalo });
  const serie = await pedir(`/api/v1/tanques/${id}/lecturas?${parametros}`);
  const puntos = serie.puntos.map((p) => ({ x: new Date(p.t).getTime(), y: p.valor }));
  const conjuntos = [{ label: variable.nombre, data: puntos, borderColor: "#075985", backgroundColor: "#075985", borderWidth: 2, pointRadius: 0, spanGaps: false }];
  const umbral = umbrales[variable.variable];
  if (umbral?.minimo !== null && umbral?.minimo !== undefined) conjuntos.push(lineaDeUmbral("Mínimo", umbral.minimo, desde.getTime(), hasta.getTime()));
  if (umbral?.maximo !== null && umbral?.maximo !== undefined) conjuntos.push(lineaDeUmbral("Máximo", umbral.maximo, desde.getTime(), hasta.getTime()));
  grafica.data.datasets = conjuntos;
  grafica.options.scales.x.min = desde.getTime();
  grafica.options.scales.x.max = hasta.getTime();
  grafica.update();

  // Resumen en texto: la información no depende solo de ver la gráfica.
  if (puntos.length === 0) {
    resumen.textContent = `Sin datos en las ${texto.replace("últimas ", "").replace("últimos ", "")}.`;
    lienzo.setAttribute("aria-label", `Gráfica de ${variable.nombre}: sin datos en las ${texto}`);
    return;
  }
  const valores = puntos.map((p) => p.y);
  const unidad = variable.unidad ? ` ${variable.unidad}` : "";
  const textoResumen = `Último: ${valores.at(-1)}${unidad} · Mínimo: ${Math.min(...valores)}${unidad} · Máximo: ${Math.max(...valores)}${unidad} (${texto}, promedios de ${intervalo})`;
  resumen.textContent = textoResumen;
  lienzo.setAttribute("aria-label", `Gráfica de ${variable.nombre}. ${textoResumen}`);
}

async function actualizarGraficas() {
  try {
    await Promise.all(variables.map(actualizarGrafica));
  } catch (fallo) {
    avisar(aviso, `${fallo.message} Las gráficas pueden estar desactualizadas.`);
  }
}

function elegirRango(evento) {
  const boton = evento.target.closest("[data-rango]");
  if (!boton) return;
  rango = boton.dataset.rango;
  for (const otro of document.querySelectorAll("[data-rango]")) otro.setAttribute("aria-pressed", String(otro === boton));
  actualizarGraficas();
}

async function iniciar() {
  if (!id || !/^\d+$/.test(id)) {
    carga.textContent = "Falta indicar el tanque.";
    return;
  }
  try {
    const pagina = await iniciarPagina();
    fecha = pagina.fecha;
    zonaHoraria = pagina.yo.zona_horaria;
    const tanque = (await pedir("/api/v1/tanques")).find((t) => String(t.id) === id);
    if (!tanque) {
      carga.textContent = "No existe ese tanque.";
      return;
    }
    document.title = `${tanque.nombre} · AquaSense`;
    document.getElementById("titulo").textContent = tanque.nombre;
    document.getElementById("insignia").replaceChildren(insignia(...ESTADOS[tanque.estado]));
    const listaUmbrales = await pedir(`/api/v1/tanques/${id}/umbrales`);
    umbrales = Object.fromEntries(listaUmbrales.map((u) => [u.variable, u]));
    variables = tanque.lecturas.filter((l) => l.tipo === "numero");
    document.getElementById("sin-graficas").hidden = variables.length > 0;
    document.getElementById("graficas").replaceChildren(...variables.map(crearTarjetaGrafica));

    carga.hidden = true;
    ocultar(aviso);
    document.getElementById("contenido").hidden = false;
    document.querySelector('[role="group"]').addEventListener("click", elegirRango);
    document.getElementById("form-cambio").addEventListener("submit", registrarCambio);
    await Promise.all([cargarPrediccion(), cargarCambios()]);
    await repetirMientrasVisible(actualizarGraficas, pagina.yo.polling_graficas_s * MS_POR_SEGUNDO).iniciar();
  } catch (fallo) {
    carga.textContent = "No se pudo cargar el detalle del tanque.";
    avisar(aviso, fallo.message);
  }
}

iniciar();
