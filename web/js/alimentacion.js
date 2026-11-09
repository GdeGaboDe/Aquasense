import { pedir } from "/js/api.js";
import {
  MS_POR_SEGUNDO,
  avisar,
  campoParametro,
  crear,
  iniciarPagina,
  leerParametros,
  llenarSelectorTanques,
  ocultar,
  repetirMientrasVisible,
} from "/js/comun.js";

const PARAMETROS_PROGRAMA = ["MODO_DISPENSA", "INTERVALO_ALIMENTACION_HORAS", "CANTIDAD_CARGAS"];
const EN_CURSO = new Set(["pendiente", "entregado"]);
const TEXTO_ESTADO = {
  pendiente: "Enviando al alimentador…",
  entregado: "El alimentador recibió la orden; esperando confirmación…",
  confirmado: "Listo: alimentación confirmada.",
  fallido: "El alimentador reportó una falla.",
  expirado: "No se pudo entregar la orden a tiempo. Revisa la conexión del nodo.",
  sin_confirmar: "Sin confirmar: el nodo no respondió. No se reintenta para evitar doble ración.",
};
const TEXTO_ORIGEN = { remoto: "Desde la web", automatico: "Automática", local: "Botón del nodo" };

const selector = document.getElementById("tanque");
const carga = document.getElementById("estado-carga");
const aviso = document.getElementById("aviso");
const estadoComando = document.getElementById("estado-comando");
const botonDispensar = document.getElementById("dispensar");
const formPrograma = document.getElementById("form-programa");
const avisoPrograma = document.getElementById("aviso-programa");

let tanques = [];
let parametrosPrograma = [];
let fecha = null;
let intervaloComandoMs = 3000;
let seguimiento = null;
let comandoEnSeguimiento = null;

const tanqueActual = () => tanques.find((t) => String(t.id) === selector.value);

function mostrarTolva(tanque) {
  const lecturas = Object.fromEntries(tanque.lecturas.map((l) => [l.variable, l]));
  const texto = document.getElementById("tolva");
  if (!lecturas.tolva_vacia && !lecturas.distancia_tolva_cm) {
    texto.textContent = "Este nodo no reporta el nivel de la tolva.";
    return;
  }
  const vacia = lecturas.tolva_vacia?.valor === 1;
  const distancia = lecturas.distancia_tolva_cm ? ` (${lecturas.distancia_tolva_cm.valor} cm al alimento)` : "";
  texto.textContent = `Tolva: ${vacia ? "⚠ vacía, recárgala" : "con alimento"}${distancia}`;
}

async function cargarBitacora(tanque) {
  const datos = await pedir(`/api/v1/tanques/${tanque.id}/dosis?tamano=10`);
  document.getElementById("bitacora-vacia").hidden = datos.total > 0;
  document.getElementById("bitacora").replaceChildren(
    ...datos.elementos.map((dosis) => {
      const fila = crear("li", "flex flex-wrap justify-between gap-2 py-2");
      const cargas = `${dosis.cargas} ${dosis.cargas === 1 ? "carga" : "cargas"}`;
      fila.append(crear("span", "font-medium", `${cargas} · ${TEXTO_ORIGEN[dosis.origen]}`), crear("span", "text-slate-700", fecha(dosis.dosificada_en)));
      return fila;
    }),
  );
}

async function cargarPrograma(tanque) {
  const datos = await pedir(`/api/v1/nodos/${tanque.nodo.id}/parametros`);
  parametrosPrograma = datos.parametros.filter((p) => PARAMETROS_PROGRAMA.includes(p.codigo));
  document.getElementById("campos-programa").replaceChildren(...parametrosPrograma.map(campoParametro));
}

async function mostrarTanque() {
  const tanque = tanqueActual();
  if (!tanque) return;
  detenerSeguimiento();
  estadoComando.textContent = "";
  ocultar(avisoPrograma);
  mostrarTolva(tanque);
  try {
    await Promise.all([cargarBitacora(tanque), cargarPrograma(tanque)]);
    ocultar(aviso);
  } catch (fallo) {
    avisar(aviso, fallo.message);
  }
}

function detenerSeguimiento() {
  clearTimeout(seguimiento);
  seguimiento = null;
  comandoEnSeguimiento = null;
  botonDispensar.disabled = false;
}

async function seguirComando(comandoId) {
  comandoEnSeguimiento = comandoId;
  const tanque = tanqueActual();
  try {
    const datos = await pedir(`/api/v1/comandos?nodo_id=${tanque.nodo.id}&tamano=5`);
    const comando = datos.elementos.find((c) => c.id === comandoId);
    if (!comando) return detenerSeguimiento();
    estadoComando.textContent = TEXTO_ESTADO[comando.estado];
    if (!EN_CURSO.has(comando.estado)) {
      detenerSeguimiento();
      return;
    }
  } catch (fallo) {
    estadoComando.textContent = fallo.message;
  }
  // El seguimiento cada pocos segundos solo corre con la pestaña visible.
  if (document.visibilityState === "visible") {
    seguimiento = setTimeout(() => seguirComando(comandoId), intervaloComandoMs);
  }
}

async function dispensar(evento) {
  evento.preventDefault();
  const tanque = tanqueActual();
  botonDispensar.disabled = true;
  try {
    const comando = await pedir("/api/v1/comandos", {
      metodo: "POST",
      cuerpo: { nodo_id: tanque.nodo.id, tipo: "DISPENSAR", argumento: Number(document.getElementById("cargas").value) },
    });
    estadoComando.textContent = TEXTO_ESTADO[comando.estado];
    comandoEnSeguimiento = comando.id;
    seguimiento = setTimeout(() => seguirComando(comando.id), intervaloComandoMs);
  } catch (fallo) {
    estadoComando.textContent = fallo.message;
    botonDispensar.disabled = false;
  }
}

async function guardarPrograma(evento) {
  evento.preventDefault();
  if (!formPrograma.reportValidity()) return;
  try {
    await pedir(`/api/v1/nodos/${tanqueActual().nodo.id}/parametros`, {
      metodo: "PUT",
      cuerpo: { valores: leerParametros(formPrograma, parametrosPrograma) },
    });
    avisar(avisoPrograma, "Guardado. El nodo lo aplicará en su próxima consulta.", "exito");
  } catch (fallo) {
    avisar(avisoPrograma, fallo.message, "error", fallo.detalles);
  }
}

document.addEventListener("visibilitychange", () => {
  clearTimeout(seguimiento);
  // Al volver a la pestaña se retoma el seguimiento del comando que quedó en curso.
  if (document.visibilityState === "visible" && comandoEnSeguimiento !== null) {
    seguimiento = setTimeout(() => seguirComando(comandoEnSeguimiento), intervaloComandoMs);
  }
});

/** La dosis y el nivel de la tolva llegan con la telemetría: se refrescan al ritmo del panel. */
async function refrescarEstado() {
  const seleccionado = selector.value;
  try {
    tanques = (await pedir("/api/v1/tanques")).filter((t) => t.nodo?.modulos.includes("servo"));
    const tanque = tanques.find((t) => String(t.id) === seleccionado);
    if (!tanque) return;
    mostrarTolva(tanque);
    await cargarBitacora(tanque);
  } catch {
    // El siguiente ciclo lo reintenta; un fallo pasajero no debe tapar el estado del comando.
  }
}

async function iniciar() {
  try {
    const pagina = await iniciarPagina();
    fecha = pagina.fecha;
    intervaloComandoMs = pagina.yo.polling_comando_s * MS_POR_SEGUNDO;
    tanques = await llenarSelectorTanques(selector, (t) => t.nodo?.modulos.includes("servo"));
    carga.hidden = true;
    if (tanques.length === 0) {
      document.getElementById("sin-servo").hidden = false;
      return;
    }
    document.getElementById("contenido").hidden = false;
    selector.addEventListener("change", mostrarTanque);
    document.getElementById("form-dispensar").addEventListener("submit", dispensar);
    formPrograma.addEventListener("submit", guardarPrograma);
    await mostrarTanque();
    const intervaloPanelMs = pagina.yo.polling_panel_s * MS_POR_SEGUNDO;
    setTimeout(repetirMientrasVisible(refrescarEstado, intervaloPanelMs).iniciar, intervaloPanelMs);
  } catch (fallo) {
    carga.textContent = "No se pudo cargar la página.";
    avisar(aviso, fallo.message);
  }
}

iniciar();
