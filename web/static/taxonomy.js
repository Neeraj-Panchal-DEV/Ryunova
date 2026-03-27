(function () {
  "use strict";

  function getCookie(name) {
    const m = document.cookie.match("(^|;) ?" + name + "=([^;]*)(;|$)");
    return m ? decodeURIComponent(m[2]) : null;
  }

  function csrftoken() {
    return getCookie("csrftoken");
  }

  function esc(s) {
    if (s == null) return "";
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function truncate(s, n) {
    if (!s) return "";
    s = String(s);
    return s.length <= n ? s : s.slice(0, n) + "…";
  }

  function fmtDate(iso) {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return String(iso);
      return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
    } catch (e) {
      return String(iso);
    }
  }

  function compareVal(a, b, mult) {
    if (a == null && b == null) return 0;
    if (a == null) return mult;
    if (b == null) return -mult;
    if (typeof a === "boolean" || typeof b === "boolean") {
      const na = a ? 1 : 0;
      const nb = b ? 1 : 0;
      return na < nb ? -mult : na > nb ? mult : 0;
    }
    if (typeof a === "number" && typeof b === "number") {
      return a < b ? -mult : a > b ? mult : 0;
    }
    const sa = String(a).toLowerCase();
    const sb = String(b).toLowerCase();
    if (sa < sb) return -mult;
    if (sa > sb) return mult;
    return 0;
  }

  function initPage(root) {
    const kind = root.dataset.kind;
    const listUrl = root.dataset.listUrl || "";
    const listPath = listUrl.split("?")[0];
    const reorderUrl = root.dataset.reorderUrl || "";
    const sortNameUrl = root.dataset.sortNameUrl || "";
    const includeInactive = root.dataset.includeInactive === "true";
    const initialEl = document.getElementById("taxonomy-initial");
    let items = [];
    try {
      items = initialEl && initialEl.textContent ? JSON.parse(initialEl.textContent) : [];
    } catch (e) {
      items = [];
    }
    if (!Array.isArray(items)) items = [];

    let sortKey = root.dataset.sort || "sort_order";
    let sortDir = root.dataset.order || "asc";

    function reorderAllowed() {
      return sortKey === "sort_order" && sortDir === "asc";
    }

    const tbody = root.querySelector("[data-taxonomy-tbody]");
    const overlay = root.querySelector("[data-drawer-overlay]");
    const addDrawer = root.querySelector("[data-drawer-add]");
    const detailDrawer = root.querySelector("[data-drawer-detail]");
    const addForm = root.querySelector("[data-add-form]");
    const detailBody = root.querySelector("[data-detail-body]");
    const openAddBtn = root.querySelector("[data-open-add]");

    function applySort() {
      const mult = sortDir === "asc" ? 1 : -1;
      const key = sortKey;
      items.sort(function (a, b) {
        return compareVal(a[key], b[key], mult);
      });
    }

    function updateSortHeaders() {
      root.querySelectorAll("[data-sort-col]").forEach(function (th) {
        const k = th.getAttribute("data-sort-col");
        th.classList.remove("taxonomy-th--sorted-asc", "taxonomy-th--sorted-desc");
        if (k === sortKey) {
          th.classList.add(sortDir === "asc" ? "taxonomy-th--sorted-asc" : "taxonomy-th--sorted-desc");
        }
      });
    }

    function renderTable() {
      if (!tbody) return;
      tbody.innerHTML = "";
      const base = listPath.replace(/\/$/, "");

      items.forEach(function (row) {
        const tr = document.createElement("tr");
        tr.setAttribute("data-taxonomy-row", "1");
        tr.dataset.id = row.id;
        tr.className = row.active ? "" : "row-inactive";
        tr.setAttribute("tabindex", "0");
        tr.setAttribute("role", "button");

        const setUrl = base + "/" + row.id + "/set-active/";

        const toggleLabel = row.active ? "Disable" : "Enable";
        const toggleClass = row.active ? "btn btn--small taxonomy-toggle-active" : "btn btn--small btn--primary taxonomy-toggle-active";
        const activeVal = row.active ? "false" : "true";

        let html = "";
        html += '<td class="taxonomy-td-drag" data-stop-row="1">';
        if (reorderAllowed()) {
          html +=
            '<span class="taxonomy-drag-handle" draggable="true" title="Drag to reorder rows">⋮⋮</span>';
        } else {
          html +=
            '<span class="taxonomy-drag-handle taxonomy-drag-handle--inactive" title="Click the Sort column header until it sorts ascending (0,1,2…) to drag rows">⋮⋮</span>';
        }
        html += "</td>";
        html += '<td class="taxonomy-td-name">' + esc(row.name) + "</td>";
        if (kind === "category") {
          html += '<td class="taxonomy-td-muted">' + esc(row.parent_name || "—") + "</td>";
        }
        html += '<td class="taxonomy-td-desc" title="' + esc(row.description || "") + '">';
        html += esc(truncate(row.description, 56) || "—");
        html += "</td>";
        html += "<td>" + esc(row.slug || "—") + "</td>";
        html += "<td>" + esc(String(row.sort_order ?? "—")) + "</td>";
        html +=
          "<td>" +
          (row.active
            ? '<span class="badge">yes</span>'
            : '<span class="badge badge--muted">no</span>') +
          "</td>";
        html += '<td class="taxonomy-td-date">' + esc(fmtDate(row.created_at)) + "</td>";
        html += '<td class="taxonomy-td-date">' + esc(fmtDate(row.updated_at)) + "</td>";
        html += '<td class="taxonomy-td-muted">' + esc(row.created_by_label || "—") + "</td>";
        html += '<td class="taxonomy-td-muted">' + esc(row.updated_by_label || "—") + "</td>";
        html += '<td class="cell-actions taxonomy-cell-actions" data-stop-row="1">';
        html += '<div class="taxonomy-cell-actions__toolbar">';
        html +=
          '<button type="button" class="' +
          esc(toggleClass) +
          '" data-toggle-url="' +
          esc(setUrl) +
          '" data-active-next="' +
          esc(activeVal) +
          '">' +
          esc(toggleLabel) +
          "</button>";
        html += "</div></td>";

        tr.innerHTML = html;

        tr.addEventListener("click", function (ev) {
          if (ev.target.closest("[data-stop-row]")) return;
          openDetail(row);
        });
        tr.addEventListener("keydown", function (ev) {
          if (ev.key !== "Enter" && ev.key !== " ") return;
          if (ev.target.closest("[data-stop-row]")) return;
          ev.preventDefault();
          openDetail(row);
        });

        tbody.appendChild(tr);
      });
    }

    function openDetail(row) {
      const base = listPath.replace(/\/$/, "");
      const q = includeInactive ? "?include_inactive=on" : "";
      const editHref = base + "/" + row.id + "/edit/" + q;

      const rows =
        kind === "category"
          ? [
              ["Name", row.name],
              ["Slug", row.slug || "—"],
              ["Description", row.description || "—"],
              ["Sort order", String(row.sort_order ?? "—")],
              ["Enabled", row.active ? "Yes" : "No"],
              ["Parent", row.parent_name || "—"],
              ["Date added", fmtDate(row.created_at)],
              ["Last modified", fmtDate(row.updated_at)],
              ["Added by", row.created_by_label || "—"],
              ["Last updated by", row.updated_by_label || "—"],
            ]
          : [
              ["Name", row.name],
              ["Slug", row.slug || "—"],
              ["Description", row.description || "—"],
              ["Sort order", String(row.sort_order ?? "—")],
              ["Enabled", row.active ? "Yes" : "No"],
              ["Date added", fmtDate(row.created_at)],
              ["Last modified", fmtDate(row.updated_at)],
              ["Added by", row.created_by_label || "—"],
              ["Last updated by", row.updated_by_label || "—"],
            ];

      detailBody.innerHTML =
        '<dl class="taxonomy-detail-dl">' +
        rows
          .map(function (p) {
            return (
              '<div class="taxonomy-detail-row"><dt>' +
              esc(p[0]) +
              '</dt><dd class="taxonomy-detail-dd">' +
              esc(p[1]) +
              "</dd></div>"
            );
          })
          .join("") +
        "</dl>" +
        '<p class="taxonomy-detail-actions"><a class="btn btn--yellow" href="' +
        esc(editHref) +
        '">Edit</a></p>';

      overlay.hidden = false;
      detailDrawer.hidden = false;
      addDrawer.hidden = true;
      addDrawer.classList.remove("drawer-panel--open");
      requestAnimationFrame(function () {
        overlay.classList.add("drawer-overlay--visible");
        detailDrawer.classList.add("drawer-panel--open");
      });
    }

    function closeDetail() {
      detailDrawer.classList.remove("drawer-panel--open");
      setTimeout(function () {
        detailDrawer.hidden = true;
        if (!addDrawer.classList.contains("drawer-panel--open")) {
          overlay.classList.remove("drawer-overlay--visible");
          overlay.hidden = true;
        }
      }, 340);
    }

    function openAdd() {
      addForm.reset();
      const activeCb = addForm.querySelector('[name="active"]');
      if (activeCb) activeCb.checked = true;
      fillParentSelect();
      overlay.hidden = false;
      addDrawer.hidden = false;
      detailDrawer.hidden = true;
      detailDrawer.classList.remove("drawer-panel--open");
      requestAnimationFrame(function () {
        overlay.classList.add("drawer-overlay--visible");
        addDrawer.classList.add("drawer-panel--open");
      });
    }

    function closeAdd() {
      addDrawer.classList.remove("drawer-panel--open");
      setTimeout(function () {
        addDrawer.hidden = true;
        if (!detailDrawer.classList.contains("drawer-panel--open")) {
          overlay.classList.remove("drawer-overlay--visible");
          overlay.hidden = true;
        }
      }, 340);
    }

    function fillParentSelect() {
      const sel = addForm.querySelector('[name="parent_id"]');
      if (!sel) return;
      const prev = sel.value;
      sel.innerHTML = '<option value="">— None —</option>';
      items.forEach(function (c) {
        const o = document.createElement("option");
        o.value = c.id;
        o.textContent = c.name;
        sel.appendChild(o);
      });
      if (prev) sel.value = prev;
    }

    if (openAddBtn) openAddBtn.addEventListener("click", openAdd);

    const sortNameBtn = root.querySelector("[data-taxonomy-sort-name]");
    if (sortNameBtn && sortNameUrl) {
      sortNameBtn.addEventListener("click", function () {
        const q = includeInactive ? "?include_inactive=on" : "";
        fetch(sortNameUrl + q, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrftoken() || "",
          },
          body: "{}",
          credentials: "same-origin",
        })
          .then(function (r) {
            return r.json().then(function (j) {
              if (!r.ok) throw new Error(j.error || "Request failed");
              if (j.items) {
                items = j.items;
                sortKey = "sort_order";
                sortDir = "asc";
                updateSortHeaders();
                renderTable();
              }
            });
          })
          .catch(function (e) {
            alert(e.message || "Could not reorder");
          });
      });
    }

    function moveRowBefore(sourceId, targetId) {
      const si = items.findIndex(function (x) {
        return String(x.id) === String(sourceId);
      });
      const ti = items.findIndex(function (x) {
        return String(x.id) === String(targetId);
      });
      if (si < 0 || ti < 0 || si === ti) return false;
      const copy = items.slice();
      const row = copy.splice(si, 1)[0];
      const newTi = si < ti ? ti - 1 : ti;
      copy.splice(newTi, 0, row);
      items = copy;
      return true;
    }

    function moveRowAfter(sourceId, targetId) {
      const si = items.findIndex(function (x) {
        return String(x.id) === String(sourceId);
      });
      const ti = items.findIndex(function (x) {
        return String(x.id) === String(targetId);
      });
      if (si < 0 || ti < 0 || si === ti) return false;
      const copy = items.slice();
      const row = copy.splice(si, 1)[0];
      let ins = ti;
      if (si < ti) ins = ti - 1;
      copy.splice(ins + 1, 0, row);
      items = copy;
      return true;
    }

    function persistRowOrder() {
      if (!reorderUrl || !reorderAllowed()) return;
      const q = includeInactive ? "?include_inactive=on" : "";
      fetch(reorderUrl + q, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken() || "",
        },
        body: JSON.stringify({ ordered_ids: items.map(function (x) { return x.id; }) }),
        credentials: "same-origin",
      })
        .then(function (r) {
          return r.json().then(function (j) {
            if (!r.ok) throw new Error(j.error || "Reorder failed");
            if (j.items) {
              items = j.items;
              sortKey = "sort_order";
              sortDir = "asc";
              updateSortHeaders();
              renderTable();
            }
          });
        })
        .catch(function (e) {
          alert(e.message || "Could not save order");
          window.location.reload();
        });
    }

    if (tbody && reorderUrl) {
      tbody.addEventListener("dragstart", function (ev) {
        const h = ev.target.closest(".taxonomy-drag-handle[draggable=true]");
        if (!h) return;
        const tr = h.closest("tr[data-taxonomy-row]");
        if (!tr || !reorderAllowed()) return;
        ev.dataTransfer.setData("text/plain", tr.dataset.id);
        ev.dataTransfer.effectAllowed = "move";
        tr.classList.add("taxonomy-row--dragging");
      });
      tbody.addEventListener("dragend", function () {
        tbody.querySelectorAll(".taxonomy-row--dragging").forEach(function (el) {
          el.classList.remove("taxonomy-row--dragging");
        });
      });
      tbody.addEventListener("dragover", function (ev) {
        if (!reorderAllowed()) return;
        const tr = ev.target.closest("tr[data-taxonomy-row]");
        if (!tr) return;
        ev.preventDefault();
        ev.dataTransfer.dropEffect = "move";
      });
      tbody.addEventListener("drop", function (ev) {
        if (!reorderAllowed()) return;
        const targetTr = ev.target.closest("tr[data-taxonomy-row]");
        const sourceId = ev.dataTransfer.getData("text/plain");
        if (!targetTr || !sourceId) return;
        const targetId = targetTr.dataset.id;
        if (!targetId || String(sourceId) === String(targetId)) return;
        ev.preventDefault();
        const rect = targetTr.getBoundingClientRect();
        const after = ev.clientY > rect.top + rect.height / 2;
        const ok = after ? moveRowAfter(sourceId, targetId) : moveRowBefore(sourceId, targetId);
        if (ok) {
          renderTable();
          persistRowOrder();
        }
      });
    }

    root.querySelectorAll("[data-close-add]").forEach(function (btn) {
      btn.addEventListener("click", closeAdd);
    });
    root.querySelectorAll("[data-close-detail]").forEach(function (btn) {
      btn.addEventListener("click", closeDetail);
    });

    overlay.addEventListener("click", function () {
      closeAdd();
      closeDetail();
    });

    root.querySelectorAll("[data-sort-col]").forEach(function (th) {
      th.addEventListener("click", function () {
        const k = th.getAttribute("data-sort-col");
        if (k === sortKey) {
          sortDir = sortDir === "asc" ? "desc" : "asc";
        } else {
          sortKey = k;
          sortDir = "asc";
        }
        applySort();
        updateSortHeaders();
        renderTable();
      });
    });

    if (addForm) {
      addForm.addEventListener("submit", function (ev) {
        ev.preventDefault();
        const submitter = ev.submitter;
        const keepAddOpen =
          submitter &&
          submitter.getAttribute &&
          submitter.getAttribute("data-keep-add-open") === "true";
        const fd = new FormData(addForm);
        const body = {
          name: (fd.get("name") || "").toString().trim(),
          description: (fd.get("description") || "").toString().trim() || null,
          sort_order: null,
          active: !!fd.get("active"),
        };
        if (kind === "category") {
          const pid = (fd.get("parent_id") || "").toString().trim();
          body.parent_id = pid || null;
        }
        if (!body.name) {
          alert("Name is required.");
          return;
        }
        const saveBtns = addForm.querySelectorAll('button[type="submit"]');
        saveBtns.forEach(function (b) {
          b.disabled = true;
        });
        fetch(listPath, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrftoken() || "",
          },
          body: JSON.stringify(body),
          credentials: "same-origin",
        })
          .then(function (r) {
            return r.json().then(function (j) {
              if (!r.ok) throw new Error(j.error || "Request failed");
              if (j.item) {
                items.push(j.item);
                applySort();
                updateSortHeaders();
                renderTable();
              }
              if (keepAddOpen) {
                addForm.reset();
                const activeCb = addForm.querySelector('[name="active"]');
                if (activeCb) activeCb.checked = true;
                fillParentSelect();
                const nameInput = addForm.querySelector('[name="name"]');
                if (nameInput) nameInput.focus();
              } else {
                closeAdd();
              }
            });
          })
          .catch(function (e) {
            alert(e.message || "Could not save");
          })
          .finally(function () {
            saveBtns.forEach(function (b) {
              b.disabled = false;
            });
          });
      });
    }

    if (tbody) {
      tbody.addEventListener("click", function (ev) {
        const btn = ev.target.closest(".taxonomy-toggle-active");
        if (!btn) return;
        ev.stopPropagation();
        const url = btn.getAttribute("data-toggle-url");
        const nextActive = btn.getAttribute("data-active-next") === "true";
        const fd = new FormData();
        fd.append("csrfmiddlewaretoken", csrftoken() || "");
        fd.append("next", listPath + (includeInactive ? "?include_inactive=on" : ""));
        fd.append("active", nextActive ? "true" : "false");
        const tr = btn.closest("tr[data-taxonomy-row]");
        const rowId = tr && tr.dataset.id;
        fetch(url, {
          method: "POST",
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": csrftoken() || "",
          },
          body: fd,
          credentials: "same-origin",
        })
          .then(function (r) {
            return r.json().then(function (j) {
              if (!r.ok) throw new Error(j.error || "Failed");
              const row = items.find(function (x) {
                return String(x.id) === String(rowId);
              });
              if (row) row.active = nextActive;
              applySort();
              updateSortHeaders();
              renderTable();
            });
          })
          .catch(function () {
            window.location.reload();
          });
      });
    }

    updateSortHeaders();
    renderTable();
  }

  document.querySelectorAll("[data-taxonomy-page]").forEach(initPage);
})();
