(function (BP) {
  "use strict";
  const CSRF = BP.CSRF;
  const COVER_MAX_BYTES = BP.COVER_MAX_BYTES;
  const SEARCH_CHANNEL_KEY = BP.SEARCH_CHANNEL_KEY || "bookpupSearchChannel";
  const DEFAULT_SEARCH_CHANNEL = BP.DEFAULT_SEARCH_CHANNEL || "irchighway:ebooks";
  const LEGACY_CHANNEL_IDS = {
    ebooks: "irchighway:ebooks",
    bookz: "undernet:bookz",
    "irchighway:bookz": "irchighway:ebooks",
  };
  let sniffSourceHints = {};

  function applyIrcTargetOptions(targets) {
    const sel = document.getElementById("channel");
    if (!sel || !targets || !targets.length) return;
    const savedRaw = localStorage.getItem(SEARCH_CHANNEL_KEY);
    const saved = LEGACY_CHANNEL_IDS[savedRaw] || savedRaw;
    sniffSourceHints = {};
    sel.textContent = "";
    targets.forEach((t) => {
      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = t.label;
      if (t.hint) sniffSourceHints[t.id] = t.hint;
      sel.appendChild(opt);
    });
    if (saved && sel.querySelector('option[value="' + saved + '"]')) {
      sel.value = saved;
    } else if (sel.querySelector('option[value="' + DEFAULT_SEARCH_CHANNEL + '"]')) {
      sel.value = DEFAULT_SEARCH_CHANNEL;
    }
    syncIrcChatChannel();
    syncChannelHint();
  }

  function syncSearchSubmitLabel() {
    const sel = document.getElementById("channel");
    const btn = document.getElementById("search-submit-btn");
    if (!sel || !btn) return;
    const v = sel.value;
    if (v === "xdcc:index") btn.textContent = "Sniff XDCC Index";
    else if (v === "soulseek:slskd") btn.textContent = "Sniff Soulseek";
    else btn.textContent = "Sniff on IRC";
  }

  function syncChannelHint() {
    const sel = document.getElementById("channel");
    const hint = document.getElementById("channel-hint");
    if (!sel || !hint) return;
    const v = sel.value;
    const fromApi = sniffSourceHints[v];
    if (fromApi) {
      hint.textContent = fromApi;
    } else if (v === "soulseek:slskd") {
      let extra =
        "Soulseek peer search via household slskd. Shared login; per-user sniff/fetch caps (admins exempt from personal caps).";
      const lim = BP.state?.soulseekLimits;
      if (lim && !lim.admin_exempt && lim.searches_remaining != null) {
        extra += ` Sniffs left this hour: ${lim.searches_remaining}; fetches today: ${lim.downloads_remaining}.`;
      }
      hint.textContent = extra;
    } else if (v === "xdcc:index") {
      hint.textContent =
        "HTTP metasearch across warez IRC—not @search. Video, comics, archives, and more (not limited to ebooks).";
    } else if (v === "all") {
      hint.textContent =
        "Runs @search on every ebook IRC channel in the list in one sniff, then merges results. Does not include XDCC.";
    } else {
      hint.textContent =
        "Novels and mainstream ebooks via @search on IRCHighway #ebooks—recommended starting trail.";
    }
    syncSearchSubmitLabel();
  }

  function ircBarkAllowed() {
    return !!ircBarkEnable?.checked;
  }

  const ircCompose = document.getElementById("irc-compose");

  function syncIrcChatChannel() {
    const sel = document.getElementById("channel");
    const input = document.getElementById("irc-chat-input");
    const send = document.getElementById("irc-chat-send");
    const barkOn = ircBarkAllowed();
    if (ircCompose) {
      ircCompose.classList.toggle("hidden", !barkOn);
    }
    if (!barkOn) {
      return;
    }
    const all = sel && sel.value === "all";
    const disabled = !!all;
    if (input) {
      input.disabled = disabled;
      input.placeholder = all ? "Pick one network to bark…" : "Bark at the channel…";
    }
    if (send) send.disabled = disabled;
  }

  async function loadIrcTargets() {
    try {
      const data = await BP.api("/api/irc/targets");
      applyIrcTargetOptions(data.targets);
    } catch {
      /* keep static options from HTML */
    }
    syncIrcChatChannel();
  }

  document.getElementById("channel")?.addEventListener("change", () => {
    syncIrcChatChannel();
    syncChannelHint();
  });

  function restoreSearchChannel() {
    const sel = document.getElementById("channel");
    if (!sel) return;
    const savedRaw = localStorage.getItem(SEARCH_CHANNEL_KEY);
    const saved = LEGACY_CHANNEL_IDS[savedRaw] || savedRaw;
    if (saved && sel.querySelector('option[value="' + saved + '"]')) {
      sel.value = saved;
    } else if (sel.querySelector('option[value="' + DEFAULT_SEARCH_CHANNEL + '"]')) {
      sel.value = DEFAULT_SEARCH_CHANNEL;
    }
    syncChannelHint();
  }


  const ircFeedEl = document.getElementById("irc-feed");
  const ircAutoscroll = document.getElementById("irc-autoscroll");
  const ircHideRaw = document.getElementById("irc-hide-raw");
  const ircHideOthers = document.getElementById("irc-hide-others");
  const ircBarkEnable = document.getElementById("irc-bark-enable");
  const IRC_HIDE_OTHERS_KEY = "bookpupIrcHideOthers";
  const IRC_HIDE_RAW_KEY = "bookpupIrcHideRaw";
  const IRC_BARK_ENABLE_KEY = "bookpupIrcBarkEnable";
  let ircFeedFloorId = 0;
  function ircFloorStorageKey() {
    return "bookpupIrcFloor_" + (BP.state.sessionUsername || "");
  }

  function resetIrcFeedLocal() {
    BP.state.ircEvents = [];
    BP.state.ircAfterId = 0;
    ircFeedFloorId = 0;
    if (ircFeedEl) ircFeedEl.innerHTML = "";
    if (BP.state.sessionUsername) sessionStorage.removeItem(ircFloorStorageKey());
  }

  function loadIrcFeedFloor() {
    if (!BP.state.sessionUsername) return;
    const raw = sessionStorage.getItem(ircFloorStorageKey());
    const n = raw ? parseInt(raw, 10) : 0;
    ircFeedFloorId = Number.isFinite(n) && n > 0 ? n : 0;
  }

  function resetIrcFeedFloorIfStale(serverLatestId) {
    const latest = typeof serverLatestId === "number" ? serverLatestId : parseInt(serverLatestId, 10);
    if (!Number.isFinite(latest) || latest < 0) return;
    if (ircFeedFloorId > 0 && latest < ircFeedFloorId) {
      ircFeedFloorId = 0;
      if (BP.state.sessionUsername) {
        sessionStorage.removeItem(ircFloorStorageKey());
      }
      rerenderIrcFeed();
    }
  }

  if (ircBarkEnable) {
    ircBarkEnable.checked = localStorage.getItem(IRC_BARK_ENABLE_KEY) === "1";
    ircBarkEnable.addEventListener("change", () => {
      localStorage.setItem(IRC_BARK_ENABLE_KEY, ircBarkEnable.checked ? "1" : "0");
      syncIrcChatChannel();
    });
    syncIrcChatChannel();
  }
  if (ircHideOthers) {
    const stored = localStorage.getItem(IRC_HIDE_OTHERS_KEY);
    ircHideOthers.checked = stored !== "0";
  }
  if (ircHideRaw) {
    ircHideRaw.checked = localStorage.getItem(IRC_HIDE_RAW_KEY) === "1";
  }

  function formatTs(ts) {
    try {
      return new Date(ts * 1000).toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return "";
    }
  }

  function ircEventVisible(ev) {
    if (ircFeedFloorId && ircEventId(ev) <= ircFeedFloorId) return false;
    if (ircHideRaw && ircHideRaw.checked && ev.kind === "raw") return false;
    if (ircHideOthers?.checked && ev.owner && ev.owner !== BP.state.sessionUsername) {
      return false;
    }
    return true;
  }

  function ircEventId(ev) {
    return typeof ev.id === "number" ? ev.id : parseInt(ev.id, 10);
  }

  function formatIrcEventPlain(ev) {
    const target = ev.target ? "@" + ev.target + " " : "";
    const tag = ev.kind ? "[" + ev.kind + "] " : "";
    const who =
      ev.owner && ev.owner !== BP.state.sessionUsername ? "[" + ev.owner + "] " : "";
    return formatTs(ev.ts) + who + tag + target + (ev.text || "");
  }

  async function copyIrcLog() {
    const hint = document.getElementById("irc-chat-msg");
    const lines = BP.state.ircEvents.filter(ircEventVisible).map(formatIrcEventPlain);
    const text = lines.join("\n");
    if (!text) {
      if (hint) {
        hint.textContent = "Nothing to copy yet.";
        hint.className = "bp-msg muted";
      }
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      if (hint) {
        hint.textContent = "Den log copied.";
        hint.className = "bp-msg muted";
      }
    } catch {
      if (hint) {
        hint.textContent = "Could not copy — check browser permissions.";
        hint.className = "bp-msg err";
      }
    }
  }

  document.getElementById("irc-copy-log")?.addEventListener("click", () => {
    copyIrcLog();
  });

  document.getElementById("irc-clear-chat")?.addEventListener("click", () => {
    const hint = document.getElementById("irc-chat-msg");
    ircFeedFloorId = BP.state.ircAfterId;
    if (BP.state.sessionUsername) {
      sessionStorage.setItem(ircFloorStorageKey(), String(ircFeedFloorId));
    }
    BP.state.ircEvents = BP.state.ircEvents.filter((ev) => ircEventId(ev) > ircFeedFloorId);
    rerenderIrcFeed();
    if (hint) {
      hint.textContent = "Den chat cleared — new lines only.";
      hint.className = "bp-msg muted";
    }
  });

  document.getElementById("irc-disconnect")?.addEventListener("click", async () => {
    const hint = document.getElementById("irc-chat-msg");
    if (hint) {
      hint.textContent = "Disconnecting…";
      hint.className = "bp-msg muted";
    }
    try {
      const data = await BP.api("/api/irc/disconnect", { method: "POST", body: "{}" });
      if (hint) {
        hint.textContent = data.was_connected
          ? "IRC disconnected."
          : "Not connected to IRC.";
        hint.className = "bp-msg muted";
      }
      pollIrcFeed(true);
    } catch (err) {
      if (hint) {
        hint.textContent = err.message;
        hint.className = "bp-msg err";
      }
    }
  });

  function renderIrcEventDom(ev) {
    if (!ircFeedEl) return;
    const div = document.createElement("div");
    const dir = ev.dir || "in";
    div.className = "bp-irc-line bp-irc-line--" + dir;
    const target = ev.target ? "@" + ev.target + " " : "";
    const tag = ev.kind ? "[" + ev.kind + "] " : "";
    const who =
      ev.owner && ev.owner !== BP.state.sessionUsername ? "[" + ev.owner + "] " : "";
    const line =
      typeof BP.humanizeIrcFeedText === "function"
        ? BP.humanizeIrcFeedText(ev.text || "")
        : String(ev.text || "");
    div.innerHTML =
      '<span class="bp-irc-meta">' +
      BP.escapeHtml(formatTs(ev.ts)) +
      "</span>" +
      BP.escapeHtml(who + tag + target + line);
    ircFeedEl.appendChild(div);
  }

  function rerenderIrcFeed() {
    if (!ircFeedEl) return;
    ircFeedEl.innerHTML = "";
    BP.state.ircEvents.forEach((ev) => {
      if (ircEventVisible(ev)) renderIrcEventDom(ev);
    });
    if (ircAutoscroll && ircAutoscroll.checked) {
      ircFeedEl.scrollTop = ircFeedEl.scrollHeight;
    }
    syncIrcPanelVisibility();
  }

  function ircDenInUse() {
    const irc = BP.state.ircSnap;
    if (irc && irc.irc_connected) return true;
    if (BP.state.queueHasActiveJob) return true;
    if (BP.state.searchPollTimer || BP.state.pollTimer || BP.state.fetchPollTimer) return true;
    return (BP.state.ircEvents || []).some((ev) => ircEventVisible(ev));
  }

  function syncIrcPanelVisibility() {
    const panel = document.getElementById("irc-panel");
    if (!panel) return;
    const inUse = ircDenInUse();
    const wasHidden = panel.classList.contains("hidden");
    panel.classList.toggle("hidden", !inUse);
    if (inUse && wasHidden) panel.open = true;
  }

  async function pollIrcFeed(force) {
    if (!BP.state.authHeader && !force) return;
    try {
      const data = await BP.api("/api/irc/feed?after=" + encodeURIComponent(BP.state.ircAfterId));
      resetIrcFeedFloorIfStale(data.latest_id);
      let added = false;
      (data.events || []).forEach((ev) => {
        BP.state.ircEvents.push(ev);
        if (ev.id > BP.state.ircAfterId) BP.state.ircAfterId = ev.id;
        const text = String(ev.text || "");
        if (/\bSniff finished:/i.test(text) || /\bSoulseek:\s*\d+\s*match/i.test(text)) {
          void BP.syncActiveSearchResults?.();
          if (!BP.state.activeSearchJob) void BP.refreshQueue?.();
        }
        if (/\bDownloaded\b/i.test(text)) {
          void BP.refreshQueue?.();
          void BP.syncActiveDownload?.();
        }
        if (ircEventVisible(ev)) {
          renderIrcEventDom(ev);
          added = true;
        }
      });
      if (data.latest_id > BP.state.ircAfterId) BP.state.ircAfterId = data.latest_id;
      if (added && ircAutoscroll && ircAutoscroll.checked && ircFeedEl) {
        ircFeedEl.scrollTop = ircFeedEl.scrollHeight;
      }
      syncIrcPanelVisibility();
    } catch {
      /* ignore between polls */
    }
  }

  ircHideRaw?.addEventListener("change", () => {
    localStorage.setItem(IRC_HIDE_RAW_KEY, ircHideRaw.checked ? "1" : "0");
    rerenderIrcFeed();
  });
  ircHideOthers?.addEventListener("change", () => {
    localStorage.setItem(IRC_HIDE_OTHERS_KEY, ircHideOthers.checked ? "1" : "0");
    rerenderIrcFeed();
  });

  async function sendIrcChat() {
    const input = document.getElementById("irc-chat-input");
    const hint = document.getElementById("irc-chat-msg");
    const channelEl = document.getElementById("channel");
    if (!input || !ircBarkAllowed()) return;
    if (channelEl?.value === "all") return;
    const text = input.value.trim();
    if (!text) return;
    if (hint) {
      hint.textContent = "Sending…";
      hint.className = "bp-msg muted";
    }
    try {
      await BP.api("/api/irc/chat", {
        method: "POST",
        body: JSON.stringify({
          message: text,
          channel: channelEl ? channelEl.value : "irchighway:ebooks",
        }),
      });
      input.value = "";
      if (hint) {
        hint.textContent = "";
        hint.className = "bp-msg muted";
      }
      pollIrcFeed(true);
    } catch (err) {
      if (hint) {
        hint.textContent = err.message;
        hint.className = "bp-msg err";
      }
    }
  }

  document.getElementById("irc-chat-send")?.addEventListener("click", () => {
    sendIrcChat();
  });
  document.getElementById("irc-chat-input")?.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") {
      ev.preventDefault();
      sendIrcChat();
    }
  });

  function startIrcPoll() {
    if (BP.state.ircPollTimer) return;
    pollIrcFeed(true);
    BP.state.ircPollTimer = setInterval(pollIrcFeed, 1200);
  }

  function stopIrcPoll() {
    if (BP.state.ircPollTimer) {
      clearInterval(BP.state.ircPollTimer);
      BP.state.ircPollTimer = null;
    }
  }
  // exports
  BP.applyIrcTargetOptions = applyIrcTargetOptions;
  BP.copyIrcLog = copyIrcLog;
  BP.formatIrcEventPlain = formatIrcEventPlain;
  BP.formatTs = formatTs;
  BP.ircBarkAllowed = ircBarkAllowed;
  BP.ircEventId = ircEventId;
  BP.ircEventVisible = ircEventVisible;
  BP.ircFloorStorageKey = ircFloorStorageKey;
  BP.loadIrcFeedFloor = loadIrcFeedFloor;
  BP.loadIrcTargets = loadIrcTargets;
  BP.pollIrcFeed = pollIrcFeed;
  BP.renderIrcEventDom = renderIrcEventDom;
  BP.rerenderIrcFeed = rerenderIrcFeed;
  BP.resetIrcFeedLocal = resetIrcFeedLocal;
  BP.restoreSearchChannel = restoreSearchChannel;
  BP.sendIrcChat = sendIrcChat;
  BP.startIrcPoll = startIrcPoll;
  BP.stopIrcPoll = stopIrcPoll;
  BP.syncIrcChatChannel = syncIrcChatChannel;
  BP.syncIrcPanelVisibility = syncIrcPanelVisibility;
})(window.BookPup);
