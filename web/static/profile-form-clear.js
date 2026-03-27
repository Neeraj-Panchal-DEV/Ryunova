(function () {
  var form = document.getElementById("profile-edit-form");
  var btn = document.getElementById("profile-form-clear");
  if (!form || !btn) return;

  var CLEAR_NAMES = [
    "display_name",
    "first_name",
    "last_name",
    "date_of_birth",
    "phone_national",
    "new_email_request",
    "admin_email",
    "job_title",
    "social_twitter",
    "social_linkedin",
    "social_github",
    "social_instagram",
    "social_other",
  ];

  btn.addEventListener("click", function () {
    if (!window.confirm("Clear all editable fields on this form? Account ID, public code, and sign-in email (read-only) are not cleared.")) {
      return;
    }
    CLEAR_NAMES.forEach(function (name) {
      var el = form.querySelector('[name="' + name + '"]');
      if (!el) return;
      el.value = "";
    });
    var dial = form.elements.namedItem("phone_country_dial");
    if (dial && dial.options && dial.options.length) {
      for (var j = 0; j < dial.options.length; j++) {
        if (dial.options[j].value === "+61") {
          dial.selectedIndex = j;
          break;
        }
      }
      if (dial.value !== "+61") dial.selectedIndex = 0;
    }
    var avatar = form.elements.namedItem("avatar");
    if (avatar) avatar.value = "";
  });
})();
