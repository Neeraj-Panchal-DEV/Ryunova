(function () {
  "use strict";

  var DISPLAY_MS = 3500;
  var DISPLAY_MS_ERROR = 12000;
  var FADE_MS = 360;

  function levelModifier(tags) {
    var t = (tags || "info").toLowerCase();
    if (t.indexOf("error") !== -1 || t.indexOf("danger") !== -1) return "snackbar--error";
    if (t.indexOf("success") !== -1) return "snackbar--success";
    if (t.indexOf("warning") !== -1) return "snackbar--warning";
    if (t.indexOf("debug") !== -1) return "snackbar--debug";
    return "snackbar--info";
  }

  function showSnackbar(bar, text, levelTags, done) {
    if (!bar) {
      if (done) done();
      return;
    }
    bar.textContent = text;
    bar.className = "snackbar " + levelModifier(levelTags);
    bar.hidden = false;
    bar.setAttribute("aria-hidden", "false");
    bar.title = "Click to dismiss";
    bar.onclick = function () {
      clearTimeout(bar._flashHideTimer);
      bar.classList.remove("snackbar--visible");
      bar.setAttribute("aria-hidden", "true");
      setTimeout(function () {
        bar.hidden = true;
        bar.className = "snackbar";
        bar.textContent = "";
        bar.onclick = null;
        bar.removeAttribute("title");
        if (done) done();
      }, FADE_MS);
    };
    requestAnimationFrame(function () {
      bar.classList.add("snackbar--visible");
    });
    var dur = DISPLAY_MS;
    var tl = (levelTags || "info").toLowerCase();
    if (tl.indexOf("error") !== -1 || tl.indexOf("danger") !== -1) {
      dur = DISPLAY_MS_ERROR;
    }
    clearTimeout(bar._flashHideTimer);
    bar._flashHideTimer = setTimeout(function () {
      bar.classList.remove("snackbar--visible");
      bar.setAttribute("aria-hidden", "true");
      bar.onclick = null;
      bar.removeAttribute("title");
      setTimeout(function () {
        bar.hidden = true;
        bar.className = "snackbar";
        bar.textContent = "";
        if (done) done();
      }, FADE_MS);
    }, dur);
  }

  function runQueue(bar, items, index) {
    if (!items || index >= items.length) return;
    showSnackbar(bar, items[index].text, items[index].level, function () {
      runQueue(bar, items, index + 1);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var data = window.__FLASH_MESSAGES__;
    if (!data || !data.length) return;
    delete window.__FLASH_MESSAGES__;
    var bar = document.getElementById("snackbar");
    runQueue(bar, data, 0);
  });
})();
