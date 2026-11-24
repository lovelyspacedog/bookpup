window.BookPup = window.BookPup || {};
(function (BP) {
  "use strict";
  BP.CSRF = { "X-Bookpup": "1" };
  const CSRF = BP.CSRF;
  BP.COVER_MAX_BYTES = 2 * 1024 * 1024;
  BP.state = {
    authHeader: null,
    sessionAdmin: false,
    sessionUsername: "",
    sessionOpdsUrl: "",
    notifiedDoneJobs: new Set(),
    coverImageSearchEnabled: false,
    activeSearchJob: null,
    pollTimer: null,
    searchPollTimer: null,
    fetchPollTimer: null,
    pendingFetch: null,
    sendTarget: null,
    ircEvents: [],
    ircAfterId: 0,
    searchTabActive: true,
    ircPollTimer: null,
    packChatAfterId: 0,
    packChatDelAfter: 0,
    packChatById: {},
    packChatUnread: 0,
    packChatUnreadByPeer: {},
    packChatTabActive: false,
    packChatBootstrapped: false,
    packChatPollTimer: null,
  };

  function bytes(n) {
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
    if (n < 1024 * 1024 * 1024) return (n / (1024 * 1024)).toFixed(1) + " MB";
    return (n / (1024 * 1024 * 1024)).toFixed(2) + " GB";
  }

  async function api(path, opts) {
    const headers = {
      ...(opts && opts.body ? { "Content-Type": "application/json" } : {}),
      ...CSRF,
      ...(BP.state.authHeader ? { Authorization: BP.state.authHeader } : {}),
      ...(opts && opts.headers ? opts.headers : {}),
    };
    const res = await fetch(path, { ...opts, headers });
    if (res.status === 401) {
      showLogin("Your session wandered off. Come inside again.");
      throw new Error("Authentication required");
    }
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { raw: text };
    }
    if (!res.ok) {
      const msg = (data && data.error) || res.statusText || "Request failed";
      throw new Error(msg);
    }
    return data;
  }

  const loginScreen = document.getElementById("login-screen");
  const appShell = document.getElementById("app-shell");
  const loginForm = document.getElementById("login-form");
  const loginMsg = document.getElementById("login-msg");
  const loginUser = document.getElementById("login-user");
  const loginPass = document.getElementById("login-pass");
  const loginTagline = document.getElementById("login-tagline");
  const logoutBtn = document.getElementById("logout-btn");

  const LOGIN_TAGLINES = [
    "Sign in to fetch your next great read.",
    "Welcome back! Ready to fetch some books?",
    "BookPup: Your household's ebook retriever.",
    "Sign in to sniff out your next favorite book.",
    "The library's cold—let BookPup warm up your queue.",
    "Tail-wagging reads start with a sign in.",
    "Good pup, good books. Sign in to begin.",
    "Your reading pile is one login away.",
    "Sit. Stay. Come inside. Fetch books.",
    "BookPup's been guarding the stash. Prove it's you.",
    "Ears up—fresh downloads await.",
    "Put your nose to #ebooks. Sign in first.",
    "The hound of e-literature is ready when you are.",
    "Drop your password—BookPup's already at the door.",
    "Woof woof (sign in for actual ebooks).",
  ];

  let loginTaglineTimer = null;
  let loginTaglineInitialized = false;

  function pickLoginTagline() {
    const i = Math.floor(Math.random() * LOGIN_TAGLINES.length);
    return LOGIN_TAGLINES[i];
  }

  function animateLoginTagline() {
    if (!loginTagline) return;
    if (loginTaglineTimer) {
      clearTimeout(loginTaglineTimer);
      loginTaglineTimer = null;
    }
    const text = pickLoginTagline();
    loginTagline.textContent = "";
    loginTagline.classList.remove("bp-typewriter--done");
    loginTagline.classList.add("bp-typewriter");
    let i = 0;
    function step() {
      if (i >= text.length) {
        loginTagline.classList.add("bp-typewriter--done");
        return;
      }
      loginTagline.textContent += text.charAt(i);
      i += 1;
      const ch = text.charAt(i - 1);
      const delay = ch === " " || ch === "—" ? 16 : 26 + Math.floor(Math.random() * 22);
      loginTaglineTimer = setTimeout(step, delay);
    }
    step();
  }

  function clearBookpupClientPrefs() {
    const keys = [];
    for (let i = 0; i < localStorage.length; i += 1) {
      const k = localStorage.key(i);
      if (k && k.startsWith("bookpup")) keys.push(k);
    }
    keys.forEach((k) => localStorage.removeItem(k));
    const token = sessionStorage.getItem("bookpupToken");
    for (let i = sessionStorage.length - 1; i >= 0; i -= 1) {
      const k = sessionStorage.key(i);
      if (k && k !== "bookpupToken") sessionStorage.removeItem(k);
    }
    if (token) sessionStorage.setItem("bookpupToken", token);
  }

  function showLogin(message) {
    const wasInApp = appShell && !appShell.classList.contains("hidden");
    const alreadyOnLogin = loginScreen && !loginScreen.classList.contains("hidden");
    sessionStorage.removeItem("bookpupToken");
    BP.state.authHeader = null;
    if (appShell) appShell.classList.add("hidden");
    if (loginScreen) loginScreen.classList.remove("hidden");
    BP.syncPwaInstallUi?.();
    BP.stopQueueTabPoll();
    if (message && loginMsg) {
      loginMsg.textContent = message;
      loginMsg.className = "bp-msg err";
    }
    if (alreadyOnLogin && !wasInApp && loginTaglineInitialized) {
      return;
    }
    requestAnimationFrame(() => {
      const focus =
        loginPass && loginUser && loginUser.value.trim() ? loginPass : loginUser;
      if (focus && typeof focus.focus === "function") focus.focus();
    });
    if (wasInApp || !loginTaglineInitialized) {
      loginTaglineInitialized = true;
      animateLoginTagline();
    }
  }

  async function loadSession() {
    try {
      const s = await api("/api/session");
      BP.state.sessionAdmin = !!s.admin;
      BP.state.sessionUsername = s.username || "";
      const tab = document.getElementById("accounts-tab");
      const adminBlock = document.getElementById("accounts-admin-block");
      if (tab) {
        tab.classList.remove("hidden");
        tab.textContent = BP.state.sessionAdmin ? "Pack roster" : "Your tag";
      }
      syncTabMoreAccountsLabel();
      if (adminBlock) adminBlock.classList.toggle("hidden", !BP.state.sessionAdmin);
      try {
        if (s.irc_targets) BP.applyIrcTargetOptions(s.irc_targets);
      } catch (_e) {
        /* channel picker is optional; don't drop admin session */
      }
      BP.state.sessionOpdsUrl = s.opds_catalog_url || s.opds_url || "";
      BP.state.soulseekLimits = s.soulseek_limits || null;
    } catch {
      BP.state.sessionAdmin = false;
    }
  }

  async function showApp() {
    if (loginScreen) loginScreen.classList.add("hidden");
    if (appShell) appShell.classList.remove("hidden");
    await loadSession();
    if (BP.state.authHeader && BP.offlineBooks) {
      void BP.offlineBooks.flushReadingSync(BP.state.authHeader);
    }
    BP.loadNotifiedDoneJobs?.();
    BP.refreshQueue();
    BP.loadLibrary();
    renderSearchHistoryUi();
    await BP.loadIrcTargets();
    BP.restoreSearchChannel();
    await BP.loadSearchWorkspace();
    BP.clearSniffQueryInput();
    BP.loadAccountTab();
    if (BP.state.sessionAdmin) BP.loadAccountsTab();
    BP.loadIrcFeedFloor();
    if (!BP.state.ircPollTimer) BP.startIrcPoll();
    BP.pollIrcFeed(true);
    BP.startPackChatPoll?.();
    BP.syncOnboardUi?.();
    BP.syncPwaInstallUi?.();
    BP.refreshQueue?.();
  }

  async function fetchPublic(path) {
    const res = await fetch(path);
    const text = await res.text();
    return text ? JSON.parse(text) : null;
  }

  async function doLogin(username, password) {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...CSRF },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      let msg = data.error || "Sign-in failed";
      if (res.status === 429 && data.retry_after_seconds) {
        msg += " Wait " + data.retry_after_seconds + "s.";
      }
      throw new Error(msg);
    }
    sessionStorage.setItem("bookpupToken", data.token);
    BP.state.authHeader = "Bearer " + data.token;
    BP.state.sessionAdmin = !!data.admin;
    BP.state.sessionUsername = data.username || username;
    BP.state.ircEvents = [];
    BP.state.ircAfterId = 0;
    const ircFeed = document.getElementById("irc-feed");
    if (ircFeed) ircFeed.innerHTML = "";
    BP.loadIrcFeedFloor();
    if (loginMsg) {
      loginMsg.textContent = "";
      loginMsg.className = "bp-msg muted";
    }
    showApp();
  }

  loginForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    loginMsg.textContent = "Scratching at the door…";
    loginMsg.className = "bp-msg muted";
    try {
      await doLogin(loginUser.value.trim(), loginForm.password.value);
    } catch (err) {
      loginMsg.textContent = err.message;
      loginMsg.className = "bp-msg err";
    }
  });

  async function doLogout() {
    try {
      await api("/api/logout", { method: "POST", body: "{}" });
    } catch (_e) {
      /* ignore */
    }
    BP.resetIrcFeedLocal();
    BP.resetPackChatLocal?.();
    showLogin();
  }

  if (logoutBtn) logoutBtn.addEventListener("click", () => void doLogout());
  document.getElementById("tab-more-logout")?.addEventListener("click", () => {
    closeTabMoreMenu();
    void doLogout();
  });

  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  const SEARCH_HISTORY_KEY = "bookpupSearchHistory";
  const SEARCH_HISTORY_MAX = 40;
  const SEARCH_CHANNEL_KEY = "bookpupSearchChannel";
  const DEFAULT_SEARCH_CHANNEL = "irchighway:ebooks";

  function loadSearchHistory() {
    try {
      const raw = JSON.parse(localStorage.getItem(SEARCH_HISTORY_KEY) || "[]");
      return Array.isArray(raw) ? raw.filter((x) => typeof x === "string" && x.trim()) : [];
    } catch {
      return [];
    }
  }

  function saveSearchHistory(items) {
    localStorage.setItem(
      SEARCH_HISTORY_KEY,
      JSON.stringify(items.slice(0, SEARCH_HISTORY_MAX))
    );
  }

  function rememberSearchQuery(q) {
    const query = String(q || "").trim();
    if (!query) return;
    const norm = query.toLowerCase();
    const next = [query].concat(
      loadSearchHistory().filter((x) => x.toLowerCase() !== norm)
    );
    saveSearchHistory(next);
    renderSearchHistoryUi();
  }

  function formatSearchHistoryLabel(q) {
    return q.length > 72 ? q.slice(0, 69) + "…" : q;
  }

  function searchHistoryMatchesInput(raw) {
    const items = loadSearchHistory();
    const needle = String(raw || "").trim().toLowerCase();
    if (!needle) return items;
    return items.filter((q) => q.toLowerCase().includes(needle));
  }

  let querySuggestionsOpen = false;
  let querySuggestionsIndex = -1;

  function setQuerySuggestionsOpen(open) {
    querySuggestionsOpen = open;
    const queryEl = document.getElementById("query");
    const list = document.getElementById("query-suggestions");
    const toggle = document.getElementById("query-history-toggle");
    if (!list || !queryEl) return;
    list.classList.toggle("hidden", !open);
    queryEl.setAttribute("aria-expanded", open ? "true" : "false");
    if (toggle) toggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (!open) querySuggestionsIndex = -1;
  }

  function pickQuerySuggestion(q) {
    const queryEl = document.getElementById("query");
    if (!queryEl || !q) return;
    queryEl.value = q;
    setQuerySuggestionsOpen(false);
    queryEl.focus();
  }

  function renderQuerySuggestions(filterText) {
    const items = loadSearchHistory();
    const superbar = document.getElementById("query-superbar");
    const list = document.getElementById("query-suggestions");
    const clearBtn = document.getElementById("search-history-clear");
    const toggle = document.getElementById("query-history-toggle");
    const hasHistory = items.length > 0;

    if (superbar) superbar.classList.toggle("bp-query-superbar--has-history", hasHistory);
    if (clearBtn) clearBtn.classList.toggle("hidden", !hasHistory);
    if (toggle) toggle.classList.toggle("hidden", !hasHistory);
    if (!list) return;

    const shown = searchHistoryMatchesInput(filterText);
    list.textContent = "";
    if (!shown.length) {
      setQuerySuggestionsOpen(false);
      return;
    }

    shown.forEach((q, i) => {
      const li = document.createElement("li");
      li.className = "bp-query-suggestions__item";
      li.setAttribute("role", "option");
      li.id = `query-suggestion-${i}`;
      li.dataset.value = q;
      li.textContent = formatSearchHistoryLabel(q);
      const active = i === querySuggestionsIndex;
      li.classList.toggle("bp-query-suggestions__item--active", active);
      li.setAttribute("aria-selected", active ? "true" : "false");
      list.appendChild(li);
    });

    if (querySuggestionsOpen) list.classList.remove("hidden");
  }

  function renderSearchHistorySelect() {
    const queryEl = document.getElementById("query");
    renderQuerySuggestions(queryEl?.value ?? "");
  }

  function renderSearchHistoryUi() {
    const queryEl = document.getElementById("query");
    renderQuerySuggestions(queryEl?.value ?? "");
  }

  function bindSearchHistoryUx() {
    const queryEl = document.getElementById("query");
    const list = document.getElementById("query-suggestions");
    const clearBtn = document.getElementById("search-history-clear");
    const toggle = document.getElementById("query-history-toggle");
    if (!queryEl || !list) return;

    let blurTimer = 0;

    const openSuggestions = () => {
      renderQuerySuggestions(queryEl.value);
      const shown = searchHistoryMatchesInput(queryEl.value);
      if (!shown.length) {
        setQuerySuggestionsOpen(false);
        return;
      }
      setQuerySuggestionsOpen(true);
      querySuggestionsIndex = -1;
      renderQuerySuggestions(queryEl.value);
    };

    queryEl.addEventListener("focus", () => {
      if (blurTimer) window.clearTimeout(blurTimer);
      openSuggestions();
    });

    queryEl.addEventListener("input", () => {
      renderQuerySuggestions(queryEl.value);
      const shown = searchHistoryMatchesInput(queryEl.value);
      setQuerySuggestionsOpen(shown.length > 0);
      querySuggestionsIndex = -1;
      renderQuerySuggestions(queryEl.value);
    });

    queryEl.addEventListener("keydown", (ev) => {
      const shown = searchHistoryMatchesInput(queryEl.value);
      if (!shown.length) return;

      if (ev.key === "ArrowDown") {
        ev.preventDefault();
        if (!querySuggestionsOpen) {
          setQuerySuggestionsOpen(true);
          querySuggestionsIndex = 0;
        } else {
          querySuggestionsIndex = Math.min(querySuggestionsIndex + 1, shown.length - 1);
        }
        renderQuerySuggestions(queryEl.value);
        list.querySelector(".bp-query-suggestions__item--active")?.scrollIntoView({ block: "nearest" });
        return;
      }
      if (ev.key === "ArrowUp") {
        if (!querySuggestionsOpen) return;
        ev.preventDefault();
        querySuggestionsIndex = Math.max(querySuggestionsIndex - 1, 0);
        renderQuerySuggestions(queryEl.value);
        return;
      }
      if (ev.key === "Escape") {
        setQuerySuggestionsOpen(false);
        return;
      }
      if (ev.key === "Enter" && querySuggestionsOpen && querySuggestionsIndex >= 0) {
        ev.preventDefault();
        pickQuerySuggestion(shown[querySuggestionsIndex]);
      }
    });

    queryEl.addEventListener("blur", () => {
      blurTimer = window.setTimeout(() => setQuerySuggestionsOpen(false), 150);
    });

    list.addEventListener("mousedown", (ev) => {
      const item = ev.target.closest(".bp-query-suggestions__item");
      if (!item) return;
      ev.preventDefault();
      pickQuerySuggestion(item.dataset.value);
    });

    toggle?.addEventListener("click", () => {
      if (querySuggestionsOpen) {
        setQuerySuggestionsOpen(false);
        return;
      }
      queryEl.focus();
      openSuggestions();
    });

    clearBtn?.addEventListener("click", () => {
      if (!loadSearchHistory().length) return;
      if (!window.confirm("Clear all recent sniff queries?")) return;
      saveSearchHistory([]);
      setQuerySuggestionsOpen(false);
      renderSearchHistoryUi();
    });
  }


  const TAB_OVERFLOW = new Set(["guide", "changelog", "accounts"]);

  function syncTabMoreAccountsLabel() {
    const src = document.getElementById("accounts-tab");
    const mirror = document.getElementById("tab-more-accounts");
    if (src && mirror) mirror.textContent = src.textContent || "Your tag";
  }

  function closeTabMoreMenu() {
    const menu = document.getElementById("tab-more-menu");
    const moreBtn = document.getElementById("tab-more");
    menu?.classList.add("hidden");
    moreBtn?.setAttribute("aria-expanded", "false");
  }

  function bindTabMoreMenu() {
    const moreBtn = document.getElementById("tab-more");
    const menu = document.getElementById("tab-more-menu");
    if (!moreBtn || !menu) return;
    moreBtn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const opening = menu.classList.contains("hidden");
      if (opening) menu.classList.remove("hidden");
      else menu.classList.add("hidden");
      moreBtn.setAttribute("aria-expanded", opening ? "true" : "false");
    });
    menu.querySelectorAll("[data-tab-target]").forEach((item) => {
      item.addEventListener("click", () => {
        const id = item.getAttribute("data-tab-target");
        const target = document.querySelector('.bp-tab[data-tab="' + CSS.escape(id) + '"]');
        if (target) activateTab(target);
        closeTabMoreMenu();
      });
    });
    document.addEventListener("click", (ev) => {
      if (menu.classList.contains("hidden")) return;
      if (ev.target.closest("#tab-more-menu") || ev.target.closest("#tab-more")) return;
      closeTabMoreMenu();
    });
  }

  bindTabMoreMenu();

  function activateTab(btn) {
    if (!btn || !btn.dataset.tab) return;
    document.querySelectorAll(".bp-tab").forEach((b) => {
      b.classList.remove("active");
      b.setAttribute("aria-selected", "false");
      b.setAttribute("tabindex", "-1");
    });
    document.querySelectorAll(".bp-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    btn.setAttribute("aria-selected", "true");
    btn.setAttribute("tabindex", "0");
    document.getElementById("panel-" + btn.dataset.tab).classList.add("active");
    const tab = btn.dataset.tab;
    const moreBtn = document.getElementById("tab-more");
    if (moreBtn) {
      moreBtn.classList.toggle("active", TAB_OVERFLOW.has(tab));
      if (!TAB_OVERFLOW.has(tab)) closeTabMoreMenu();
    }
    if (BP.state.packChatTabActive && tab !== "pack") BP.onPackChatTabInactive?.();
    BP.state.searchTabActive = tab === "search";
    if (tab === "pack") BP.onPackChatTabActive?.();
    if (BP.state.searchTabActive) {
      BP.clearSniffQueryInput();
      if (!BP.state.ircPollTimer) BP.startIrcPoll();
      else BP.pollIrcFeed(true);
    } else {
      BP.stopIrcPoll();
    }
    BP.stopQueueTabPoll();
    if (tab === "library") BP.loadLibrary();
    if (tab === "queue") BP.startQueueTabPoll();
    BP.syncWalkTrailEntry?.();
    if (tab === "guide") BP.loadGuide();
    if (tab === "changelog") BP.loadChangelog();
    if (tab === "accounts") {
      BP.loadAccountTab();
      if (BP.state.sessionAdmin) {
        BP.loadAccountsTab();
        BP.loadAdminDigest();
        BP.loadAdminBugInbox?.();
        BP.loadAdminFeatureInbox?.();
      }
    }
  }

  const tablist = document.querySelector(".bp-tabs");
  document.querySelectorAll(".bp-tab").forEach((btn) => {
    if (!btn.classList.contains("active")) btn.setAttribute("tabindex", "-1");
    btn.addEventListener("click", () => activateTab(btn));
  });
  if (tablist) {
    tablist.addEventListener("keydown", (ev) => {
      const tabs = [...document.querySelectorAll(".bp-tab")].filter((t) => !t.classList.contains("hidden"));
      const ix = tabs.indexOf(document.activeElement);
      if (ix < 0) return;
      let next = ix;
      if (ev.key === "ArrowRight") next = (ix + 1) % tabs.length;
      else if (ev.key === "ArrowLeft") next = (ix - 1 + tabs.length) % tabs.length;
      else if (ev.key === "Home") next = 0;
      else if (ev.key === "End") next = tabs.length - 1;
      else return;
      ev.preventDefault();
      tabs[next].focus();
      activateTab(tabs[next]);
    });
  }

  function pickToastStack(kind) {
    if (kind === "err") {
      return document.getElementById("bp-toast-stack-assertive") || document.getElementById("bp-toast-stack");
    }
    return document.getElementById("bp-toast-stack");
  }

  function appendToast(stack, el, dwellMs) {
    if (!stack) return;
    stack.appendChild(el);
    requestAnimationFrame(() => el.classList.add("bp-toast--show"));
    const ms = dwellMs || 6500;
    setTimeout(() => {
      el.classList.remove("bp-toast--show");
      setTimeout(() => el.remove(), 450);
    }, ms);
    while (stack.children.length > 5) {
      stack.firstChild.remove();
    }
  }

  function showAppToast(title, message, kind, actions) {
    const stack = pickToastStack(kind);
    if (!stack || !message) return;
    const el = document.createElement("div");
    el.className = "bp-toast bp-toast--" + (kind || "info");
    el.innerHTML =
      '<strong class="bp-toast-title">' +
      escapeHtml(title || "BookPup") +
      '</strong><span class="bp-toast-msg">' +
      escapeHtml(message) +
      "</span>";
    const actList = actions && actions.length ? actions : null;
    if (actList) {
      const foot = document.createElement("div");
      foot.className = "bp-toast-actions";
      actList.forEach((a) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "bp-btn bp-btn--ghost bp-toast-action";
        b.textContent = a.label;
        b.addEventListener("click", () => {
          try {
            a.onClick?.();
          } finally {
            el.remove();
          }
        });
        foot.appendChild(b);
      });
      el.appendChild(foot);
    }
    appendToast(stack, el, actList ? 12000 : 6500);
  }

  function showQueueToast(job, message, kind) {
    const stack = pickToastStack(kind);
    if (!stack || !message) return;
    const titleFn = typeof BP.queueToastTitle === "function" ? BP.queueToastTitle(job) : "BookPup";
    const el = document.createElement("div");
    el.className = "bp-toast bp-toast--" + (kind || "info");
    el.innerHTML =
      '<strong class="bp-toast-title">' +
      escapeHtml(titleFn) +
      '</strong><span class="bp-toast-msg">' +
      escapeHtml(message) +
      "</span>";
    appendToast(stack, el);
  }

  function tabButton(name) {
    return document.querySelector('.bp-tab[data-tab="' + CSS.escape(name) + '"]');
  }

  function openStashPanel() {
    goToFreshCatches();
  }

  function goToFreshCatches() {
    const btn = tabButton("library");
    if (btn) activateTab(btn);
    document.getElementById("lib-section-downloads")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  BP.STAGING_TTL_SECONDS = 24 * 3600;
  BP.SEARCH_CHANNEL_KEY = SEARCH_CHANNEL_KEY;
  BP.DEFAULT_SEARCH_CHANNEL = DEFAULT_SEARCH_CHANNEL;

  // exports
  BP.activateTab = activateTab;
  BP.animateLoginTagline = animateLoginTagline;
  BP.api = api;
  BP.bindSearchHistoryUx = bindSearchHistoryUx;
  BP.bindTabMoreMenu = bindTabMoreMenu;
  BP.bytes = bytes;
  BP.clearBookpupClientPrefs = clearBookpupClientPrefs;
  BP.closeTabMoreMenu = closeTabMoreMenu;
  BP.doLogin = doLogin;
  BP.doLogout = doLogout;
  BP.escapeHtml = escapeHtml;
  BP.fetchPublic = fetchPublic;
  BP.loadSearchHistory = loadSearchHistory;
  BP.loadSession = loadSession;
  BP.pickLoginTagline = pickLoginTagline;
  BP.rememberSearchQuery = rememberSearchQuery;
  BP.renderSearchHistorySelect = renderSearchHistorySelect;
  BP.renderSearchHistoryUi = renderSearchHistoryUi;
  BP.saveSearchHistory = saveSearchHistory;
  BP.showApp = showApp;
  BP.showAppToast = showAppToast;
  BP.showLogin = showLogin;
  BP.showQueueToast = showQueueToast;
  BP.syncTabMoreAccountsLabel = syncTabMoreAccountsLabel;
  BP.tabButton = tabButton;
  BP.openStashPanel = openStashPanel;
  BP.goToFreshCatches = goToFreshCatches;
})(window.BookPup);
