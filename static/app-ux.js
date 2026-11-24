(function (BP) {
  "use strict";

  const ONBOARD_KEY = "bookpupOnboardDismissed";
  const FETCH_COUNT_KEY = "bookpupCompletedFetches";
  const IRC_PANEL_KEY = "bookpupIrcPanelOpen";
  const NOTIFY_PROMPT_KEY = "bookpupNotifyPrompted";
  const SNIFF_HIDE_KENNEL_KEY = "bookpupSniffHideKennel";
  const GUIDE_PAGE_KEY = "bookpupGuidePage";

  function completedFetches() {
    try {
      return parseInt(localStorage.getItem(FETCH_COUNT_KEY) || "0", 10) || 0;
    } catch {
      return 0;
    }
  }

  function bumpCompletedFetches() {
    localStorage.setItem(FETCH_COUNT_KEY, String(completedFetches() + 1));
    syncIrcPanelDefault();
    syncOnboardUi();
  }

  function syncOnboardUi() {
    const banner = document.getElementById("onboard-banner");
    const checklist = document.getElementById("sniff-checklist");
    const dismissed = localStorage.getItem(ONBOARD_KEY) === "1";
    if (banner) banner.classList.toggle("hidden", dismissed);
    if (checklist) checklist.classList.toggle("hidden", dismissed && completedFetches() > 2);
  }

  function syncIrcPanelDefault() {
    BP.syncIrcPanelVisibility?.();
    const panel = document.getElementById("irc-panel");
    if (!panel || panel.classList.contains("hidden")) return;
    if (localStorage.getItem(IRC_PANEL_KEY) === "1") panel.open = true;
  }

  function openGuidePage(pageIndex) {
    sessionStorage.setItem(GUIDE_PAGE_KEY, String(pageIndex));
    const btn = BP.tabButton("guide");
    if (btn) BP.activateTab(btn);
    BP.loadGuide?.();
  }

  function bindOnboarding() {
    document.getElementById("onboard-dismiss")?.addEventListener("click", () => {
      localStorage.setItem(ONBOARD_KEY, "1");
      syncOnboardUi();
    });
    document.getElementById("onboard-guide")?.addEventListener("click", () => openGuidePage(1));
    const panel = document.getElementById("irc-panel");
    panel?.addEventListener("toggle", () => {
      if (panel.open) localStorage.setItem(IRC_PANEL_KEY, "1");
    });
  }

  function markSniffStep(stepId) {
    const el = document.getElementById(stepId);
    if (el) el.classList.add("bp-sniff-checklist__item--done");
  }

  function markUxSniffStarted() {
    markSniffStep("sniff-step-sniff");
    const panel = document.getElementById("irc-panel");
    if (panel) {
      panel.classList.remove("hidden");
      panel.open = true;
    }
  }

  function markUxFetchComplete() {
    markSniffStep("sniff-step-fetch");
    bumpCompletedFetches();
  }

  function markUxStashComplete() {
    markSniffStep("sniff-step-stash");
  }

  function maybePromptFetchNotify() {
    if (localStorage.getItem(NOTIFY_PROMPT_KEY) === "1") return;
    if (localStorage.getItem("bookpupNotifyDl") === "1") return;
    localStorage.setItem(NOTIFY_PROMPT_KEY, "1");
    BP.showAppToast(
      "Stay notified?",
      "Enable desktop alerts under Your tag when a fetch lands.",
      "info",
      [
        {
          label: "Your tag",
          onClick: () => {
            const btn = BP.tabButton("accounts");
            if (btn) BP.activateTab(btn);
            document.getElementById("notify-dl-enable")?.focus();
          },
        },
      ]
    );
  }

  function stagingExpiryLabel(job) {
    const ttl = BP.STAGING_TTL_SECONDS || 86400;
    const start = job?.updated_at || job?.created_at;
    if (!start) return "Stash before the catch spoils (~24 hours).";
    const left = Math.max(0, Math.floor(start + ttl - Date.now() / 1000));
    if (left < 3600) return `About ${Math.max(1, Math.floor(left / 60))}m left in staging.`;
    const h = Math.floor(left / 3600);
    return `About ${h}h left in staging (~24h total).`;
  }

  function revealDownloadFromJob(_job) {
    BP.goToFreshCatches?.();
  }

  let tossResolver = null;

  function openTossModal(title, opts) {
    const light = !!(opts && opts.light);
    return new Promise((resolve) => {
      const modal = document.getElementById("toss-modal");
      const phrases = [
        "bury the bone",
        "drop this bone",
        "not in my kennel",
        "scratch this fetch",
        "lose the trail",
        "bury it deep",
        "dig it out",
        "pass on this one",
      ];
      const phrase = phrases[Math.floor(Math.random() * phrases.length)];
      const display = document.getElementById("toss-phrase-display");
      const input = document.getElementById("toss-phrase-input");
      const phraseBlock = document.getElementById("toss-phrase-block");
      const lede = document.getElementById("toss-modal-lede");
      const msg = document.getElementById("toss-modal-msg");
      const titleEl = document.getElementById("toss-modal-title");
      const submitBtn = document.getElementById("toss-submit-btn");
      if (!modal) {
        resolve(false);
        return;
      }
      modal.dataset.mode = light ? "light" : "phrase";
      modal.dataset.phrase = phrase;
      if (titleEl) titleEl.textContent = light ? "Remove fresh catch" : "Toss from kennel";
      if (lede) {
        lede.textContent = light
          ? title
            ? `Remove “${title}” from Fresh catches? The file leaves your kennel.`
            : "Remove this fresh catch from your kennel?"
          : title
            ? `Toss “${title}” from your catalogued library?`
            : "Toss this from your kennel?";
      }
      if (phraseBlock) phraseBlock.classList.toggle("hidden", light);
      if (display) display.textContent = phrase;
      if (input) {
        input.value = "";
        input.required = !light;
      }
      if (submitBtn) submitBtn.textContent = light ? "Remove" : "Toss";
      if (msg) {
        msg.textContent = "";
        msg.className = "bp-msg muted";
      }
      modal.classList.remove("hidden");
      document.body.classList.add("bp-reader-open");
      if (light) submitBtn?.focus();
      else input?.focus();
      tossResolver = (ok) => {
        tossResolver = null;
        modal.classList.add("hidden");
        document.body.classList.remove("bp-reader-open");
        resolve(ok);
      };
    });
  }

  function bindTossModal() {
    const modal = document.getElementById("toss-modal");
    const form = document.getElementById("toss-form");
    document.getElementById("toss-modal-close")?.addEventListener("click", () => tossResolver?.(false));
    document.getElementById("toss-cancel-btn")?.addEventListener("click", () => tossResolver?.(false));
    modal?.addEventListener("click", (ev) => {
      if (ev.target === modal) tossResolver?.(false);
    });
    document.addEventListener("keydown", (ev) => {
      if (ev.key !== "Escape") return;
      if (!modal || modal.classList.contains("hidden") || !tossResolver) return;
      tossResolver(false);
    });
    form?.addEventListener("submit", (ev) => {
      ev.preventDefault();
      const light = modal?.dataset.mode === "light";
      if (light) {
        tossResolver?.(true);
        return;
      }
      const input = document.getElementById("toss-phrase-input");
      const expected = modal?.dataset.phrase || "";
      const ok = input && input.value === expected;
      const msg = document.getElementById("toss-modal-msg");
      if (!ok && msg) {
        msg.textContent = "Phrase does not match.";
        msg.className = "bp-msg err";
        return;
      }
      tossResolver?.(!!ok);
    });
  }

  function bindHeaderZipWeather() {
    const input = document.getElementById("bp-header-zip");
    if (!input || input.dataset.bound === "1") return;
    input.dataset.bound = "1";
    const prompt = document.getElementById("bp-header-zip-prompt");
    const out = document.getElementById("bp-header-weather");
    const versionRow = document.getElementById("bp-header-version");
    const zipRe = /^\d{5}(-\d{4})?$/;
    let forecast = null;
    let unit = "F";
    let clickTimer = null;

    function formatForecastLine() {
      if (!forecast || !out) return;
      const temp = unit === "C" ? forecast.temp_c : forecast.temp_f;
      const sign = temp.startsWith("-") ? "" : "+";
      out.textContent = forecast.city + ": " + forecast.emoji + "  " + sign + temp + "°" + unit;
    }

    function showForecast(data) {
      forecast = {
        city: data.city,
        emoji: data.emoji,
        temp_f: data.temp_f,
        temp_c: data.temp_c,
      };
      unit = "F";
      prompt?.classList.add("hidden");
      input.classList.add("hidden");
      versionRow?.classList.add("bp-header-version--forecast");
      out?.classList.remove("hidden");
      out?.setAttribute("role", "button");
      out?.setAttribute("tabindex", "0");
      out?.setAttribute(
        "title",
        "Click to switch °F / °C. Double-click to enter a new ZIP."
      );
      formatForecastLine();
    }

    function resetHeaderWeather() {
      forecast = null;
      unit = "F";
      prompt?.classList.remove("hidden");
      input.classList.remove("hidden");
      input.value = "";
      input.disabled = false;
      versionRow?.classList.remove("bp-header-version--forecast");
      out?.classList.add("hidden");
      out?.removeAttribute("role");
      out?.removeAttribute("tabindex");
      out?.removeAttribute("title");
      out.textContent = "";
      input.focus();
    }

    input.addEventListener("keydown", async (ev) => {
      if (ev.key !== "Enter") return;
      ev.preventDefault();
      const raw = input.value.trim();
      if (!zipRe.test(raw)) return;
      const zip = raw.slice(0, 5);
      input.disabled = true;
      try {
        const res = await fetch("/api/weather?zip=" + encodeURIComponent(zip));
        const data = res.ok ? await res.json() : null;
        if (!data || !data.city || !data.temp_f || !data.temp_c) return;
        showForecast(data);
      } catch {
        /* offline */
      } finally {
        input.disabled = false;
      }
    });

    out?.addEventListener("click", () => {
      if (!forecast || out.classList.contains("hidden")) return;
      if (clickTimer) clearTimeout(clickTimer);
      clickTimer = setTimeout(() => {
        clickTimer = null;
        unit = unit === "F" ? "C" : "F";
        formatForecastLine();
      }, 260);
    });

    out?.addEventListener("dblclick", (ev) => {
      ev.preventDefault();
      if (clickTimer) {
        clearTimeout(clickTimer);
        clickTimer = null;
      }
      resetHeaderWeather();
    });

    out?.addEventListener("keydown", (ev) => {
      if (!forecast || out.classList.contains("hidden")) return;
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        unit = unit === "F" ? "C" : "F";
        formatForecastLine();
      }
    });
  }

  function bindSniffHideKennelFilter() {
    const el = document.getElementById("sniff-hide-kennel");
    if (!el) return;
    if (typeof BP.bindSniffFilter === "function") {
      BP.bindSniffFilter("sniff-hide-kennel", SNIFF_HIDE_KENNEL_KEY);
    }
  }

  function initUx() {
    bindOnboarding();
    bindTossModal();
    bindHeaderZipWeather();
    bindSniffHideKennelFilter();
    syncOnboardUi();
    syncIrcPanelDefault();
    document.getElementById("fresh-empty-sniff")?.addEventListener("click", () => {
      const btn = BP.tabButton("search");
      if (btn) BP.activateTab(btn);
    });
    document.getElementById("fresh-empty-upload")?.addEventListener("click", () => {
      BP.goToFreshCatches();
      document.getElementById("fresh-upload-btn")?.click();
    });
  }

  BP.markUxSniffStarted = markUxSniffStarted;
  BP.markUxFetchComplete = markUxFetchComplete;
  BP.markUxStashComplete = markUxStashComplete;
  BP.maybePromptFetchNotify = maybePromptFetchNotify;
  BP.revealDownloadFromJob = revealDownloadFromJob;
  BP.stagingExpiryLabel = stagingExpiryLabel;
  BP.openTossModal = openTossModal;
  BP.syncOnboardUi = syncOnboardUi;
  BP.SNIFF_HIDE_KENNEL_KEY = SNIFF_HIDE_KENNEL_KEY;
  BP.initUx = initUx;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initUx);
  } else {
    initUx();
  }
})(window.BookPup);