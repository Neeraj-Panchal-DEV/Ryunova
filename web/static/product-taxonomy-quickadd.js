/**
 * Product form: quick-add category / brand via same drawer pattern as taxonomy list pages.
 * POSTs JSON to Django category_list / brand_list (same as taxonomy.js).
 */
(function () {
  "use strict";

  function getCookie(name) {
    const m = document.cookie.match("(^|;) ?" + name + "=([^;]*)(;|$)");
    return m ? decodeURIComponent(m[2]) : null;
  }

  function csrftoken() {
    return getCookie("csrftoken");
  }

  /** Parse JSON body; on error responses prefer API detail/error over raw HTML. */
  function parseResponseJson(r) {
    return r.text().then(function (t) {
      var j = {};
      try {
        j = t ? JSON.parse(t) : {};
      } catch (ignore) {
        j = {};
      }
      if (!r.ok) {
        var msg =
          (typeof j.detail === "string" && j.detail) ||
          (Array.isArray(j.detail) && j.detail.map(function (x) { return x.msg || x; }).join("; ")) ||
          j.error ||
          (t && t.indexOf("<!DOCTYPE") === -1 && t.slice(0, 400)) ||
          r.statusText ||
          "Request failed";
        throw new Error(msg);
      }
      return j;
    });
  }

  const root = document.getElementById("product-taxonomy-quickadd");
  if (!root) return;

  const categoryUrl = root.dataset.categoryUrl || "";
  const brandUrl = root.dataset.brandUrl || "";
  const includeInactive = root.dataset.includeInactive === "true";

  let categoriesSnapshot = [];
  try {
    const el = document.getElementById("product-form-categories-json");
    categoriesSnapshot = el && el.textContent ? JSON.parse(el.textContent) : [];
  } catch (e) {
    categoriesSnapshot = [];
  }
  if (!Array.isArray(categoriesSnapshot)) categoriesSnapshot = [];

  const overlay = document.getElementById("product-quick-overlay");
  const drawerCat = document.getElementById("product-quick-drawer-category");
  const drawerBrand = document.getElementById("product-quick-drawer-brand");
  const formCat = document.getElementById("product-quick-form-category");
  const formBrand = document.getElementById("product-quick-form-brand");
  const selCategory = document.getElementById("product-field-category_id");
  const selBrand = document.getElementById("product-field-brand_id");

  if (!overlay || !drawerCat || !drawerBrand || !formCat || !formBrand || !selCategory || !selBrand) {
    return;
  }

  function listJsonUrl(base) {
    const u = new URL(base, window.location.origin);
    u.searchParams.set("format", "json");
    if (includeInactive) u.searchParams.set("include_inactive", "on");
    return u.pathname + u.search;
  }

  function closeDrawer() {
    drawerCat.classList.remove("drawer-panel--open");
    drawerBrand.classList.remove("drawer-panel--open");
    setTimeout(function () {
      overlay.classList.remove("drawer-overlay--visible");
      overlay.hidden = true;
      overlay.setAttribute("aria-hidden", "true");
      drawerCat.hidden = true;
      drawerBrand.hidden = true;
    }, 340);
  }

  function openCategoryDrawer() {
    formCat.reset();
    const activeCb = formCat.querySelector('[name="active"]');
    if (activeCb) activeCb.checked = true;
    fillParentSelect();
    drawerBrand.hidden = true;
    drawerBrand.classList.remove("drawer-panel--open");
    overlay.hidden = false;
    overlay.setAttribute("aria-hidden", "false");
    drawerCat.hidden = false;
    requestAnimationFrame(function () {
      overlay.classList.add("drawer-overlay--visible");
      drawerCat.classList.add("drawer-panel--open");
      const first = formCat.querySelector('input[name="name"]');
      if (first) first.focus();
    });
  }

  function openBrandDrawer() {
    formBrand.reset();
    const activeCb = formBrand.querySelector('[name="active"]');
    if (activeCb) activeCb.checked = true;
    drawerCat.hidden = true;
    drawerCat.classList.remove("drawer-panel--open");
    overlay.hidden = false;
    overlay.setAttribute("aria-hidden", "false");
    drawerBrand.hidden = false;
    requestAnimationFrame(function () {
      overlay.classList.add("drawer-overlay--visible");
      drawerBrand.classList.add("drawer-panel--open");
      const first = formBrand.querySelector('input[name="name"]');
      if (first) first.focus();
    });
  }

  function fillParentSelect() {
    const sel = formCat.querySelector('[name="parent_id"]');
    if (!sel) return;
    const prev = sel.value;
    sel.innerHTML = '<option value="">— None —</option>';
    categoriesSnapshot.forEach(function (c) {
      const o = document.createElement("option");
      o.value = c.id;
      o.textContent = c.name;
      sel.appendChild(o);
    });
    if (prev) sel.value = prev;
  }

  function mergeCategoryIntoSnapshot(item) {
    if (!item || item.id == null) return;
    const idStr = String(item.id);
    categoriesSnapshot = categoriesSnapshot.filter(function (c) {
      return String(c.id) !== idStr;
    });
    categoriesSnapshot.push(item);
  }

  function refreshCategoriesSnapshot() {
    return fetch(listJsonUrl(categoryUrl), {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    })
      .then(function (r) {
        return r.json().then(function (j) {
          if (r.ok && j.items) categoriesSnapshot = j.items;
        });
      })
      .catch(function () {
        /* keep snapshot */
      });
  }

  function addOrSelectOption(select, id, name) {
    const idStr = String(id);
    let found = false;
    for (let i = 0; i < select.options.length; i++) {
      if (select.options[i].value === idStr) {
        select.options[i].textContent = name;
        found = true;
        break;
      }
    }
    if (!found) {
      const o = document.createElement("option");
      o.value = idStr;
      o.textContent = name;
      select.appendChild(o);
    }
    select.value = idStr;
  }

  document.querySelectorAll("[data-open-quick-category]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      openCategoryDrawer();
    });
  });

  document.querySelectorAll("[data-open-quick-brand]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      openBrandDrawer();
    });
  });

  document.querySelectorAll("[data-close-product-quick]").forEach(function (btn) {
    btn.addEventListener("click", closeDrawer);
  });

  overlay.addEventListener("click", closeDrawer);

  formCat.addEventListener("submit", function (ev) {
    ev.preventDefault();
    const fd = new FormData(formCat);
    const body = {
      name: (fd.get("name") || "").toString().trim(),
      description: (fd.get("description") || "").toString().trim() || null,
      sort_order: null,
      active: !!fd.get("active"),
    };
    const pid = (fd.get("parent_id") || "").toString().trim();
    body.parent_id = pid || null;
    if (!body.name) {
      alert("Name is required.");
      return;
    }
    fetch(categoryUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrftoken() || "",
      },
      body: JSON.stringify(body),
      credentials: "same-origin",
    })
      .then(parseResponseJson)
      .then(function (j) {
        if (j.item) {
          addOrSelectOption(selCategory, j.item.id, j.item.name);
          mergeCategoryIntoSnapshot(j.item);
          fillParentSelect();
          refreshCategoriesSnapshot().then(function () {
            fillParentSelect();
          });
        }
      })
      .then(function () {
        closeDrawer();
      })
      .catch(function (e) {
        alert(e.message || "Could not save category");
      });
  });

  formBrand.addEventListener("submit", function (ev) {
    ev.preventDefault();
    const fd = new FormData(formBrand);
    const body = {
      name: (fd.get("name") || "").toString().trim(),
      description: (fd.get("description") || "").toString().trim() || null,
      sort_order: null,
      active: !!fd.get("active"),
    };
    if (!body.name) {
      alert("Name is required.");
      return;
    }
    fetch(brandUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrftoken() || "",
      },
      body: JSON.stringify(body),
      credentials: "same-origin",
    })
      .then(parseResponseJson)
      .then(function (j) {
        if (j.item) {
          addOrSelectOption(selBrand, j.item.id, j.item.name);
        }
      })
      .then(function () {
        closeDrawer();
      })
      .catch(function (e) {
        alert(e.message || "Could not save brand");
      });
  });
})();
