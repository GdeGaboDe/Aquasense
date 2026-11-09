// Único envoltorio de fetch: interpreta el formato de error y redirige al login con 401.

const LOGIN = "/login.html";

export class ErrorApi extends Error {
  constructor(codigo, mensaje, estadoHttp, detalles = null) {
    super(mensaje);
    this.codigo = codigo;
    this.estadoHttp = estadoHttp;
    this.detalles = detalles;
  }
}

async function leerError(respuesta) {
  try {
    const { error } = await respuesta.json();
    return new ErrorApi(error.code, error.message, respuesta.status, error.details);
  } catch {
    return new ErrorApi("ERROR_DESCONOCIDO", "El servidor respondió con un error.", respuesta.status);
  }
}

/**
 * Hace una petición a la API con una ruta relativa.
 * @param {string} ruta p. ej. "/api/v1/tanques"
 * @param {{metodo?: string, cuerpo?: object, sinRedirigir?: boolean}} [opciones]
 * @returns {Promise<any>} el JSON de la respuesta, o null si no trae cuerpo.
 * @throws {ErrorApi}
 */
export async function pedir(ruta, { metodo = "GET", cuerpo, sinRedirigir = false } = {}) {
  let respuesta;
  try {
    respuesta = await fetch(ruta, {
      method: metodo,
      credentials: "same-origin",
      headers: cuerpo ? { "Content-Type": "application/json" } : {},
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
    });
  } catch {
    throw new ErrorApi("SIN_RED", "No se pudo contactar al servidor. Revisa tu conexión.", 0);
  }

  if (respuesta.status === 401 && !sinRedirigir) {
    window.location.assign(LOGIN);
  }
  if (!respuesta.ok) {
    throw await leerError(respuesta);
  }
  return respuesta.status === 204 ? null : respuesta.json();
}
