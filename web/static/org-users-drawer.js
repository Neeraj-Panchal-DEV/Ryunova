(function () {
  var drawer = document.getElementById("org-users-drawer");
  if (!drawer) return;

  var openBtn = document.getElementById("org-users-open-drawer");
  var closeBtn = document.getElementById("org-users-close-drawer");
  var cancelBtn = document.getElementById("org-users-cancel-drawer");
  var backdrop = document.getElementById("org-users-drawer-backdrop");

  function openDrawer() {
    drawer.removeAttribute("hidden");
    drawer.setAttribute("aria-hidden", "false");
    if (openBtn) openBtn.setAttribute("aria-expanded", "true");
    document.body.classList.add("drawer-open");
    if (closeBtn) closeBtn.focus();
  }

  function closeDrawer() {
    drawer.setAttribute("hidden", "");
    drawer.setAttribute("aria-hidden", "true");
    if (openBtn) {
      openBtn.setAttribute("aria-expanded", "false");
      openBtn.focus();
    }
    document.body.classList.remove("drawer-open");
  }

  if (openBtn) openBtn.addEventListener("click", openDrawer);
  if (closeBtn) closeBtn.addEventListener("click", closeDrawer);
  if (cancelBtn) cancelBtn.addEventListener("click", closeDrawer);
  if (backdrop) backdrop.addEventListener("click", closeDrawer);

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !drawer.hasAttribute("hidden")) closeDrawer();
  });
})();
