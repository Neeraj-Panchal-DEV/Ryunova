(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("product-master-form");
    if (!form) return;
    form.addEventListener("submit", function () {
      var btns = form.querySelectorAll("button[type='submit']");
      for (var i = 0; i < btns.length; i++) {
        var b = btns[i];
        if (b.disabled) continue;
        b.disabled = true;
        if (!b.getAttribute("data-original-label")) {
          b.setAttribute("data-original-label", b.textContent.trim());
        }
        b.textContent = "Saving…";
      }
    });
  });
})();
