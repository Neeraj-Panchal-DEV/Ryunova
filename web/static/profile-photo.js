(function () {
  "use strict";

  var root = document.querySelector("[data-profile-photo]");
  if (!root) return;

  var fileInput = document.getElementById("profile-avatar-file");
  var pickBtn = document.getElementById("profile-avatar-pick");
  var preview = document.getElementById("profile-avatar-preview");
  var openCam = document.getElementById("profile-camera-open");
  var modal = document.getElementById("profile-camera-modal");
  var video = document.getElementById("profile-camera-video");
  var canvas = document.getElementById("profile-camera-canvas");
  var capBtn = document.getElementById("profile-camera-capture");
  var errEl = document.getElementById("profile-camera-error");
  var stream = null;
  var videoReadyCleanup = null;

  var cropModal = document.getElementById("profile-crop-modal");
  var cropImg = document.getElementById("profile-crop-img");
  var cropApply = document.getElementById("profile-crop-apply");
  var cropperInstance = null;
  var cropObjectUrl = null;

  function showErr(msg) {
    if (!errEl) return;
    errEl.textContent = msg;
    errEl.hidden = !msg;
  }

  function setPreviewFromFile(file) {
    if (!preview || !file || !file.type || file.type.indexOf("image/") !== 0) return;
    var url = URL.createObjectURL(file);
    if (preview.tagName === "IMG") {
      preview.src = url;
    } else {
      var img = document.createElement("img");
      img.id = "profile-avatar-preview";
      img.className = "profile-page__preview";
      img.width = 120;
      img.height = 120;
      img.alt = "";
      img.src = url;
      preview.replaceWith(img);
      preview = img;
    }
  }

  function destroyCropper() {
    if (cropperInstance) {
      cropperInstance.destroy();
      cropperInstance = null;
    }
  }

  function closeCropModal(clearFileInput) {
    destroyCropper();
    if (cropObjectUrl) {
      URL.revokeObjectURL(cropObjectUrl);
      cropObjectUrl = null;
    }
    if (cropImg) {
      cropImg.removeAttribute("src");
      cropImg.onload = null;
      cropImg.onerror = null;
    }
    if (cropModal) {
      cropModal.hidden = true;
      cropModal.setAttribute("aria-hidden", "true");
    }
    document.body.classList.remove("profile-crop-modal--open");
    if (clearFileInput && fileInput) {
      fileInput.value = "";
    }
  }

  function startCropperOnImage() {
    if (typeof window.Cropper === "undefined") {
      window.alert("Photo cropper could not load. Check that /static/vendor/cropper/cropper.min.js is available, then refresh.");
      closeCropModal(true);
      return;
    }
    if (!cropImg) return;
    destroyCropper();
    cropperInstance = new window.Cropper(cropImg, {
      aspectRatio: 1,
      viewMode: 1,
      dragMode: "move",
      background: false,
      responsive: true,
      autoCropArea: 0.85,
      minCropBoxWidth: 48,
      minCropBoxHeight: 48,
      checkOrientation: false,
    });
  }

  function openCropModal(file) {
    if (!cropModal || !cropImg || !file || !file.type || file.type.indexOf("image/") !== 0) return;
    destroyCropper();
    if (cropObjectUrl) {
      URL.revokeObjectURL(cropObjectUrl);
      cropObjectUrl = null;
    }
    cropObjectUrl = URL.createObjectURL(file);

    var loadHandled = false;
    function whenLoaded() {
      if (loadHandled) return;
      loadHandled = true;
      cropImg.onload = null;
      cropImg.onerror = null;
      /* Cropper measures the container; wait until the modal is visible and laid out. */
      window.requestAnimationFrame(function () {
        window.requestAnimationFrame(function () {
          startCropperOnImage();
        });
      });
    }

    cropImg.onload = whenLoaded;
    cropImg.onerror = function () {
      cropImg.onload = null;
      cropImg.onerror = null;
      closeCropModal(true);
    };
    cropModal.hidden = false;
    cropModal.removeAttribute("hidden");
    cropModal.setAttribute("aria-hidden", "false");
    document.body.classList.add("profile-crop-modal--open");
    cropImg.src = cropObjectUrl;
    if (cropImg.complete && cropImg.naturalWidth) {
      whenLoaded();
    }
  }

  if (pickBtn && fileInput) {
    pickBtn.addEventListener("click", function () {
      fileInput.click();
    });
    fileInput.addEventListener("change", function () {
      var f = fileInput.files && fileInput.files[0];
      if (!f) return;
      /* Do not clear the input here — some browsers invalidate the File when the value is cleared immediately. */
      openCropModal(f);
    });
  }

  if (cropModal) {
    cropModal.querySelectorAll("[data-profile-crop-close]").forEach(function (el) {
      el.addEventListener("click", function (e) {
        e.preventDefault();
        closeCropModal(true);
      });
    });
  }

  if (cropApply && fileInput) {
    cropApply.addEventListener("click", function (e) {
      e.preventDefault();
      if (!cropperInstance) return;
      var canvas = cropperInstance.getCroppedCanvas({
        width: 512,
        height: 512,
        imageSmoothingQuality: "high",
      });
      if (!canvas) return;
      canvas.toBlob(
        function (blob) {
          if (!blob) return;
          var file = new File([blob], "profile-avatar.jpg", { type: "image/jpeg" });
          var dt = new DataTransfer();
          dt.items.add(file);
          fileInput.files = dt.files;
          setPreviewFromFile(file);
          closeCropModal(false);
        },
        "image/jpeg",
        0.92
      );
    });
  }

  function stopStream() {
    detachVideoReadyListeners();
    if (stream) {
      stream.getTracks().forEach(function (t) {
        t.stop();
      });
      stream = null;
    }
    if (video) {
      video.srcObject = null;
    }
  }

  function updateCaptureEnabled() {
    if (!capBtn || !video) return;
    var ok = !!(video.srcObject && video.videoWidth > 0 && video.videoHeight > 0);
    capBtn.disabled = !ok;
  }

  function detachVideoReadyListeners() {
    if (typeof videoReadyCleanup === "function") {
      videoReadyCleanup();
      videoReadyCleanup = null;
    }
  }

  function attachVideoReadyListeners() {
    detachVideoReadyListeners();
    if (!video) return;
    var onReady = function () {
      updateCaptureEnabled();
    };
    video.addEventListener("loadedmetadata", onReady);
    video.addEventListener("loadeddata", onReady);
    video.addEventListener("playing", onReady);
    video.addEventListener("canplay", onReady);
    videoReadyCleanup = function () {
      video.removeEventListener("loadedmetadata", onReady);
      video.removeEventListener("loadeddata", onReady);
      video.removeEventListener("playing", onReady);
      video.removeEventListener("canplay", onReady);
    };
  }

  function getCameraStream() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return Promise.reject(new Error("unsupported"));
    }
    var attempts = [
      { video: { facingMode: { ideal: "user" } }, audio: false },
      { video: { facingMode: "user" }, audio: false },
      { video: true, audio: false },
    ];
    function tryAt(i) {
      if (i >= attempts.length) {
        return Promise.reject(new Error("constraints"));
      }
      return navigator.mediaDevices.getUserMedia(attempts[i]).catch(function () {
        return tryAt(i + 1);
      });
    }
    return tryAt(0);
  }

  function closeCameraModal() {
    if (!modal) return;
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
    stopStream();
    showErr("");
    if (capBtn) capBtn.disabled = true;
    document.body.classList.remove("profile-camera-modal--open");
  }

  function openCameraModal() {
    if (!modal || !video) return;
    showErr("");
    modal.hidden = false;
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("profile-camera-modal--open");
    if (capBtn) capBtn.disabled = true;

    getCameraStream()
      .then(function (s) {
        stream = s;
        video.srcObject = s;
        attachVideoReadyListeners();
        updateCaptureEnabled();
        var playPromise = video.play();
        if (playPromise !== undefined && typeof playPromise.then === "function") {
          playPromise.then(updateCaptureEnabled).catch(function () {
            updateCaptureEnabled();
          });
        }
      })
      .catch(function () {
        showErr("Could not access the camera. Check permissions or use “Choose file”.");
      });
  }

  if (openCam) {
    openCam.addEventListener("click", function (e) {
      e.preventDefault();
      openCameraModal();
    });
  }

  if (modal) {
    modal.querySelectorAll("[data-profile-camera-close]").forEach(function (el) {
      el.addEventListener("click", function (e) {
        e.preventDefault();
        closeCameraModal();
      });
    });
  }

  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Escape") return;
    if (cropModal && !cropModal.hidden) {
      closeCropModal(true);
      return;
    }
    if (modal && !modal.hidden) {
      closeCameraModal();
    }
  });

  if (capBtn && canvas && video && fileInput) {
    capBtn.addEventListener("click", function (e) {
      e.preventDefault();
      var w = video.videoWidth;
      var h = video.videoHeight;
      if (!w || !h) {
        showErr("Video not ready yet. Wait for the preview or try again.");
        return;
      }
      canvas.width = w;
      canvas.height = h;
      var ctx = canvas.getContext("2d");
      ctx.drawImage(video, 0, 0, w, h);
      canvas.toBlob(
        function (blob) {
          if (!blob) {
            showErr("Could not capture image.");
            return;
          }
          var file = new File([blob], "profile-camera.jpg", { type: "image/jpeg" });
          closeCameraModal();
          openCropModal(file);
        },
        "image/jpeg",
        0.92
      );
    });
  }
})();
