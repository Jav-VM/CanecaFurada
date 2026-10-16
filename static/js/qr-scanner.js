/*
 * Lector de QR del panel del personal (mejora progresiva).
 *
 * Usa el lector nativo del navegador (BarcodeDetector) si existe y, si no,
 * jsQR servido desde este mismo sitio (static/vendor/jsqr). Cuando lee un
 * código, lo copia en el campo del formulario y lo envía: la validación la
 * hace siempre el servidor. Sin cámara o sin JavaScript se teclea el código.
 * El código leído no se guarda ni se envía a ningún otro sitio.
 */
(function () {
  "use strict";
  var root = document.querySelector("[data-qr-scanner]");
  if (!root) return;
  var form = document.getElementById(root.getAttribute("data-form"));
  var input = form && form.querySelector("[name=code]");
  if (!input || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;

  var video = root.querySelector("[data-qr-video]");
  var startButton = root.querySelector("[data-qr-start]");
  var stopButton = root.querySelector("[data-qr-stop]");
  var status = root.querySelector("[data-qr-status]");
  var stream = null;
  var detect = null;
  var timer = null;
  var canvas = document.createElement("canvas");
  var context = canvas.getContext("2d", { willReadFrequently: true });

  root.hidden = false;

  function say(text) {
    status.textContent = text;
  }

  function stop() {
    if (timer) window.clearTimeout(timer);
    timer = null;
    if (stream) stream.getTracks().forEach(function (track) { track.stop(); });
    stream = null;
    video.hidden = true;
    stopButton.hidden = true;
    startButton.hidden = false;
  }

  function found(text) {
    stop();
    input.value = text;
    say(root.dataset.textRead || "Código leído. Comprobando…");
    if (form.requestSubmit) form.requestSubmit(); else form.submit();
  }

  function nativeDetector() {
    var detector = new window.BarcodeDetector({ formats: ["qr_code"] });
    return function () {
      return detector.detect(video).then(function (codes) {
        return codes.length ? codes[0].rawValue : null;
      });
    };
  }

  function jsqrDetector() {
    return function () {
      var width = video.videoWidth;
      var height = video.videoHeight;
      if (!width || !height) return Promise.resolve(null);
      canvas.width = width;
      canvas.height = height;
      context.drawImage(video, 0, 0, width, height);
      var result = window.jsQR(context.getImageData(0, 0, width, height).data, width, height, {
        inversionAttempts: "dontInvert"
      });
      return Promise.resolve(result ? result.data : null);
    };
  }

  function loadJsqr() {
    if (window.jsQR) return Promise.resolve();
    return new Promise(function (resolve, reject) {
      var script = document.createElement("script");
      script.src = root.getAttribute("data-jsqr-src");
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  function chooseDetector() {
    if (detect) return Promise.resolve(detect);
    var nativeCheck = "BarcodeDetector" in window
      ? window.BarcodeDetector.getSupportedFormats().catch(function () { return []; })
      : Promise.resolve([]);
    return nativeCheck.then(function (formats) {
      if (formats.indexOf("qr_code") !== -1) return nativeDetector();
      return loadJsqr().then(jsqrDetector);
    }).then(function (fn) {
      detect = fn;
      return fn;
    });
  }

  function scanLoop() {
    if (!stream) return;
    detect().then(function (text) {
      if (text) found(text);
      else timer = window.setTimeout(scanLoop, 250);
    }).catch(function () {
      timer = window.setTimeout(scanLoop, 500);
    });
  }

  startButton.addEventListener("click", function () {
    say(root.dataset.textOpening || "Abriendo la cámara…");
    chooseDetector().then(function () {
      return navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
    }).then(function (mediaStream) {
      stream = mediaStream;
      video.srcObject = stream;
      video.hidden = false;
      startButton.hidden = true;
      stopButton.hidden = false;
      return video.play();
    }).then(function () {
      say(root.dataset.textAim || "Apunta la cámara al QR del cliente.");
      scanLoop();
    }).catch(function () {
      stop();
      say(root.dataset.textError || "No se ha podido usar la cámara. Revisa el permiso del navegador o escribe el código.");
    });
  });

  stopButton.addEventListener("click", function () {
    stop();
    say("");
  });

  window.addEventListener("pagehide", stop);
})();
