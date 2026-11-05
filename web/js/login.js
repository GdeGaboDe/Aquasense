import { pedir } from "/js/api.js";

const formulario = document.getElementById("formulario");
const usuario = document.getElementById("usuario");
const contrasena = document.getElementById("contrasena");
const error = document.getElementById("error");
const entrar = document.getElementById("entrar");
const botonVer = document.getElementById("ver-contrasena");

function verContrasena(visible) {
  contrasena.type = visible ? "text" : "password";
  botonVer.textContent = visible ? "Ocultar" : "Mostrar";
  botonVer.setAttribute("aria-pressed", String(visible));
}

function mostrarError(mensaje) {
  error.textContent = mensaje;
  error.classList.remove("hidden");
}

async function iniciarSesion(evento) {
  evento.preventDefault();
  error.classList.add("hidden");
  if (!usuario.value.trim() || !contrasena.value) {
    mostrarError("Escribe tu usuario y tu contraseña.");
    return;
  }

  // Se oculta al enviar para que no quede a la vista mientras se abre el panel o tras un error.
  verContrasena(false);
  entrar.disabled = true;
  entrar.textContent = "Entrando…";
  try {
    await pedir("/api/v1/auth/login", {
      metodo: "POST",
      cuerpo: { usuario: usuario.value.trim(), contrasena: contrasena.value },
      sinRedirigir: true,
    });
    window.location.assign("/");
  } catch (fallo) {
    contrasena.value = "";
    contrasena.focus();
    mostrarError(fallo.message);
    entrar.disabled = false;
    entrar.textContent = "Entrar";
  }
}

botonVer.addEventListener("click", () => verContrasena(contrasena.type === "password"));
formulario.addEventListener("submit", iniciarSesion);
usuario.focus();
