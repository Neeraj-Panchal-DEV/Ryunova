(function () {
  "use strict";

  function closeSubmenus() {
    document.querySelectorAll("[data-user-nav-submenu]").forEach(function (wrap) {
      var panel = wrap.querySelector(".user-nav__submenu-panel");
      var trig = wrap.querySelector(".user-nav__submenu-trigger");
      if (panel) panel.hidden = true;
      if (trig) trig.setAttribute("aria-expanded", "false");
      wrap.classList.remove("user-nav__submenu--open");
    });
  }

  function closeMainNavDropdowns() {
    document.querySelectorAll("[data-main-nav-dropdown]").forEach(function (wrap) {
      var panel = wrap.querySelector(".nav-dropdown__panel");
      var trig = wrap.querySelector(".nav-dropdown__trigger");
      if (panel) panel.hidden = true;
      if (trig) trig.setAttribute("aria-expanded", "false");
      wrap.classList.remove("nav-dropdown--open");
    });
  }

  function closeAll() {
    closeMainNavDropdowns();
    closeSubmenus();
    document.querySelectorAll("[data-user-nav]").forEach(function (root) {
      var menu = root.querySelector("[data-user-nav-menu]");
      var btn = root.querySelector(".user-nav__trigger");
      if (menu) {
        menu.hidden = true;
      }
      if (btn) {
        btn.setAttribute("aria-expanded", "false");
      }
      root.classList.remove("user-nav--open");
    });
  }

  document.querySelectorAll("[data-user-nav]").forEach(function (root) {
    var trigger = root.querySelector(".user-nav__trigger");
    var menu = root.querySelector("[data-user-nav-menu]");
    if (!trigger || !menu) return;

    trigger.addEventListener("click", function (ev) {
      ev.stopPropagation();
      if (!menu.hidden) {
        menu.hidden = true;
        trigger.setAttribute("aria-expanded", "false");
        root.classList.remove("user-nav--open");
        return;
      }
      closeAll();
      menu.hidden = false;
      trigger.setAttribute("aria-expanded", "true");
      root.classList.add("user-nav--open");
    });

    menu.addEventListener("click", function (ev) {
      ev.stopPropagation();
    });
  });

  document.querySelectorAll("[data-user-nav-submenu]").forEach(function (wrap) {
    var trig = wrap.querySelector(".user-nav__submenu-trigger");
    var panel = wrap.querySelector(".user-nav__submenu-panel");
    if (!trig || !panel) return;
    trig.addEventListener("click", function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      var open = panel.hidden;
      document.querySelectorAll("[data-user-nav-submenu]").forEach(function (other) {
        if (other === wrap) return;
        var p = other.querySelector(".user-nav__submenu-panel");
        var t = other.querySelector(".user-nav__submenu-trigger");
        if (p) p.hidden = true;
        if (t) t.setAttribute("aria-expanded", "false");
        other.classList.remove("user-nav__submenu--open");
      });
      panel.hidden = !open;
      trig.setAttribute("aria-expanded", open ? "true" : "false");
      wrap.classList.toggle("user-nav__submenu--open", open);
    });
  });

  document.addEventListener("click", function () {
    closeAll();
  });

  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") {
      closeAll();
    }
  });
})();
