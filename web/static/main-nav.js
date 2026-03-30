(function () {
  "use strict";

  var SNACK_FADE_MS = 360;
  var SNACK_SHOW_MS = 3500;

  function showSnackbar(message) {
    var bar = document.getElementById("snackbar");
    if (!bar) return;
    clearTimeout(bar._mainNavHideTimer);
    bar.textContent = message;
    bar.className = "snackbar snackbar--info";
    bar.hidden = false;
    bar.setAttribute("aria-hidden", "false");
    requestAnimationFrame(function () {
      bar.classList.add("snackbar--visible");
    });
    bar._mainNavHideTimer = setTimeout(function () {
      bar.classList.remove("snackbar--visible");
      bar.setAttribute("aria-hidden", "true");
      setTimeout(function () {
        bar.hidden = true;
        bar.className = "snackbar";
        bar.textContent = "";
      }, SNACK_FADE_MS);
    }, SNACK_SHOW_MS);
  }

  document.querySelectorAll("[data-snackbar-trigger]").forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      var msg = btn.getAttribute("data-snackbar-message") || "Future releases";
      showSnackbar(msg);
    });
  });

  function closeAllDropdowns() {
    document.querySelectorAll("[data-main-nav-dropdown]").forEach(function (wrap) {
      var panel = wrap.querySelector(".nav-dropdown__panel");
      var trig = wrap.querySelector(".nav-dropdown__trigger");
      if (panel) panel.hidden = true;
      if (trig) trig.setAttribute("aria-expanded", "false");
      wrap.classList.remove("nav-dropdown--open");
    });
  }

  function closeUserNavMenus() {
    document.querySelectorAll("[data-user-nav]").forEach(function (root) {
      var menu = root.querySelector("[data-user-nav-menu]");
      var btn = root.querySelector(".user-nav__trigger");
      if (menu) menu.hidden = true;
      if (btn) btn.setAttribute("aria-expanded", "false");
      root.classList.remove("user-nav--open");
    });
    document.querySelectorAll("[data-user-nav-submenu]").forEach(function (wrap) {
      var panel = wrap.querySelector(".user-nav__submenu-panel");
      var trig = wrap.querySelector(".user-nav__submenu-trigger");
      if (panel) panel.hidden = true;
      if (trig) trig.setAttribute("aria-expanded", "false");
      wrap.classList.remove("user-nav__submenu--open");
    });
  }

  document.querySelectorAll("[data-main-nav-dropdown]").forEach(function (wrap) {
    var trig = wrap.querySelector(".nav-dropdown__trigger");
    var panel = wrap.querySelector(".nav-dropdown__panel");
    if (!trig || !panel) return;

    trig.addEventListener("click", function (ev) {
      ev.stopPropagation();
      var willOpen = panel.hidden;
      if (willOpen) {
        closeUserNavMenus();
      }
      document.querySelectorAll("[data-main-nav-dropdown]").forEach(function (other) {
        if (other === wrap) return;
        var p = other.querySelector(".nav-dropdown__panel");
        var t = other.querySelector(".nav-dropdown__trigger");
        if (p) p.hidden = true;
        if (t) t.setAttribute("aria-expanded", "false");
        other.classList.remove("nav-dropdown--open");
      });
      panel.hidden = !willOpen;
      trig.setAttribute("aria-expanded", willOpen ? "true" : "false");
      wrap.classList.toggle("nav-dropdown--open", willOpen);
    });
  });

  document.addEventListener("click", function () {
    closeAllDropdowns();
  });

  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") {
      closeAllDropdowns();
    }
  });
})();
