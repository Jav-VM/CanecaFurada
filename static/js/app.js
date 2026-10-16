/*
 * Mejoras progresivas de la interfaz. Sin JavaScript todo funciona igual:
 * el menú se muestra desplegado y los formularios se envían con normalidad.
 * Aquí no hay reglas de negocio ni validaciones: las aplica el servidor.
 */
(function () {
  "use strict";
  var root = document.documentElement;
  root.classList.remove("no-js");
  root.classList.add("js");

  // Menú principal plegable en pantallas pequeñas.
  var toggle = document.querySelector("[data-nav-toggle]");
  var panel = toggle && document.getElementById(toggle.getAttribute("aria-controls"));
  if (toggle && panel) {
    toggle.addEventListener("click", function () {
      var open = toggle.getAttribute("aria-expanded") !== "true";
      toggle.setAttribute("aria-expanded", String(open));
      panel.classList.toggle("is-open", open);
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
        toggle.click();
        toggle.focus();
      }
    });
  }

  // Estado de carga: evita el doble envío y avisa de que la petición está en curso.
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form.matches("form[data-loading]")) return;
    if (form.dataset.submitting === "true") {
      event.preventDefault();
      return;
    }
    form.dataset.submitting = "true";
    form.setAttribute("aria-busy", "true");
    var button = form.querySelector("[type=submit]");
    if (button) {
      button.dataset.originalText = button.textContent;
      button.textContent = button.dataset.loadingText || document.body.dataset.sendingText || "Enviando…";
      button.setAttribute("aria-busy", "true");
      button.disabled = true;
    }
  });

  // Al volver con el botón "atrás" el navegador puede restaurar la página en ese estado.
  window.addEventListener("pageshow", function () {
    document.querySelectorAll("form[data-submitting]").forEach(function (form) {
      delete form.dataset.submitting;
      form.removeAttribute("aria-busy");
      var button = form.querySelector("[type=submit][aria-busy]");
      if (button) {
        button.textContent = button.dataset.originalText;
        button.removeAttribute("aria-busy");
        button.disabled = false;
      }
    });
  });

  // Lleva el foco al resumen de errores para que se anuncie y se vea.
  var summary = document.querySelector("[data-error-summary]");
  if (summary) summary.focus();
})();
