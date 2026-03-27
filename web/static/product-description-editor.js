/**
 * Rich HTML product description (TinyMCE) — stored in `description` for channel APIs (e.g. Shopify body_html).
 */
(function () {
  "use strict";

  var TA_ID = "product_description_html";

  function run() {
    var el = document.getElementById(TA_ID);
    if (!el || typeof tinymce === "undefined") return;

    tinymce.init({
      selector: "#" + TA_ID,
      height: 420,
      menubar: false,
      license_key: "gpl",
      promotion: false,
      branding: false,
      plugins: "lists link autoresize code table",
      toolbar:
        "undo redo | blocks | bold italic underline strikethrough | alignleft aligncenter alignright | bullist numlist outdent indent | link table | removeformat | code",
      block_formats: "Paragraph=p; Heading 2=h2; Heading 3=h3; Preformatted=pre",
      content_style:
        "body { font-family: system-ui, -apple-system, sans-serif; font-size: 16px; line-height: 1.5; } p { margin: 0.5em 0; }",
      link_default_target: "_blank",
      link_title: false,
      relative_urls: false,
      remove_script_host: false,
      convert_urls: true,
      autoresize_bottom_margin: 24,
      setup: function (editor) {
        editor.on("change input undo redo", function () {
          editor.save();
        });
      },
    });

    var form = el.closest("form");
    if (form) {
      form.addEventListener("submit", function () {
        if (tinymce.get(TA_ID)) {
          tinymce.get(TA_ID).save();
        }
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
