(function () {
  "use strict";

  function getCsrfToken() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1].trim()) : "";
  }

  function fmtWhen(iso) {
    if (!iso) return "—";
    try {
      var d = new Date(iso);
      return d.toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (e) {
      return iso;
    }
  }

  function renderList(ul, items) {
    ul.innerHTML = "";
    if (!items || !items.length) {
      var li = document.createElement("li");
      li.className = "field__hint";
      li.textContent = "No comments yet.";
      ul.appendChild(li);
      return;
    }
    items.forEach(function (c) {
      var li = document.createElement("li");
      li.className = "product-comments-list__item";
      li.innerHTML =
        '<div class="product-comments-meta"><strong></strong> · <span class="product-comments-time"></span></div>' +
        '<p class="product-comments-body"></p>';
      li.querySelector("strong").textContent = c.author_display_name || "User";
      li.querySelector(".product-comments-time").textContent = fmtWhen(c.created_at);
      li.querySelector(".product-comments-body").textContent = c.body || "";
      ul.appendChild(li);
    });
  }

  function setBtnCount(btn, n) {
    if (!btn) return;
    var span = btn.querySelector(".product-comments-count");
    if (n > 0) {
      btn.classList.add("product-comments-btn--has");
      if (!span) {
        span = document.createElement("span");
        span.className = "product-comments-count";
        btn.appendChild(document.createTextNode(" "));
        btn.appendChild(span);
      }
      span.textContent = String(n);
    } else {
      btn.classList.remove("product-comments-btn--has");
      if (span) span.remove();
    }
  }

  function openOverlay(overlay, panel) {
    overlay.hidden = false;
    overlay.classList.add("drawer-overlay--visible");
    overlay.setAttribute("aria-hidden", "false");
    panel.hidden = false;
    requestAnimationFrame(function () {
      panel.classList.add("drawer-panel--open");
    });
  }

  function closeOverlay(overlay, panel) {
    panel.classList.remove("drawer-panel--open");
    overlay.classList.remove("drawer-overlay--visible");
    overlay.setAttribute("aria-hidden", "true");
    setTimeout(function () {
      overlay.hidden = true;
      panel.hidden = true;
    }, 340);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var openBtn = document.getElementById("product-open-comments");
    if (!openBtn) return;

    var url = openBtn.getAttribute("data-comments-url");
    var overlay = document.getElementById("product-comments-overlay");
    var panel = document.getElementById("product-comments-drawer");
    var ul = document.getElementById("product-comments-list");
    var addWrap = document.getElementById("product-comments-add-wrap");
    var openAddBtn = document.getElementById("product-comments-open-add");
    var form = document.getElementById("product-comments-form");
    var textarea = document.getElementById("product-comments-body-input");
    var cancelAdd = document.getElementById("product-comments-cancel-add");

    function loadComments() {
      if (!url || !ul) return;
      fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } })
        .then(function (r) {
          return r.json().then(function (j) {
            return { ok: r.ok, data: j };
          });
        })
        .then(function (x) {
          if (!x.ok) throw new Error(x.data.detail || "Failed to load comments");
          renderList(ul, x.data);
        })
        .catch(function (e) {
          ul.innerHTML = '<li class="field__hint">' + (e.message || "Could not load comments.") + "</li>";
        });
    }

    openBtn.addEventListener("click", function () {
      if (overlay && panel) {
        openOverlay(overlay, panel);
        loadComments();
      }
    });

    if (overlay) {
      overlay.addEventListener("click", function () {
        if (panel) closeOverlay(overlay, panel);
      });
    }
    var closeBtn = document.getElementById("product-comments-close");
    if (closeBtn && overlay && panel) {
      closeBtn.addEventListener("click", function () {
        closeOverlay(overlay, panel);
      });
    }

    if (openAddBtn && addWrap) {
      openAddBtn.addEventListener("click", function () {
        addWrap.hidden = false;
        if (textarea) {
          textarea.value = "";
          textarea.focus();
        }
      });
    }
    if (cancelAdd && addWrap) {
      cancelAdd.addEventListener("click", function () {
        addWrap.hidden = true;
        if (textarea) textarea.value = "";
      });
    }

    if (form && textarea && url) {
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var body = (textarea.value || "").trim();
        if (!body) return;
        fetch(url, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify({ body: body }),
        })
          .then(function (r) {
            return r.json().then(function (j) {
              return { ok: r.ok, data: j };
            });
          })
          .then(function (x) {
            if (!x.ok) throw new Error(x.data.detail || "Could not save comment");
            addWrap.hidden = true;
            textarea.value = "";
            var first = ul.querySelector(".product-comments-list__item") || ul.firstChild;
            var li = document.createElement("li");
            li.className = "product-comments-list__item";
            li.innerHTML =
              '<div class="product-comments-meta"><strong></strong> · <span class="product-comments-time"></span></div>' +
              '<p class="product-comments-body"></p>';
            li.querySelector("strong").textContent = x.data.author_display_name || "You";
            li.querySelector(".product-comments-time").textContent = fmtWhen(x.data.created_at);
            li.querySelector(".product-comments-body").textContent = x.data.body || "";
            var hint = ul.querySelector("li.field__hint");
            if (hint) hint.remove();
            if (ul.firstChild) ul.insertBefore(li, ul.firstChild);
            else ul.appendChild(li);
            var n = ul.querySelectorAll(".product-comments-list__item").length;
            setBtnCount(openBtn, n);
            var listBtns = document.querySelectorAll(".product-list-comments-btn[data-product-id]");
            listBtns.forEach(function (b) {
              if (b.getAttribute("data-product-id") === openBtn.getAttribute("data-product-id")) {
                setBtnCount(b, n);
              }
            });
          })
          .catch(function (e) {
            alert(e.message || "Error");
          });
      });
    }

    if (window.location.hash === "#comments" && overlay && panel) {
      openOverlay(overlay, panel);
      loadComments();
    }
  });
})();
