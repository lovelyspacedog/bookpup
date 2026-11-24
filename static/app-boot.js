(function (BP) {
  "use strict";
  const CSRF = BP.CSRF;
  const COVER_MAX_BYTES = BP.COVER_MAX_BYTES;
  async function boot() {
    try {
      const cfg = await BP.fetchPublic("/api/config");
      const loginUser = document.getElementById("login-user");
      if (cfg && cfg.username && loginUser && !loginUser.value) {
        loginUser.value = cfg.username;
      }
    } catch (_e) {
      /* offline */
    }
    try {
      const caps = await BP.fetchPublic("/api/capabilities");
      BP.state.coverImageSearchEnabled = !!(caps && caps.cover_image_search);
    } catch (_e) {
      BP.state.coverImageSearchEnabled = false;
    }
    const imgBtns = [
      document.getElementById("register-cover-images-btn"),
      document.getElementById("cover-modal-images-btn"),
    ];
    if (!BP.state.coverImageSearchEnabled) {
      imgBtns.forEach((btn) => {
        if (btn) btn.disabled = true;
      });
    }
    const token = sessionStorage.getItem("bookpupToken");
    if (token) {
      BP.state.authHeader = "Bearer " + token;
      try {
        await BP.api("/api/queue");
        BP.showApp();
        BP.scheduleQueueRefresh(8000);
        return;
      } catch (_e) {
        if (!navigator.onLine && BP.offlineBooks) {
          try {
            const metas = await BP.offlineBooks.listMeta();
            if (metas.length) {
              BP.state.offlineOnly = true;
              document.getElementById("login-screen")?.classList.add("hidden");
              document.getElementById("app-shell")?.classList.remove("hidden");
              const libTab = BP.tabButton?.("library");
              if (libTab) BP.activateTab?.(libTab);
              await BP.loadLibrary?.();
              BP.showAppToast?.(
                "Offline",
                "Server unreachable — opening books kept on this device.",
                "info"
              );
              return;
            }
          } catch {
            /* fall through */
          }
        }
        BP.showLogin("Your session wandered off. Come inside again.");
        return;
      }
    }
    BP.showLogin();
  }

  BP.bindSearchHistoryUx();
  BP.renderSearchHistoryUi();
  boot();
  // exports
  BP.boot = boot;
})(window.BookPup);
