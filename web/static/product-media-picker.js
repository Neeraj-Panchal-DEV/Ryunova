/**
 * Multi file picker: previews + sync radio selection to hidden cover_index for create / edit-without-media.
 */
(function () {
  const input = document.getElementById("product-media-input");
  const preview = document.getElementById("product-media-preview");
  const coverField = document.getElementById("product-cover-index");
  if (!input || !preview || !coverField) return;

  function extOf(name) {
    const m = (name || "").toLowerCase().match(/\.([a-z0-9]+)$/);
    return m ? m[1] : "";
  }

  function isVideoFile(f) {
    const t = (f.type || "").toLowerCase();
    if (t.startsWith("video/")) return true;
    return /^(mp4|webm|mov)$/i.test(extOf(f.name));
  }

  function render() {
    preview.innerHTML = "";
    const files = input.files;
    if (!files.length) {
      coverField.value = "0";
      return;
    }
    const n = files.length;
    let current = parseInt(coverField.value, 10);
    if (Number.isNaN(current) || current < 0 || current >= n) current = 0;
    coverField.value = String(current);

    for (let i = 0; i < n; i++) {
      const f = files[i];
      const card = document.createElement("div");
      card.className = "product-media-preview__card";

      const wrap = document.createElement("div");
      wrap.className = "product-media-preview__thumb";
      const url = URL.createObjectURL(f);
      if (isVideoFile(f)) {
        const v = document.createElement("video");
        v.src = url;
        v.muted = true;
        v.playsInline = true;
        v.preload = "metadata";
        wrap.appendChild(v);
      } else {
        const im = document.createElement("img");
        im.src = url;
        im.alt = "";
        wrap.appendChild(im);
      }

      const label = document.createElement("label");
      label.className = "product-media-preview__cover-label";
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = "cover_pick_new_ui";
      radio.checked = i === current;
      radio.addEventListener("change", function () {
        if (radio.checked) coverField.value = String(i);
      });
      const span = document.createElement("span");
      span.textContent = " Cover";

      label.appendChild(radio);
      label.appendChild(span);
      card.appendChild(wrap);
      card.appendChild(label);
      preview.appendChild(card);
    }
  }

  input.addEventListener("change", render);
})();
