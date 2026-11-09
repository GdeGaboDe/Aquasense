import { pedir } from "/js/api.js";
import { avisar, campoParametro, crear, iniciarPagina, leerParametros, llenarSelectorTanques, ocultar } from "/js/comun.js";

const CAMPO = "w-full rounded border border-slate-500 p-2 text-base";

const selector = document.getElementById("tanque");
const carga = document.getElementById("estado-carga");
const aviso = document.getElementById("aviso");
const formUmbrales = document.getElementById("form-umbrales");
const formParametros = document.getElementById("form-parametros");

let tanques = [];
let umbrales = [];
let parametros = [];

const tanqueActual = () => tanques.find((t) => String(t.id) === selector.value);

function campoNumero(id, texto, valor, atributos = {}) {
  const caja = crear("div");
  const etiqueta = crear("label", "mb-1 block text-sm font-medium", texto);
  etiqueta.htmlFor = id;
  const control = Object.assign(crear("input", CAMPO), { id, type: "number", step: "any", ...atributos });
  control.value = valor === null || valor === undefined ? "" : String(valor);
  caja.append(etiqueta, control);
  return caja;
}

function filaUmbral(umbral) {
  const grupo = crear("fieldset", "rounded border border-slate-300 p-3");
  const unidad = umbral.unidad ? ` (${umbral.unidad})` : "";
  grupo.append(crear("legend", "px-1 font-semibold", `${umbral.nombre}${unidad}`));
  const limites = { min: umbral.min_fisico ?? "", max: umbral.max_fisico ?? "" };
  const campos = crear("div", "grid grid-cols-3 gap-2");
  campos.append(
    campoNumero(`min-${umbral.variable}`, "Mínimo", umbral.minimo, limites),
    campoNumero(`max-${umbral.variable}`, "Máximo", umbral.maximo, limites),
    campoNumero(`his-${umbral.variable}`, "Histéresis", umbral.histeresis, { min: "0" }),
  );
  grupo.append(campos);
  return grupo;
}

async function cargarUmbrales(tanque) {
  umbrales = await pedir(`/api/v1/tanques/${tanque.id}/umbrales`);
  document.getElementById("sin-umbrales").hidden = umbrales.length > 0;
  document.getElementById("guardar-umbrales").hidden = umbrales.length === 0;
  document.getElementById("campos-umbrales").replaceChildren(...umbrales.map(filaUmbral));
}

function leerNumero(id) {
  const texto = document.getElementById(id).value.trim();
  return texto === "" ? null : Number(texto);
}

async function guardarUmbrales(evento) {
  evento.preventDefault();
  const avisoUmbrales = document.getElementById("aviso-umbrales");
  if (!formUmbrales.reportValidity()) return;
  const cuerpo = umbrales.map((u) => ({
    variable: u.variable,
    minimo: leerNumero(`min-${u.variable}`),
    maximo: leerNumero(`max-${u.variable}`),
    histeresis: leerNumero(`his-${u.variable}`) ?? 0,
  }));
  try {
    umbrales = await pedir(`/api/v1/tanques/${tanqueActual().id}/umbrales`, { metodo: "PUT", cuerpo: { umbrales: cuerpo } });
    avisar(avisoUmbrales, "Umbrales guardados.", "exito");
  } catch (fallo) {
    avisar(avisoUmbrales, fallo.message, "error", fallo.detalles);
  }
}

function mostrarPendiente(datos) {
  const caja = document.getElementById("pendiente");
  caja.hidden = !datos.pendiente_de_aplicar;
  const aplicada = datos.config_version_aplicada ?? "ninguna";
  caja.textContent = `⏳ Pendiente de aplicar: el nodo tiene la versión ${aplicada} y la vigente es la ${datos.config_version}.`;
}

async function cargarParametros(tanque) {
  const datos = await pedir(`/api/v1/nodos/${tanque.nodo.id}/parametros`);
  parametros = datos.parametros;
  mostrarPendiente(datos);
  document.getElementById("campos-parametros").replaceChildren(...parametros.map(campoParametro));
}

async function guardarParametros(evento) {
  evento.preventDefault();
  const avisoParametros = document.getElementById("aviso-parametros");
  if (!formParametros.reportValidity()) return;
  try {
    const datos = await pedir(`/api/v1/nodos/${tanqueActual().nodo.id}/parametros`, {
      metodo: "PUT",
      cuerpo: { valores: leerParametros(formParametros, parametros) },
    });
    mostrarPendiente(datos);
    avisar(avisoParametros, "Parámetros guardados.", "exito");
  } catch (fallo) {
    avisar(avisoParametros, fallo.message, "error", fallo.detalles);
  }
}

async function enviarComando(tipo, argumento) {
  const avisoControl = document.getElementById("aviso-control");
  try {
    await pedir("/api/v1/comandos", { metodo: "POST", cuerpo: { nodo_id: tanqueActual().nodo.id, tipo, argumento } });
    avisar(avisoControl, "Orden enviada. El nodo la recibirá en su próxima consulta.", "exito");
  } catch (fallo) {
    avisar(avisoControl, fallo.message);
  }
}

function mostrarControl(tanque) {
  const modulos = tanque.nodo?.modulos ?? [];
  document.getElementById("form-silenciar").hidden = !modulos.includes("alarma");
  document.getElementById("control-aireador").hidden = !modulos.includes("aireador");
  document.getElementById("seccion-control").hidden = !(modulos.includes("alarma") || modulos.includes("aireador"));
  ocultar(document.getElementById("aviso-control"));
}

async function mostrarTanque() {
  const tanque = tanqueActual();
  if (!tanque) return;
  for (const id of ["aviso-umbrales", "aviso-parametros"]) ocultar(document.getElementById(id));
  document.getElementById("seccion-parametros").hidden = !tanque.nodo;
  mostrarControl(tanque);
  try {
    await Promise.all([cargarUmbrales(tanque), tanque.nodo ? cargarParametros(tanque) : null]);
    ocultar(aviso);
  } catch (fallo) {
    avisar(aviso, fallo.message);
  }
}

async function refrescarTanques() {
  tanques = await llenarSelectorTanques(selector);
  document.getElementById("con-tanques").hidden = tanques.length === 0;
  const sinNodo = document.getElementById("nodo-tanque");
  sinNodo.replaceChildren(
    ...tanques.filter((t) => !t.nodo).map((t) => Object.assign(crear("option", "", t.nombre), { value: String(t.id) })),
  );
  const padre = document.getElementById("nodo-padre");
  padre.replaceChildren(
    Object.assign(crear("option", "", "Autónomo (habla con el servidor)"), { value: "" }),
    ...tanques
      .filter((t) => t.nodo && !t.nodo.es_satelite)
      .map((t) => Object.assign(crear("option", "", `Satélite de ${t.nodo.nombre} (${t.nombre})`), { value: String(t.nodo.id) })),
  );
}

async function crearTanque(evento) {
  evento.preventDefault();
  const formulario = evento.target;
  const avisoTanque = document.getElementById("aviso-tanque");
  if (!formulario.reportValidity()) return;
  const datos = Object.fromEntries(new FormData(formulario));
  try {
    await pedir("/api/v1/tanques", {
      metodo: "POST",
      cuerpo: { nombre: datos.nombre, volumen_l: Number(datos.volumen_l), especie: datos.especie || null },
    });
    formulario.reset();
    avisar(avisoTanque, `Tanque ${datos.nombre} creado; se registró su llenado como primer cambio de agua.`, "exito");
    await refrescarTanques();
    await mostrarTanque();
  } catch (fallo) {
    avisar(avisoTanque, fallo.message, "error", fallo.detalles);
  }
}

async function crearNodo(evento) {
  evento.preventDefault();
  const formulario = evento.target;
  const avisoNodo = document.getElementById("aviso-nodo");
  const cajaToken = document.getElementById("token");
  cajaToken.hidden = true;
  if (!formulario.reportValidity()) return;
  const datos = Object.fromEntries(new FormData(formulario));
  try {
    const nodo = await pedir("/api/v1/nodos", {
      metodo: "POST",
      cuerpo: {
        mac: datos.mac,
        nombre: datos.nombre,
        tanque_id: Number(datos.tanque_id),
        padre_id: datos.padre_id ? Number(datos.padre_id) : null,
      },
    });
    formulario.reset();
    avisar(avisoNodo, `Nodo ${nodo.nombre} creado.`, "exito");
    if (nodo.token) {
      document.getElementById("token-valor").value = nodo.token;
      cajaToken.hidden = false;
      document.getElementById("token-valor").select();
    }
    await refrescarTanques();
  } catch (fallo) {
    avisar(avisoNodo, fallo.message, "error", fallo.detalles);
  }
}

async function iniciar() {
  try {
    await iniciarPagina();
    await refrescarTanques();
    carga.hidden = true;
    selector.addEventListener("change", mostrarTanque);
    formUmbrales.addEventListener("submit", guardarUmbrales);
    formParametros.addEventListener("submit", guardarParametros);
    document.getElementById("form-silenciar").addEventListener("submit", (e) => {
      e.preventDefault();
      enviarComando("SILENCIAR_ALARMA", Number(document.getElementById("minutos").value));
    });
    document.getElementById("aireador-on").addEventListener("click", () => enviarComando("AIREADOR", 1));
    document.getElementById("aireador-off").addEventListener("click", () => enviarComando("AIREADOR", 0));
    document.getElementById("form-tanque").addEventListener("submit", crearTanque);
    document.getElementById("form-nodo").addEventListener("submit", crearNodo);
    if (tanques.length > 0) await mostrarTanque();
  } catch (fallo) {
    carga.textContent = "No se pudo cargar la página.";
    avisar(aviso, fallo.message);
  }
}

iniciar();
