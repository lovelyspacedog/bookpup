(function (BP) {
  "use strict";

  const COMPLETE_KEY = "bookpupWalkTrailComplete";
  const ACTIVE_JOB = "walk-trail-practice";

  let active = false;
  let stepIndex = 0;
  let tutorialQuery = "";
  let tutorialTitle = "";
  let tutorialItemId = "";
  let mockIrcTimer = null;
  let stepAdvanceTimer = null;
  let registerSnapshot = null;
  let fetchDone = false;
  let fetchError = "";
  let focusTargetEl = null;
  const autoAdvanceFired = new Set();

  function fetchStepIndex() {
    return steps.findIndex((s) => s.id === "fetch");
  }

  function advanceFromFetch() {
    updateTipChrome();
    const idx = fetchStepIndex();
    if (stepIndex < idx) return;
    if (currentStep()?.id !== "fetch") return;
    if (autoAdvanceFired.has("fetch-done")) return;
    autoAdvanceFired.add("fetch-done");
    setTimeout(() => void goNext(), 250);
  }

  function practiceRow() {
    if (BP.state.walkTrailPracticeRow) return BP.state.walkTrailPracticeRow;
    const tr = document.querySelector("tr[data-walk-trail-row]");
    if (!tr) return null;
    const title = tr.querySelector(".bp-sniff-title-text")?.textContent?.trim() || tutorialTitle;
    return {
      walk_trail: true,
      title,
      command: "!TrailBot " + title,
      server: "TrailBot",
      network: "IRCHighway",
      irc_target: "irchighway:ebooks",
    };
  }

  const root = () => document.getElementById("walk-trail-root");
  const tipEl = () => document.getElementById("walk-trail-tip");
  const spotEl = () => document.getElementById("walk-trail-spot");

  function isComplete() {
    try {
      return localStorage.getItem(COMPLETE_KEY) === "1";
    } catch {
      return false;
    }
  }

  function markComplete() {
    try {
      localStorage.setItem(COMPLETE_KEY, "1");
    } catch {
      /* ignore */
    }
    BP.syncWalkTrailEntry?.();
  }

  function resetComplete() {
    try {
      localStorage.removeItem(COMPLETE_KEY);
    } catch {
      /* ignore */
    }
    BP.syncWalkTrailEntry?.();
  }

  function tutorialFilename(query) {
    const base = String(query || "practice").trim() || "practice";
    return base.toLowerCase().endsWith(".mobi") ? base : base + ".mobi";
  }

  function buildDecoyRows(query) {
    const title = tutorialFilename(query);
    return [
      {
        server: "TrailBot",
        title: title,
        size_hint: "9 KB",
        command: "!TrailBot " + title,
        network: "IRCHighway",
        irc_target: "irchighway:ebooks",
        walk_trail: true,
      },
      {
        server: "MockServ",
        title: "Grass For His Pillow.epub",
        size_hint: "142 KB",
        command: "!bald Grass For His Pillow.epub",
        network: "IRCHighway",
        irc_target: "irchighway:ebooks",
      },
      {
        server: "MockServ",
        title: "Hamlet [retail].epub",
        size_hint: "512 KB",
        command: "!DukeLupus Hamlet.epub",
        network: "IRCHighway",
        irc_target: "irchighway:ebooks",
      },
    ];
  }

  function pushMockIrcLine(text, dir) {
    const ev = {
      id: (BP.state.ircAfterId || 0) + 1,
      ts: Date.now() / 1000,
      text,
      dir: dir || "out",
      target: "#ebooks",
      kind: "chat",
    };
    BP.state.ircAfterId = ev.id;
    if (!BP.state.ircEvents) BP.state.ircEvents = [];
    BP.state.ircEvents.push(ev);
    const panel = document.getElementById("irc-panel");
    if (panel) {
      panel.classList.remove("hidden");
      panel.open = true;
    }
    const feed = document.getElementById("irc-feed");
    if (feed) {
      const div = document.createElement("div");
      div.className = "bp-irc-line bp-irc-line--" + (ev.dir || "in");
      const meta = new Date().toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
      div.innerHTML =
        '<span class="bp-irc-meta">' + BP.escapeHtml(meta) + "</span>" + BP.escapeHtml((ev.target ? "@" + ev.target + " " : "") + text);
      feed.appendChild(div);
      feed.scrollTop = feed.scrollHeight;
    }
    BP.syncIrcPanelVisibility?.();
  }

  function clearMockIrcTimer() {
    if (mockIrcTimer) {
      clearTimeout(mockIrcTimer);
      mockIrcTimer = null;
    }
  }

  function runMockIrcScript(query) {
    clearMockIrcTimer();
    pushMockIrcLine("@search " + query, "out");
    mockIrcTimer = setTimeout(() => pushMockIrcLine("SearchBot: sniffing catalogue…", "in"), 600);
    setTimeout(() => pushMockIrcLine("SearchBot: 3 matches (practice)", "in"), 1400);
    setTimeout(() => pushMockIrcLine("Sniff finished: practice results ready", "in"), 2200);
  }

  const MOBILE_TIP_MQ = window.matchMedia("(max-width: 640px)");

  function tabBarInsetPx() {
    const shell = document.querySelector(".bp-tabbar-shell");
    if (!shell || !MOBILE_TIP_MQ.matches) return 0;
    return Math.ceil(shell.getBoundingClientRect().height || 0);
  }

  function clearFocusTarget() {
    if (focusTargetEl) {
      focusTargetEl.classList.remove("bp-walk-trail-focus");
      focusTargetEl = null;
    }
  }

  function markFocusTarget(target) {
    clearFocusTarget();
    if (!target) return;
    focusTargetEl = target;
    target.classList.add("bp-walk-trail-focus");
  }

  function resolveStepTarget(st) {
    if (!st) return null;
    if (st.id === "welcome") {
      if (MOBILE_TIP_MQ.matches) return document.querySelector("#search-form");
      return document.querySelector("#tab-search") || document.querySelector("#search-form");
    }
    if (st.id === "fetch") {
      return (
        document.querySelector("tr[data-walk-trail-row] .dl-row") ||
        document.querySelector("tr[data-walk-trail-row]") ||
        document.querySelector("#results-wrap")
      );
    }
    if (st.id === "kennel") {
      const libOpen = document.getElementById("panel-library")?.classList.contains("active");
      if (libOpen && tutorialItemId) {
        const card = document.querySelector('.bp-lib-card[data-lib-item-id="' + tutorialItemId + '"]');
        return card || document.getElementById("lib-section-downloads");
      }
      if (libOpen) return document.getElementById("lib-section-downloads");
      return document.querySelector("#tab-library");
    }
    if (st.id === "tag") {
      const modal = document.getElementById("register-modal");
      if (modal && !modal.classList.contains("hidden")) {
        return document.getElementById("register-submit") || document.getElementById("reg-title");
      }
      if (tutorialItemId) {
        const card = document.querySelector('.bp-lib-card[data-lib-item-id="' + tutorialItemId + '"]');
        return card?.querySelector(".register") || card || document.getElementById("lib-section-downloads");
      }
      return document.getElementById("lib-section-downloads");
    }
    return st.selector ? document.querySelector(st.selector) : null;
  }

  function layoutSpotRing(target) {
    const spot = spotEl();
    if (!spot || !target) {
      spot?.classList.add("hidden");
      return;
    }
    const pad = 6;
    const rect = target.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) {
      spot.classList.add("hidden");
      return;
    }
    spot.classList.remove("hidden");
    spot.style.top = rect.top - pad + "px";
    spot.style.left = rect.left - pad + "px";
    spot.style.width = rect.width + pad * 2 + "px";
    spot.style.height = rect.height + pad * 2 + "px";
  }

  let relayoutToken = 0;
  function scheduleWalkTrailLayout(target, placement) {
    layoutSpotRing(target);
    positionTip(target, placement);
    const token = ++relayoutToken;
    const run = () => {
      if (!active || token !== relayoutToken) return;
      layoutSpotRing(target);
      positionTip(target, placement);
    };
    requestAnimationFrame(run);
    [50, 150, 350, 700].forEach((ms) => setTimeout(run, ms));
  }

  function coachTopBandPx() {
    const tip = tipEl();
    if (!tip || tip.classList.contains("hidden") || !tip.classList.contains("bp-walk-trail-tip--dock-top")) return 0;
    return Math.ceil(tip.getBoundingClientRect().bottom) + 12;
  }

  function scrollRevealBelowTopCoach(target) {
    if (!target || !MOBILE_TIP_MQ.matches) return;
    const band = coachTopBandPx();
    const margin = 12;
    const rect = target.getBoundingClientRect();
    if (band > 0) {
      if (rect.top < band) {
        window.scrollBy({ top: rect.top - band, behavior: "instant" });
        return;
      }
    }
    const floor = band > 0 ? band : margin;
    if (rect.bottom > window.innerHeight - margin) {
      window.scrollBy({ top: rect.bottom - (window.innerHeight - margin), behavior: "instant" });
    } else if (rect.top < floor) {
      window.scrollBy({ top: rect.top - floor, behavior: "instant" });
    }
  }

  function defaultScrollTarget(target, st) {
    if (!target) return;
    if (st?.id === "sniff" && BP.state.walkTrailSearchDone) return;
    try {
      const block =
        st?.id === "den" || st?.id === "kennel" ? "start" : MOBILE_TIP_MQ.matches ? "nearest" : "center";
      target.scrollIntoView({ block, inline: "nearest", behavior: "instant" });
    } catch {
      /* ignore */
    }
  }

  function placeSpot(target) {
    if (!target) {
      layoutSpotRing(null);
      return;
    }
    const st = currentStep();
    const dockTopCoach = MOBILE_TIP_MQ.matches && st?.mobileTip === "top";
    if (dockTopCoach) {
      scheduleWalkTrailLayout(target, st?.placement);
      requestAnimationFrame(() => {
        if (!active || target !== resolveStepTarget(currentStep())) return;
        scrollRevealBelowTopCoach(target);
        scheduleWalkTrailLayout(target, st?.placement);
      });
      return;
    }
    defaultScrollTarget(target, st);
    scheduleWalkTrailLayout(target, st?.placement);
  }

  function ensureDenPanelOpen() {
    const panel = document.getElementById("irc-panel");
    if (!panel) return;
    panel.classList.remove("hidden");
    panel.open = true;
  }

  function ensureDenMockVisible() {
    const feed = document.getElementById("irc-feed");
    if (!feed) return;
    if (feed.children.length >= 2) return;
    runMockIrcScript(tutorialQuery || "practice");
  }

  function positionTip(target, placement) {
    const tip = tipEl();
    if (!tip) return;
    const margin = 12;
    const st = currentStep();
    tip.dataset.placement = placement || "bottom";
    const dockMobile = MOBILE_TIP_MQ.matches;
    const dockTop = dockMobile && st?.mobileTip === "top";
    tip.classList.toggle("bp-walk-trail-tip--dock", dockMobile && !dockTop);
    tip.classList.toggle("bp-walk-trail-tip--dock-top", dockTop);
    if (dockMobile) {
      tip.style.top = "";
      tip.style.left = "";
      tip.style.right = "";
      tip.style.bottom = "";
      tip.style.transform = "";
      tip.style.setProperty("--bp-walk-trail-tab-inset", tabBarInsetPx() + "px");
      return;
    }
    tip.style.setProperty("--bp-walk-trail-tab-inset", "0px");
    if (!target) {
      tip.style.top = "50%";
      tip.style.left = "50%";
      tip.style.right = "";
      tip.style.bottom = "";
      tip.style.transform = "translate(-50%, -50%)";
      return;
    }
    const rect = target.getBoundingClientRect();
    tip.style.transform = "";
    tip.style.right = "";
    tip.style.bottom = "";
    const tipRect = tip.getBoundingClientRect();
    let top;
    let left;
    if (placement === "top") {
      top = rect.top - tipRect.height - margin;
      left = rect.left + Math.max(0, (rect.width - tipRect.width) / 2);
    } else if (placement === "left") {
      top = rect.top + Math.max(0, (rect.height - tipRect.height) / 2);
      left = rect.left - tipRect.width - margin;
    } else {
      top = rect.bottom + margin;
      left = rect.left + Math.max(0, (rect.width - tipRect.width) / 2);
    }
    const pad = 8;
    const maxTop = window.innerHeight - tipRect.height - pad;
    const maxLeft = window.innerWidth - tipRect.width - pad;
    top = Math.min(Math.max(pad, top), Math.max(pad, maxTop));
    left = Math.min(Math.max(pad, left), Math.max(pad, maxLeft));
    tip.style.top = top + "px";
    tip.style.left = left + "px";
  }

  const steps = [
    {
      id: "welcome",
      title: "Walk the Trail",
      body: "A hands-on practice sniff and fetch — no real IRC bots. You choose the title; we fake the chat.",
      selector: "#tab-search",
      placement: "bottom",
      advance: "manual",
    },
    {
      id: "query",
      title: "What to sniff for",
      body: "Type any author or title you like (at least 2 characters). This becomes your practice .mobi name.",
      selector: "#query",
      placement: "bottom",
      advance: "input",
      inputMin: 2,
    },
    {
      id: "channel",
      title: "Sniff source",
      body: "Keep Main trail selected — best first stop for novels and MOBI/EPUB on IRCHighway #ebooks.",
      selector: "#channel",
      placement: "bottom",
      advance: "channel",
      channel: "irchighway:ebooks",
    },
    {
      id: "sniff",
      title: "Sniff on IRC",
      body: "Press the button to run a practice sniff. Den chatter will show fake status lines.",
      selector: "#search-submit-btn",
      placement: "top",
      advance: "search-done",
    },
    {
      id: "den",
      title: "Den chatter",
      body: "During real sniffs, bot lines stream here. For practice we added fake @search status in the box below. Tap Next when you have read them.",
      selector: "#irc-panel",
      placement: "top",
      mobileTip: "top",
      advance: "manual",
    },
    {
      id: "filter",
      title: "Filter results",
      body: "Optional: narrow the table (EPUB only, hide bots, etc.). Filters only change what you see.",
      selector: "#filter",
      placement: "bottom",
      mobileTip: "top",
      advance: "manual",
    },
    {
      id: "fetch",
      title: "Fetch your row",
      body: "Click Fetch on the row that matches your practice .mobi (not the decoy EPUBs).",
      selector: "tr[data-walk-trail-row]",
      placement: "top",
      advance: "fetch-done",
    },
    {
      id: "queue",
      title: "Fetch queue",
      body: "Real fetches show progress here. Practice uses a shortcut — peek at this tab, then tap Next.",
      selector: "#tab-queue",
      placement: "bottom",
      mobileTip: "top",
      advance: "manual",
    },
    {
      id: "kennel",
      title: "Fresh catches",
      body: "Your practice .mobi is in Fresh catches below. Scroll until you see it, then tap Next.",
      selector: "#tab-library",
      placement: "top",
      mobileTip: "top",
      advance: "kennel-open",
    },
    {
      id: "tag",
      title: "Tag this book",
      body: "Tap Tag on your practice catch. Change at least one field (title, author, or tags), then save.",
      selector: "#lib-items-downloads",
      placement: "top",
      mobileTip: "top",
      advance: "tag-saved",
    },
    {
      id: "catalog",
      title: "Catalogued bones",
      body: "After you tag, the book moves here and counts toward your storage quota.",
      selector: "#lib-section-calibre",
      placement: "top",
      advance: "manual",
    },
    {
      id: "pack",
      title: "Pack chat",
      body: "Household chat lives here — not IRC Den chatter. We opened Pack chat; tap Next when you are ready.",
      selector: "#tab-pack",
      placement: "bottom",
      mobileTip: "top",
      advance: "pack-open",
    },
    {
      id: "pack-house",
      title: "Pack channel",
      body: "Pack chat · everyone reaches the whole household. Pups in the sidebar are for private messages.",
      selector: "#pack-chat-mode-pack",
      placement: "bottom",
      mobileTip: "top",
      advance: "manual",
    },
    {
      id: "pack-bots",
      title: "BugBot & FeatureCat",
      body: "Open BugBot or FeatureCat in the sidebar to report bugs or ideas. Admins see them on Pack roster. Type clear in a bot thread to reset.",
      selector: "#pack-chat-sidebar-hint",
      placement: "bottom",
      mobileTip: "top",
      advance: "manual",
    },
    {
      id: "cleanup",
      title: "Remove practice book?",
      body: "Optional: toss the tutorial file so it does not stay on your shelf.",
      selector: null,
      placement: "top",
      advance: "cleanup",
    },
    {
      id: "done",
      title: "Trail complete",
      body: "Opening Pup guide page 12 for Pack chat and everyday habits.",
      selector: null,
      placement: "top",
      advance: "finish",
    },
  ];

  function currentStep() {
    return steps[stepIndex];
  }

  function canAdvanceManual() {
    const st = currentStep();
    if (!st) return false;
    if (st.advance === "manual") return true;
    if (st.advance === "input") {
      const el = document.getElementById("query");
      return el && String(el.value || "").trim().length >= (st.inputMin || 2);
    }
    if (st.advance === "channel") {
      const el = document.getElementById("channel");
      return el && el.value === (st.channel || "irchighway:ebooks");
    }
    if (st.advance === "search-done") return !!BP.state.walkTrailSearchDone;
    if (st.advance === "fetch-done") return fetchDone;
    if (st.advance === "kennel-open") {
      return document.getElementById("panel-library")?.classList.contains("active");
    }
    if (st.advance === "pack-open") {
      return document.getElementById("panel-pack")?.classList.contains("active");
    }
    if (st.advance === "tag-saved") return !!BP.state.walkTrailTagged;
    if (st.advance === "cleanup") return true;
    if (st.advance === "finish") return true;
    return false;
  }

  function updateTipChrome() {
    const st = currentStep();
    const tip = tipEl();
    if (!st || !tip) return;
    const titleEl = document.getElementById("walk-trail-tip-title");
    const bodyEl = tip.querySelector("[data-wt-body]");
    if (titleEl) titleEl.textContent = st.title;
    if (bodyEl) {
      let copy = st.body;
      if (st.id === "fetch" && fetchError) {
        copy =
          fetchError + (fetchError.endsWith(".") ? " " : ". ") + "Tap Retry fetch, or try the practice row again.";
      } else if (st.id === "tag") {
        const modal = document.getElementById("register-modal");
        if (modal && !modal.classList.contains("hidden")) {
          copy = "Change at least one field (title, author, or tags), then tap Tag it.";
        }
      }
      bodyEl.textContent = copy;
    }
    tip.classList.remove("hidden");
    const nextBtn = tip.querySelector("[data-wt-next]");
    const retryBtn = tip.querySelector("[data-wt-retry]");
    const skipBtn = tip.querySelector("[data-wt-cleanup-skip]");
    const canNext = canAdvanceManual();
    if (nextBtn) {
      nextBtn.disabled = !canNext && st.advance !== "cleanup" && st.advance !== "finish";
      nextBtn.classList.toggle("hidden", st.advance === "search-done" || st.advance === "fetch-done" || st.advance === "tag-saved");
    }
    if (retryBtn) {
      retryBtn.classList.toggle("hidden", st.id !== "fetch" || !fetchError);
    }
    if (skipBtn) {
      skipBtn.classList.toggle("hidden", st.advance !== "cleanup");
    }
    if (st.id === "den") {
      ensureDenPanelOpen();
      ensureDenMockVisible();
    }
    if (st.id === "tag") {
      BP.state.walkTrailExpectTag = true;
    }
    const tagModal =
      st.id === "tag" && document.getElementById("register-modal") && !document.getElementById("register-modal").classList.contains("hidden");
    document.body.classList.toggle("bp-walk-trail-tag-modal", !!tagModal);
    if (tagModal) {
      clearFocusTarget();
      layoutSpotRing(null);
      const submit = document.getElementById("register-submit");
      try {
        submit?.scrollIntoView({ block: "end", behavior: "instant", inline: "nearest" });
      } catch {
        /* ignore */
      }
      const tip = tipEl();
      if (tip) {
        tip.classList.remove("bp-walk-trail-tip--dock");
        tip.classList.add("bp-walk-trail-tip--dock-top");
      }
      scheduleWalkTrailLayout(null, "top");
      return;
    }
    document.body.classList.remove("bp-walk-trail-tag-modal");
    const target = resolveStepTarget(st);
    markFocusTarget(target);
    placeSpot(target);
  }

  function showOverlay() {
    root()?.classList.remove("hidden");
    document.body.classList.add("bp-walk-trail-active");
    updateTipChrome();
  }

  function hideOverlay() {
    root()?.classList.add("hidden");
    document.body.classList.remove("bp-walk-trail-active");
    spotEl()?.classList.add("hidden");
    clearFocusTarget();
  }

  function teardownWalk(partial) {
    active = false;
    BP.walkTrailActive = false;
    BP.state.walkTrailSearchDone = false;
    BP.state.walkTrailTagged = false;
    BP.state.walkTrailExpectTag = false;
    fetchDone = false;
    fetchError = "";
    tutorialItemId = "";
    registerSnapshot = null;
    autoAdvanceFired.clear();
    clearMockIrcTimer();
    if (stepAdvanceTimer) {
      clearInterval(stepAdvanceTimer);
      stepAdvanceTimer = null;
    }
    document.body.classList.remove("bp-walk-trail-tag-modal");
    hideOverlay();
    if (!partial) {
      BP.state.activeSearchJob = BP.state.activeSearchJob === ACTIVE_JOB ? null : BP.state.activeSearchJob;
    }
  }

  async function handleCleanupStep() {
    if (!tutorialItemId) return;
    const items = (typeof BP.getLibraryItems === "function" ? BP.getLibraryItems() : []) || [];
    const item = items.find((it) => it.id === tutorialItemId);
    if (item && (await BP.confirmToss(item.title || "practice book", { light: true }))) {
      await BP.tossLibraryItem(item.id);
      void BP.loadLibrary?.();
    }
  }

  async function goNext(skipCleanup) {
    const st = currentStep();
    if (!st) return;
    if (st.advance === "cleanup" && !skipCleanup) {
      await handleCleanupStep();
    }
    if (st.advance === "finish") {
      markComplete();
      teardownWalk(true);
      BP.openGuidePage?.(11);
      return;
    }
    if (stepIndex >= steps.length - 1) {
      markComplete();
      teardownWalk(true);
      return;
    }
    stepIndex += 1;
    const next = currentStep();
    if (next?.id === "queue") {
      const qbtn = BP.tabButton("queue");
      if (qbtn) BP.activateTab(qbtn);
    }
    if (next?.id === "kennel") {
      const libBtn = BP.tabButton("library");
      if (libBtn) BP.activateTab(libBtn);
    }
    if (next?.id === "pack" || next?.id === "pack-house" || next?.id === "pack-bots") {
      const packBtn = BP.tabButton("pack");
      if (packBtn) BP.activateTab(packBtn);
    }
    updateTipChrome();
  }

  function autoWatchAdvance() {
    if (stepAdvanceTimer) clearInterval(stepAdvanceTimer);
    stepAdvanceTimer = setInterval(() => {
      if (!active) return;
      const st = currentStep();
      if (!st) return;
      const key = st.id + ":" + st.advance;
      if (st.advance === "tag-saved" && BP.state.walkTrailTagged && !autoAdvanceFired.has(key)) {
        autoAdvanceFired.add(key);
        setTimeout(() => void goNext(), 400);
      }
      updateTipChrome();
    }, 350);
  }

  function restartWalkTrail() {
    if (active) return;
    resetComplete();
    startWalkTrail();
  }

  function startWalkTrail() {
    if (active) return;
    if (isComplete()) return;
    teardownWalk(true);
    active = true;
    BP.walkTrailActive = true;
    stepIndex = 0;
    fetchDone = false;
    fetchError = "";
    tutorialQuery = "";
    tutorialTitle = "";
    tutorialItemId = "";
    BP.state.walkTrailSearchDone = false;
    BP.state.walkTrailTagged = false;
    const btn = BP.tabButton("search");
    if (btn) BP.activateTab(btn);
    const ch = document.getElementById("channel");
    if (ch) ch.value = "irchighway:ebooks";
    const searchMsg = document.getElementById("search-msg");
    if (searchMsg) {
      searchMsg.textContent = "";
      searchMsg.className = "bp-msg";
    }
    BP.syncChannelHint?.();
    showOverlay();
    autoWatchAdvance();
  }

  function exitWalkTrail() {
    teardownWalk(false);
  }

  async function handleSearchSubmit(body) {
    tutorialQuery = String(body.query || "").trim();
    tutorialTitle = tutorialFilename(tutorialQuery);
    const searchMsg = document.getElementById("search-msg");
    if (searchMsg) {
      searchMsg.textContent = "Practice sniff on Main trail…";
      searchMsg.className = "bp-msg muted";
    }
    BP.markUxSniffStarted?.();
    BP.state.activeSearchJob = ACTIVE_JOB;
    BP.state.walkTrailSearchDone = true;
    runMockIrcScript(tutorialQuery);
    const rows = buildDecoyRows(tutorialQuery);
    BP.state.walkTrailPracticeRow = rows.find((r) => r.walk_trail) || null;
    BP.ingestWalkTrailResults?.(rows, tutorialQuery);
    document.getElementById("results-wrap")?.scrollIntoView({ block: "start", behavior: "instant" });
    updateTipChrome();
    setTimeout(() => {
      if (!active || currentStep()?.id !== "sniff" || !BP.state.walkTrailSearchDone) return;
      const key = "sniff:search-done";
      if (autoAdvanceFired.has(key)) return;
      autoAdvanceFired.add(key);
      void goNext();
    }, 2600);
  }

  function onDocumentFetchClick(ev) {
    if (!active || fetchDone) return;
    if (stepIndex < fetchStepIndex()) return;
    const btn = ev.target.closest?.(".dl-row");
    const tr = btn?.closest?.("tr[data-walk-trail-row]");
    if (!btn || !tr) return;
    const row = practiceRow();
    if (!row) return;
    ev.preventDefault();
    ev.stopPropagation();
    void handleFetch(row, tr);
  }

  async function handleFetch(row, tr) {
    if (fetchDone) return;
    if (!row.walk_trail) {
      BP.showAppToast("Walk the Trail", "Fetch the practice .mobi row from this sniff.", "info");
      return;
    }
    if (tr && BP.setFetchRowState) BP.setFetchRowState(tr, "loading");
    const searchMsg = document.getElementById("search-msg");
    if (searchMsg) searchMsg.textContent = "Practice fetch…";
    fetchError = "";
    try {
      pushMockIrcLine("!TrailBot " + tutorialTitle, "out");
      setTimeout(() => pushMockIrcLine("TrailBot: sending " + tutorialTitle + " (practice)", "in"), 500);
      const data = await BP.api("/api/walk-trail/fetch", {
        method: "POST",
        body: JSON.stringify({ query: tutorialQuery, title: tutorialTitle }),
      });
      tutorialItemId = data.library_item_id || data.item?.id || "";
      if (tr && BP.setFetchRowState) BP.setFetchRowState(tr, "done");
      if (searchMsg) searchMsg.textContent = "Practice fetch complete — see Fresh catches.";
      BP.markUxFetchComplete?.();
      fetchDone = true;
      void BP.loadLibrary?.();
      void BP.refreshQueue?.();
      advanceFromFetch();
    } catch (err) {
      if (tr && BP.setFetchRowState) BP.setFetchRowState(tr, "fetch");
      const msg = err.message || "Practice fetch failed";
      if (/already have|duplicate|kennel/i.test(msg)) {
        fetchDone = true;
        void BP.loadLibrary?.();
        advanceFromFetch();
        return;
      }
      if (searchMsg) {
        searchMsg.textContent = msg;
        searchMsg.className = "bp-msg err";
      }
      fetchError = msg;
      updateTipChrome();
      BP.showAppToast("Walk the Trail", msg, "info");
    }
  }

  function retryFetch() {
    fetchError = "";
    updateTipChrome();
    const row = practiceRow();
    const tr = document.querySelector("tr[data-walk-trail-row]");
    if (row) void handleFetch(row, tr);
  }

  function onRegisterOpen(item) {
    if (!active || !BP.state.walkTrailExpectTag) return;
    if (item.id !== tutorialItemId) return;
    registerSnapshot = {
      title: document.getElementById("reg-title")?.value || "",
      authors: document.getElementById("reg-authors")?.value || "",
      tags: document.getElementById("reg-tags")?.value || "",
    };
    BP.state.walkTrailRegisterReady = false;
    syncRegisterSubmitGate();
    updateTipChrome();
  }

  function syncRegisterSubmitGate() {
    const btn = document.getElementById("register-submit");
    if (!active || !BP.state.walkTrailExpectTag || !registerSnapshot) {
      if (btn) btn.disabled = false;
      return;
    }
    const title = document.getElementById("reg-title")?.value || "";
    const authors = document.getElementById("reg-authors")?.value || "";
    const tags = document.getElementById("reg-tags")?.value || "";
    const changed =
      title !== registerSnapshot.title || authors !== registerSnapshot.authors || tags !== registerSnapshot.tags;
    if (btn) btn.disabled = !changed;
  }

  function onRegisterSaved(itemId) {
    if (!active) return;
    if (itemId === tutorialItemId) {
      BP.state.walkTrailTagged = true;
      BP.state.walkTrailExpectTag = false;
      tutorialItemId = itemId;
      updateTipChrome();
    }
  }

  function bindShell() {
    const r = root();
    if (!r) return;
    r.querySelector("[data-wt-retry]")?.addEventListener("click", () => retryFetch());
    r.querySelector("[data-wt-next]")?.addEventListener("click", () => void goNext());
    r.querySelector("[data-wt-exit]")?.addEventListener("click", () => exitWalkTrail());
    r.querySelector("[data-wt-cleanup-skip]")?.addEventListener("click", () => void goNext(true));
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && active) exitWalkTrail();
    });
    document.addEventListener("click", onDocumentFetchClick, true);
    document.addEventListener("touchend", onDocumentFetchClick, true);
    const relayout = () => {
      if (active) updateTipChrome();
    };
    window.addEventListener("resize", relayout);
    MOBILE_TIP_MQ.addEventListener("change", relayout);
    window.visualViewport?.addEventListener("resize", relayout);
    ["reg-title", "reg-authors", "reg-tags"].forEach((id) => {
      document.getElementById(id)?.addEventListener("input", syncRegisterSubmitGate);
    });
  }

  function syncWalkTrailEntry() {
    const complete = isComplete();
    const onboardDismissed = localStorage.getItem("bookpupOnboardDismissed") === "1";
    const again = "Walk the Trail again";
    const label = complete ? again : "Walk the Trail";
    const onboardBtn = document.getElementById("onboard-walk-trail");
    const sniffBtn = document.getElementById("sniff-walk-trail");
    if (onboardBtn) onboardBtn.textContent = label;
    if (sniffBtn) sniffBtn.textContent = label;
    const sniffWrap = document.getElementById("sniff-walk-trail-wrap");
    if (sniffWrap) {
      const showSniffLink = complete || onboardDismissed;
      sniffWrap.classList.toggle("hidden", !showSniffLink);
      const hint = sniffWrap.querySelector(".muted");
      if (hint) {
        hint.textContent = complete
          ? " — run the practice tour again"
          : " — step-by-step tutorial mode";
      }
    }
  }

  bindShell();

  BP.walkTrailActive = false;
  BP.startWalkTrail = startWalkTrail;
  BP.restartWalkTrail = restartWalkTrail;
  BP.exitWalkTrail = exitWalkTrail;
  BP.resetWalkTrailComplete = resetComplete;
  BP.walkTrailOnSearch = handleSearchSubmit;
  BP.walkTrailOnFetch = handleFetch;
  BP.syncWalkTrailEntry = syncWalkTrailEntry;
  BP.walkTrailOnRegisterOpen = onRegisterOpen;
  BP.walkTrailOnRegisterSaved = onRegisterSaved;
  BP.walkTrailIsComplete = isComplete;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", syncWalkTrailEntry);
  } else {
    syncWalkTrailEntry();
  }
})(window.BookPup);