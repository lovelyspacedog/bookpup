(function (BP) {
  "use strict";

  const INSTALL_DISMISS_KEY = "bookpupPwaInstallDismissed";
  let deferredInstall = null;

  function installBlocks() {
    return Array.from(document.querySelectorAll("[data-pwa-install]"));
  }

  function isStandalone() {
    return (
      window.matchMedia("(display-mode: standalone)").matches ||
      window.matchMedia("(display-mode: minimal-ui)").matches ||
      window.navigator.standalone === true
    );
  }

  function syncPwaInstallUi() {
    const hidden =
      isStandalone() || localStorage.getItem(INSTALL_DISMISS_KEY) === "1" || !deferredInstall;
    installBlocks().forEach((card) => {
      card.classList.toggle("hidden", hidden);
      const btn = card.querySelector("[data-pwa-install-btn]");
      if (btn) btn.disabled = !deferredInstall;
      const status = card.querySelector("[data-pwa-install-status]");
      if (!status) return;
      if (isStandalone()) {
        status.textContent = "Running from your home screen.";
        status.classList.remove("hidden");
      } else {
        status.textContent = "";
        status.classList.add("hidden");
      }
    });
  }

  async function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    try {
      await navigator.serviceWorker.register("/sw.js");
    } catch {
      /* optional */
    }
  }

  async function runInstallPrompt() {
    if (!deferredInstall) return;
    deferredInstall.prompt();
    try {
      await deferredInstall.userChoice;
    } catch {
      /* ignore */
    }
    deferredInstall = null;
    syncPwaInstallUi();
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

  document.addEventListener("click", (ev) => {
    const t = ev.target;
    if (!(t instanceof Element)) return;
    if (t.matches("[data-pwa-install-btn]")) {
      ev.preventDefault();
      void runInstallPrompt();
      return;
    }
    if (t.matches("[data-pwa-install-dismiss]")) {
      ev.preventDefault();
      localStorage.setItem(INSTALL_DISMISS_KEY, "1");
      syncPwaInstallUi();
    }
  });

  window.addEventListener("load", () => {
    void registerServiceWorker();
    syncPwaInstallUi();
  });

  BP.syncPwaInstallUi = syncPwaInstallUi;
  BP.isStandaloneDisplay = isStandalone;
})(window.BookPup);