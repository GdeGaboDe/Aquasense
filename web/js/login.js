import { pedir } from "/js/api.js";

const formulario = document.getElementById("formulario");
const usuario = document.getElementById("usuario");
const contrasena = document.getElementById("contrasena");
const error = document.getElementById("error");
const entrar = document.getElementById("entrar");

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

formulario.addEventListener("submit", iniciarSesion);
usuario.focus();
