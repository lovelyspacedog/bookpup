(function (BP) {
  "use strict";

  const INSTALL_DISMISS_KEY = "bookpupPwaInstallDismissed";
  let deferredInstall = null;

  function isStandalone() {
    return (
      window.matchMedia("(display-mode: standalone)").matches ||
      window.matchMedia("(display-mode: minimal-ui)").matches ||
      window.navigator.standalone === true
    );
  }

  function syncPwaInstallUi() {
    const card = document.getElementById("pwa-install-card");
    const btn = document.getElementById("pwa-install-btn");
    const status = document.getElementById("pwa-install-status");
    if (!card) return;
    const hidden =
      isStandalone() || localStorage.getItem(INSTALL_DISMISS_KEY) === "1" || !deferredInstall;
    card.classList.toggle("hidden", hidden);
    if (btn) btn.disabled = !deferredInstall;
    if (status && isStandalone()) {
      status.textContent = "Running from your home screen.";
      status.classList.remove("hidden");
    }
  }

  async function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    try {
      await navigator.serviceWorker.register("/sw.js");
    } catch {
      /* optional */
    }
  }

  window.addEventListener("beforeinstallprompt", (ev) => {
    ev.preventDefault();
    deferredInstall = ev;
    syncPwaInstallUi();
  });

  window.addEventListener("appinstalled", () => {
    deferredInstall = null;
    syncPwaInstallUi();
  });

  document.getElementById("pwa-install-btn")?.addEventListener("click", async () => {
    if (!deferredInstall) return;
    deferredInstall.prompt();
    try {
      await deferredInstall.userChoice;
    } catch {
      /* ignore */
    }
    deferredInstall = null;
    syncPwaInstallUi();
  });

  document.getElementById("pwa-install-dismiss")?.addEventListener("click", () => {
    localStorage.setItem(INSTALL_DISMISS_KEY, "1");
    syncPwaInstallUi();
  });

  window.addEventListener("load", () => {
    void registerServiceWorker();
    syncPwaInstallUi();
  });

  BP.syncPwaInstallUi = syncPwaInstallUi;
  BP.isStandaloneDisplay = isStandalone;
})(window.BookPup);