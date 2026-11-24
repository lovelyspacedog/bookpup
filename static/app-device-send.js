(function (BP) {
  "use strict";

  const modal = document.getElementById("device-send-modal");
  const form = document.getElementById("device-send-form");
  const titleEl = document.getElementById("device-send-title");
  const formatSel = document.getElementById("device-send-format");
  const hintEl = document.getElementById("device-send-hint");
  const linkInput = document.getElementById("device-send-link");
  const kindleSteps = document.getElementById("device-send-kindle-steps");
  const kindleBtn = document.getElementById("device-send-kindle-btn");
  const msgEl = document.getElementById("device-send-msg");
  let activeItem = null;
  let formats = [];

  function closeDeviceSendModal() {
    modal?.classList.add("hidden");
    activeItem = null;
    formats = [];
    if (form) form.classList.remove("hidden");
    if (linkInput) linkInput.value = "";
    if (msgEl) {
      msgEl.textContent = "";
      msgEl.className = "bp-msg muted";
    }
    kindleSteps?.classList.add("hidden");
  }

  function updateFormatHint() {
    if (!formatSel || !hintEl) return;
    const hit = formats.find((f) => f.id === formatSel.value);
    hintEl.textContent = hit?.hint || "";
  }

  async function openDeviceSendModal(item) {
    if (!modal || !item?.id || !BP.isRegisteredItem?.(item)) return;
    activeItem = item;
    modal.classList.remove("hidden");
    if (titleEl) titleEl.textContent = item.title || item.filename || "Book";
    if (linkInput) linkInput.value = "";
    kindleSteps?.classList.add("hidden");
    if (msgEl) {
      msgEl.textContent = "Loading formats…";
      msgEl.className = "bp-msg muted";
    }
    try {
      const data = await BP.api("/api/library/" + encodeURIComponent(item.id) + "/sideload");
      formats = data.formats || [];
      if (!formatSel) return;
      formatSel.textContent = "";
      formats.forEach((f) => {
        const opt = document.createElement("option");
        opt.value = f.id;
        opt.textContent = f.label;
        formatSel.appendChild(opt);
      });
      formatSel.onchange = updateFormatHint;
      updateFormatHint();
      if (kindleBtn) {
        const ready = !!BP.state.sessionKindleSendReady;
        kindleBtn.classList.toggle("hidden", !ready);
        if (!ready && BP.state.sessionKindleSmtp && !BP.state.sessionKindleEmail) {
          if (msgEl) {
            msgEl.textContent = "Add your Send-to-Kindle address under Your tag to use Email to my Kindle.";
            msgEl.className = "bp-msg muted";
          }
        } else if (msgEl) {
          msgEl.textContent = "";
        }
      }
    } catch (err) {
      if (msgEl) {
        msgEl.textContent = err.message || "Could not load formats";
        msgEl.className = "bp-msg err";
      }
    }
  }

  async function createSideloadLink() {
    if (!activeItem || !formatSel) return;
    if (msgEl) {
      msgEl.textContent = "Creating link…";
      msgEl.className = "bp-msg muted";
    }
    try {
      const data = await BP.api(
        "/api/library/" + encodeURIComponent(activeItem.id) + "/sideload",
        {
          method: "POST",
          body: JSON.stringify({ format: formatSel.value }),
        }
      );
      if (linkInput) linkInput.value = data.download_url || "";
      const mins = Math.round((data.expires_in_seconds || 3600) / 60);
      if (msgEl) {
        msgEl.textContent =
          "Link ready — expires in about " + mins + " minutes (one download).";
        msgEl.className = "bp-msg";
      }
      kindleSteps?.classList.remove("hidden");
    } catch (err) {
      if (msgEl) {
        msgEl.textContent = err.message || "Could not create link";
        msgEl.className = "bp-msg err";
      }
    }
  }

  document.getElementById("device-send-modal-close")?.addEventListener("click", closeDeviceSendModal);
  document.getElementById("device-send-cancel")?.addEventListener("click", closeDeviceSendModal);
  form?.addEventListener("submit", (ev) => {
    ev.preventDefault();
    void createSideloadLink();
  });
  async function emailToKindle() {
    if (!activeItem || !formatSel) return;
    if (msgEl) {
      msgEl.textContent = "Sending…";
      msgEl.className = "bp-msg muted";
    }
    try {
      const data = await BP.api(
        "/api/library/" + encodeURIComponent(activeItem.id) + "/kindle-send",
        {
          method: "POST",
          body: JSON.stringify({ format: formatSel.value }),
        }
      );
      BP.showAppToast(
        "Kindle",
        "Emailed “" + (data.title || activeItem.title) + "” to " + (data.to || "your Kindle") + ".",
        "ok"
      );
      if (msgEl) {
        msgEl.textContent = "Sent — the book should appear on your Kindle after Amazon processes the email.";
        msgEl.className = "bp-msg";
      }
    } catch (err) {
      if (msgEl) {
        msgEl.textContent = err.message || "Could not send email";
        msgEl.className = "bp-msg err";
      }
    }
  }

  kindleBtn?.addEventListener("click", () => void emailToKindle());

  document.getElementById("device-send-copy")?.addEventListener("click", async () => {
    const url = linkInput?.value || "";
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      BP.showAppToast("Link", "Download link copied.", "ok");
    } catch {
      linkInput?.select();
      BP.showAppToast("Link", "Select the link and copy.", "info");
    }
  });

  BP.openDeviceSendModal = openDeviceSendModal;
  BP.closeDeviceSendModal = closeDeviceSendModal;
})(window.BookPup);