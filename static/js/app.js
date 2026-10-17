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

  // Aviso inmediato de edad mínima al elegir la fecha de nacimiento. Solo informa:
  // el servidor vuelve a comprobarlo al enviar (misma regla que validators.age_on).
  document.querySelectorAll("input[data-min-age]").forEach(function (input) {
    var notice = input.closest(".field") && input.closest(".field").querySelector("[data-min-age-notice]");
    if (!notice) return;
    function check() {
      var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(input.value);
      var underAge = false;
      if (match) {
        var today = new Date();
        var year = +match[1], month = +match[2], day = +match[3];
        var age = today.getFullYear() - year;
        if (today.getMonth() + 1 < month || (today.getMonth() + 1 === month && today.getDate() < day)) age -= 1;
        underAge = age >= 0 && age < Number(input.dataset.minAge);
      }
      notice.textContent = underAge ? input.dataset.minAgeMessage : "";
    }
    input.addEventListener("change", check);
    input.addEventListener("input", check);
  });

  // Clientes → columna «Envío» (Fase 19): casilla general de la página, contador y
  // barra con el botón «Comunicaciones», que aparece al marcar alguno. Sin JS la barra
  // se ve siempre; el servidor recalcula y valida la selección.
  var bar = document.querySelector("[data-selection-bar]");
  if (bar) {
    var items = Array.prototype.slice.call(document.querySelectorAll("[data-select-item]"));
    var all = document.querySelector("[data-select-all]");
    var counter = bar.querySelector("[data-selection-count]");
    var refresh = function () {
      var checked = items.filter(function (item) { return item.checked; }).length;
      counter.textContent = String(checked);
      bar.hidden = checked === 0;
      if (all) {
        all.checked = checked > 0 && checked === items.length;
        all.indeterminate = checked > 0 && checked < items.length;
      }
    };
    items.forEach(function (item) { item.addEventListener("change", refresh); });
    if (all) {
      all.addEventListener("change", function () {
        items.forEach(function (item) { item.checked = all.checked; });
        refresh();
      });
    }
    refresh();
  }

  // Botones que necesitan campos rellenos («Crear y enviar»): se activan cuando todos
  // tienen texto. Solo es una ayuda: el servidor valida igual.
  document.querySelectorAll("[data-requires]").forEach(function (button) {
    var form = button.form;
    var fields = button.dataset.requires.split(" ").map(function (name) { return form.elements[name]; }).filter(Boolean);
    var update = function () {
      button.disabled = fields.some(function (field) { return !String(field.value).trim(); });
    };
    fields.forEach(function (field) { field.addEventListener("input", update); });
    update();
  });

  // Localidad según el código postal (España): desplegable con las del CP,
  // marcada sola si solo hay una; sin datos, texto libre. Sin JS el servidor
  // valida igual y pinta el desplegable tras un envío con errores.
  document.querySelectorAll("[data-locality-for]").forEach(function (initial) {
    var form = initial.form;
    var postal = form && form.elements[initial.dataset.localityFor];
    var country = form && form.elements.country;
    if (!postal) return;
    var current = initial;
    var lastQuery = null;
    var timer = null;

    function replaceWith(tag) {
      if (current.tagName.toLowerCase() === tag) return current;
      var next = document.createElement(tag);
      ["id", "name", "class", "autocomplete", "aria-describedby", "aria-invalid"].forEach(function (attr) {
        if (current.hasAttribute(attr)) next.setAttribute(attr, current.getAttribute(attr));
      });
      Object.keys(current.dataset).forEach(function (key) { next.dataset[key] = current.dataset[key]; });
      if (tag === "input") { next.type = "text"; next.maxLength = 100; }
      current.replaceWith(next);
      current = next;
      return next;
    }

    function show(localities) {
      if (!localities.length) {
        var keep = current.tagName === "INPUT" ? current.value : "";
        replaceWith("input").value = keep;
        return;
      }
      var previous = current.value;
      var select = replaceWith("select");
      select.innerHTML = "";
      if (localities.length > 1) {
        var empty = document.createElement("option");
        empty.value = "";
        empty.textContent = select.dataset.chooseText || "";
        select.appendChild(empty);
      }
      localities.forEach(function (name) {
        var option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        if (localities.length === 1 || name.toLowerCase() === String(previous).toLowerCase()) option.selected = true;
        select.appendChild(option);
      });
    }

    function lookup() {
      var code = postal.value.replace(/\s+/g, "");
      var spain = !country || country.value === "ES";
      if (!spain || !/^\d{5}$/.test(code)) {
        lastQuery = null;
        show([]);
        return;
      }
      if (code === lastQuery) return;
      lastQuery = code;
      fetch(initial.dataset.localitiesUrl + "?cp=" + encodeURIComponent(code), { headers: { Accept: "application/json" } })
        .then(function (response) { return response.ok ? response.json() : { localities: [] }; })
        .then(function (data) { if (lastQuery === code) show(data.localities || []); })
        .catch(function () { if (lastQuery === code) show([]); });
    }

    postal.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(lookup, 250); });
    if (country) country.addEventListener("change", lookup);
    if (postal.value) lookup();
  });
})();
