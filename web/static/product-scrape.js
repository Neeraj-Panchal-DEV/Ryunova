(function () {
  "use strict";

  function getCsrfToken() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1].trim()) : "";
  }

  function showToast(msg) {
    var bar = document.getElementById("snackbar");
    if (!bar) {
      alert(msg);
      return;
    }
    bar.textContent = msg;
    bar.className = "snackbar snackbar--tl snackbar--success";
    bar.hidden = false;
    bar.setAttribute("aria-hidden", "false");
    requestAnimationFrame(function () {
      bar.classList.add("snackbar--visible");
    });
    setTimeout(function () {
      bar.classList.remove("snackbar--visible");
      bar.setAttribute("aria-hidden", "true");
      setTimeout(function () {
        bar.hidden = true;
        bar.className = "snackbar";
        bar.textContent = "";
      }, 360);
    }, 4000);
  }

  function setImportAttrs(dataOrigin, importUrl) {
    var hid = document.getElementById("product-import-attributes");
    if (!hid) return;
    var o = { data_origin: dataOrigin, import_source_url: importUrl };
    hid.value = JSON.stringify(o);
  }

  function setField(name, value) {
    var el = document.querySelector('[name="' + name + '"]');
    if (!el || value === undefined || value === null) return;
    if (el.tagName === "SELECT") {
      var opts = el.querySelectorAll("option");
      var v = String(value);
      for (var i = 0; i < opts.length; i++) {
        if (opts[i].value === v) {
          el.value = v;
          return;
        }
      }
      return;
    }
    el.value = value;
  }

  function setDescriptionHtml(html) {
    if (!html) return;
    var ta = document.getElementById("product_description_html");
    if (!ta) return;
    function apply() {
      if (window.tinymce && tinymce.get(ta.id)) {
        tinymce.get(ta.id).setContent(html);
        return true;
      }
      ta.value = html;
      return false;
    }
    if (!apply()) {
      var n = 0;
      var timer = setInterval(function () {
        n++;
        if (apply() || n > 25) clearInterval(timer);
      }, 120);
    }
  }

  function matchBrandByName(name) {
    if (!name) return;
    var sel = document.getElementById("product-field-brand_id");
    if (!sel) return;
    var n = name.trim().toLowerCase();
    var opts = sel.querySelectorAll("option");
    for (var i = 0; i < opts.length; i++) {
      if ((opts[i].textContent || "").trim().toLowerCase() === n) {
        sel.value = opts[i].value;
        return;
      }
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
    var scrapeUrl = document.getElementById("product-scrape-endpoint");
    if (!scrapeUrl) return;
    var endpoint = scrapeUrl.getAttribute("data-url");
    var overlay = document.getElementById("product-scrape-overlay");
    var panel = document.getElementById("product-scrape-drawer");
    var titleEl = document.getElementById("product-scrape-drawer-title");
    var input = document.getElementById("product-scrape-url-input");
    var form = document.getElementById("product-scrape-form");
    var loader = document.getElementById("product-scrape-loader");
    var errEl = document.getElementById("product-scrape-error");
    var currentSource = "shopify";

    function bindOpen(id, source) {
      var btn = document.getElementById(id);
      if (!btn || !overlay || !panel) return;
      btn.addEventListener("click", function () {
        currentSource = source || btn.getAttribute("data-scrape-source") || "shopify";
        if (titleEl) {
          titleEl.textContent =
            currentSource === "ebay" ? "Import from eBay listing" : "Import from Shopify product";
        }
        if (input) input.value = "";
        if (errEl) errEl.textContent = "";
        openOverlay(overlay, panel);
      });
    }

    bindOpen("product-open-scrape-shopify", "shopify");
    bindOpen("product-open-scrape-ebay", "ebay");

    var closeBtn = document.getElementById("product-scrape-close");
    if (closeBtn && overlay && panel) {
      closeBtn.addEventListener("click", function () {
        closeOverlay(overlay, panel);
      });
    }
    if (overlay && panel) {
      overlay.addEventListener("click", function () {
        closeOverlay(overlay, panel);
      });
    }

    if (form && endpoint && input) {
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var u = (input.value || "").trim();
        if (!u) return;
        if (errEl) errEl.textContent = "";
        if (loader) loader.hidden = false;
        fetch(endpoint, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify({ url: u, source: currentSource }),
        })
          .then(function (r) {
            return r.json().then(function (j) {
              return { ok: r.ok, data: j };
            });
          })
          .then(function (x) {
            if (loader) loader.hidden = true;
            if (!x.ok) throw new Error(x.data.detail || "Import failed");
            var d = x.data;
            setField("title", d.title || "");
            setDescriptionHtml(d.description || "");
            if (d.condition) setField("condition", d.condition);
            setField("base_price", d.base_price != null ? String(d.base_price) : "");
            setField("compare_at_price", d.compare_at_price != null ? String(d.compare_at_price) : "");
            if (d.quantity != null) setField("quantity", String(d.quantity));
            setField("model", d.model || "");
            setField("colour", d.colour || "");
            matchBrandByName(d.suggested_brand_name);
            setImportAttrs(d.data_origin || currentSource, d.import_source_url || u);
            closeOverlay(overlay, panel);
            showToast("Import successful — review fields and save the product.");
          })
          .catch(function (e) {
            if (loader) loader.hidden = true;
            if (errEl) errEl.textContent = e.message || "Import failed";
          });
      });
    }
  });
})();
