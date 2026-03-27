(function () {
  "use strict";

  var SNACK_FADE_MS = 360;

  function showSnackbar(message) {
    var bar = document.getElementById("snackbar");
    if (!bar) return;
    clearTimeout(bar._flashHideTimer);
    clearTimeout(bar._hideTimer);
    bar.textContent = message;
    bar.className = "snackbar";
    bar.hidden = false;
    bar.setAttribute("aria-hidden", "false");
    requestAnimationFrame(function () {
      bar.classList.add("snackbar--visible");
    });
    bar._hideTimer = setTimeout(function () {
      bar.classList.remove("snackbar--visible");
      bar.setAttribute("aria-hidden", "true");
      setTimeout(function () {
        bar.hidden = true;
        bar.className = "snackbar";
      }, SNACK_FADE_MS);
    }, 1000);
  }

  document.querySelectorAll("[data-snackbar-trigger]").forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      var msg = btn.getAttribute("data-snackbar-message") || "future feature";
      showSnackbar(msg);
    });
  });
})();
