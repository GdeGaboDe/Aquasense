import { pedir } from "/js/api.js";
import { avisar, crear, formatearValor, iniciarPagina, insigniaSeveridad, llenarSelectorTanques, ocultar } from "/js/comun.js";

const TAMANO = 20;
const estado = document.getElementById("estado");
const tanque = document.getElementById("tanque");
const lista = document.getElementById("lista");
const carga = document.getElementById("estado-carga");
const aviso = document.getElementById("aviso");
const anterior = document.getElementById("anterior");
const siguiente = document.getElementById("siguiente");
const textoPagina = document.getElementById("pagina");

let pagina = 1;
let fecha = null;

function crearAlerta(alerta) {
  const elemento = crear("li", "rounded-lg bg-white p-4 shadow");
  const encabezado = crear("div", "mb-1 flex flex-wrap items-center gap-2");
  encabezado.append(insigniaSeveridad(alerta.severidad), crear("h2", "font-bold", alerta.descripcion));
  const detalle = alerta.variable_nombre
    ? `${alerta.tanque} · ${alerta.variable_nombre}: ${formatearValor(alerta.valor, alerta.unidad)}`
    : alerta.tanque;
  const tiempo = alerta.activa
    ? `Activa desde ${fecha(alerta.iniciada_en)}`
    : `Del ${fecha(alerta.iniciada_en)} al ${fecha(alerta.resuelta_en)}`;
  elemento.append(encabezado, crear("p", "text-slate-800", detalle), crear("p", "text-sm text-slate-700", tiempo));
  return elemento;
}

async function cargar() {
  const parametros = new URLSearchParams({ pagina: String(pagina), tamano: String(TAMANO) });
  if (estado.value) parametros.set("activa", estado.value);
  if (tanque.value) parametros.set("tanque_id", tanque.value);
  carga.textContent = "Cargando alertas…";
  try {
    const datos = await pedir(`/api/v1/alertas?${parametros}`);
    ocultar(aviso);
    lista.replaceChildren(...datos.elementos.map(crearAlerta));
    const paginas = Math.max(1, Math.ceil(datos.total / TAMANO));
    carga.textContent = datos.total === 0 ? "No hay alertas con estos filtros." : `${datos.total} alertas`;
    textoPagina.textContent = `Página ${pagina} de ${paginas}`;
    anterior.disabled = pagina <= 1;
    siguiente.disabled = pagina >= paginas;
  } catch (fallo) {
    avisar(aviso, fallo.message);
    carga.textContent = "No se pudieron cargar las alertas.";
  }
}

function filtrar() {
  pagina = 1;
  cargar();
}

async function iniciar() {
  try {
    ({ fecha } = await iniciarPagina());
    const tanques = await llenarSelectorTanques(tanque);
    tanque.prepend(Object.assign(crear("option", "", "Todos"), { value: "" }));
    tanque.value = "";
    if (tanques.length === 0) tanque.disabled = true;
    estado.addEventListener("change", filtrar);
    tanque.addEventListener("change", filtrar);
    anterior.addEventListener("click", () => { pagina -= 1; cargar(); });
    siguiente.addEventListener("click", () => { pagina += 1; cargar(); });
    await cargar();
  } catch (fallo) {
    avisar(aviso, fallo.message);
    carga.textContent = "No se pudo cargar la página.";
  }
}

iniciar();
