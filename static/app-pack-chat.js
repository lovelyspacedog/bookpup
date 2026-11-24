(function (BP) {
  "use strict";

  const POLL_MS = 2000;
  const BOOKPUP_USER = "bookpup";
  const BUGBOT_USER = "bugbot";
  const FEATURECAT_USER = "featurecat";

  function virtualBotLabel(peer) {
    if (peer === BOOKPUP_USER) return "BookPup";
    if (peer === BUGBOT_USER) return "BugBot";
    if (peer === FEATURECAT_USER) return "FeatureCat";
    return peer;
  }

  function isVirtualBot(peer) {
    return peer === BOOKPUP_USER || peer === BUGBOT_USER || peer === FEATURECAT_USER;
  }

  function isVirtualBotSender(from) {
    return from === BOOKPUP_USER || from === BUGBOT_USER || from === FEATURECAT_USER;
  }

  function virtualBotOpenPath(peer) {
    if (peer === BUGBOT_USER) return "/api/pack/chat/bugbot/open";
    if (peer === FEATURECAT_USER) return "/api/pack/chat/featurecat/open";
    return null;
  }

  function virtualBotAlwaysVisible(peer) {
    return peer === BUGBOT_USER || peer === FEATURECAT_USER;
  }

  function virtualBotAlwaysOnline(peer) {
    return peer === BUGBOT_USER || peer === FEATURECAT_USER;
  }
  const feedEl = document.getElementById("pack-chat-feed");
  const presenceEl = document.getElementById("pack-presence-list");
  const inputEl = document.getElementById("pack-chat-input");
  const hintEl = document.getElementById("pack-chat-msg");
  const sendBtn = document.getElementById("pack-chat-send");
  const clearBtn = document.getElementById("pack-chat-clear");
  const badgeEl = document.getElementById("pack-tab-badge");
  const modePackBtn = document.getElementById("pack-chat-mode-pack");
  const modeLabelEl = document.getElementById("pack-chat-mode-label");
  const modeSubEl = document.getElementById("pack-chat-mode-sub");

  if (!BP.state.packChatAfterId) BP.state.packChatAfterId = 0;
  if (!BP.state.packChatDelAfter) BP.state.packChatDelAfter = 0;
  if (!BP.state.packChatById) BP.state.packChatById = {};
  if (BP.state.packChatUnread == null) BP.state.packChatUnread = 0;
  if (!BP.state.packChatUnreadByPeer) BP.state.packChatUnreadByPeer = {};
  if (BP.state.packChatTabActive == null) BP.state.packChatTabActive = false;
  if (BP.state.packChatBootstrapped == null) BP.state.packChatBootstrapped = false;
  if (BP.state.packChatMode == null) BP.state.packChatMode = "pack";
  if (BP.state.packChatDmPeer == null) BP.state.packChatDmPeer = "";

  function dmPeer(msg) {
    return msg && msg.to != null && String(msg.to).trim() !== "";
  }

  function messageInCurrentThread(msg) {
    const me = BP.state.sessionUsername || "";
    if (!msg) return false;
    if (BP.state.packChatMode === "pack") return !dmPeer(msg);
    const peer = BP.state.packChatDmPeer || "";
    if (!peer) return false;
    if (peer === BOOKPUP_USER) {
      return String(msg.username) === BOOKPUP_USER && String(msg.to) === me;
    }
    const from = String(msg.username);
    const to = String(msg.to || "");
    return (from === me && to === peer) || (from === peer && to === me);
  }

  function syncPackBadge() {
    if (!badgeEl) return;
    const n = BP.state.packChatUnread || 0;
    badgeEl.classList.toggle("hidden", n < 1);
    badgeEl.textContent = n > 9 ? "9+" : String(n);
  }

  function peerFromIncoming(msg) {
    if (!msg || !dmPeer(msg)) return "";
    const me = BP.state.sessionUsername || "";
    const from = String(msg.username);
    if (from === me) return "";
    if (isVirtualBotSender(from)) return from;
    if (String(msg.to || "").toLowerCase() === me.toLowerCase()) return from;
    return "";
  }

  function unreadPeerCount(peer) {
    const key = String(peer || "").trim();
    if (!key) return 0;
    const map = BP.state.packChatUnreadByPeer || {};
    if (map[key] != null) return map[key];
    const folded = key.toLowerCase();
    const alt = Object.keys(map).find((k) => k.toLowerCase() === folded);
    return alt ? map[alt] : 0;
  }

  function addUnreadPeer(peer, delta) {
    const key = String(peer || "").trim();
    if (!key || delta < 1) return;
    const map = BP.state.packChatUnreadByPeer;
    const folded = key.toLowerCase();
    const canon = Object.keys(map).find((k) => k.toLowerCase() === folded) || key;
    map[canon] = (map[canon] || 0) + delta;
  }

  function applyPeerBadge(li, peer) {
    if (!li || !peer) return;
    const n = unreadPeerCount(peer);
    let badge = li.querySelector(".bp-pack-peer-badge");
    if (n < 1) {
      badge?.remove();
      return;
    }
    const nameRow = li.querySelector(".bp-pack-presence-name-row");
    if (!badge) {
      badge = document.createElement("span");
      badge.className = "bp-pack-peer-badge";
      if (nameRow) nameRow.appendChild(badge);
      else li.querySelector(".bp-pack-presence-name")?.after(badge);
    }
    badge.textContent = n > 9 ? "9+" : String(n);
    badge.setAttribute("aria-label", n + " unread private message" + (n === 1 ? "" : "s"));
  }

  function syncAllPeerBadges() {
    presenceEl?.querySelectorAll("[data-pack-dm-peer]").forEach((li) => {
      applyPeerBadge(li, li.getAttribute("data-pack-dm-peer"));
    });
  }

  function clearPeerUnread(peer) {
    const key = String(peer || "").trim();
    if (!key) return;
    const map = BP.state.packChatUnreadByPeer;
    const folded = key.toLowerCase();
    const canon = Object.keys(map).find((k) => k.toLowerCase() === folded);
    if (!canon) return;
    const n = map[canon] || 0;
    if (n < 1) return;
    delete map[canon];
    BP.state.packChatUnread = Math.max(0, (BP.state.packChatUnread || 0) - n);
    syncPackBadge();
    syncAllPeerBadges();
  }

  function canDeleteMessage(msg) {
    const me = BP.state.sessionUsername || "";
    if (!me || !msg) return false;
    if (BP.state.sessionAdmin) return true;
    const from = String(msg.username);
    if (from === me) return true;
    if (isVirtualBotSender(from) && String(msg.to) === me) return true;
    return false;
  }

  function removeMessageDom(id) {
    const mid = Number(id);
    delete BP.state.packChatById[mid];
    const node = feedEl?.querySelector('[data-pack-msg-id="' + mid + '"]');
    node?.remove();
  }

  function renderMessageRow(msg) {
    if (!feedEl || !msg) return;
    const id = Number(msg.id);
    if (!id || !messageInCurrentThread(msg)) {
      const existing = feedEl.querySelector('[data-pack-msg-id="' + id + '"]');
      existing?.remove();
      return;
    }
    BP.state.packChatById[id] = msg;
    let row = feedEl.querySelector('[data-pack-msg-id="' + id + '"]');
    if (!row) {
      row = document.createElement("div");
      row.setAttribute("data-pack-msg-id", String(id));
      feedEl.appendChild(row);
    }
    const from = String(msg.username || "?");
    row.className =
      "bp-irc-line bp-pack-chat-line" +
      (isVirtualBotSender(from) ? " bp-pack-chat-line--sys" : "");
    const whoLabel = isVirtualBotSender(from) ? virtualBotLabel(from) : from;
    const delBtn = canDeleteMessage(msg)
      ? '<button type="button" class="bp-btn bp-btn--ghost bp-pack-chat-delete" data-pack-delete="' +
        id +
        '" aria-label="Delete message">Remove</button>'
      : "";
    row.innerHTML =
      '<p class="bp-pack-chat-line-body">' +
      '<span class="bp-irc-meta">' +
      BP.escapeHtml(formatTs(msg.ts)) +
      "</span> " +
      "<strong>" +
      BP.escapeHtml(whoLabel) +
      "</strong>: " +
      '<span class="bp-pack-chat-text">' +
      BP.escapeHtml(String(msg.text || "")) +
      "</span></p>" +
      delBtn;
  }

  function rerenderPackFeed() {
    if (!feedEl) return;
    feedEl.innerHTML = "";
    const rows = Object.values(BP.state.packChatById).sort((a, b) => Number(a.id) - Number(b.id));
    rows.forEach((m) => renderMessageRow(m));
    feedEl.scrollTop = feedEl.scrollHeight;
  }

  function formatTs(ts) {
    const d = new Date((Number(ts) || 0) * 1000);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  }

  function syncSidebarSelection() {
    if (modePackBtn) {
      const packOn = BP.state.packChatMode === "pack";
      modePackBtn.classList.toggle("active", packOn);
      modePackBtn.setAttribute("aria-pressed", packOn ? "true" : "false");
    }
    presenceEl?.querySelectorAll("[data-pack-dm-peer]").forEach((li) => {
      const peer = li.getAttribute("data-pack-dm-peer");
      const on =
        BP.state.packChatMode === "dm" &&
        String(BP.state.packChatDmPeer) === String(peer);
      li.classList.toggle("bp-pack-presence-item--active", on);
      li.setAttribute("aria-current", on ? "true" : "false");
    });
  }

  function syncModeUi() {
    const peer = BP.state.packChatDmPeer || "";
    const peerLabel = virtualBotLabel(peer);
    if (modeLabelEl) {
      modeLabelEl.textContent =
        BP.state.packChatMode === "pack"
          ? "Pack chat — everyone"
          : "Private message — " + peerLabel;
    }
    if (modeSubEl) {
      if (BP.state.packChatMode === "pack") {
        modeSubEl.textContent = "Messages here go to the whole household.";
      } else if (peer === BOOKPUP_USER) {
        modeSubEl.textContent = "Scheduled sniff alerts land here. Only you see this thread.";
      } else if (peer === BUGBOT_USER) {
        modeSubEl.textContent = "Describe a bug or rough edge — BugBot saves it for your admin.";
      } else if (peer === FEATURECAT_USER) {
        modeSubEl.textContent = "Pitch a feature — FeatureCat saves it for your admin.";
      } else {
        modeSubEl.textContent = "Only you and " + peerLabel + " see this thread.";
      }
    }
    if (inputEl) {
      inputEl.placeholder =
        BP.state.packChatMode === "pack"
          ? "Message everyone in the pack…"
          : "Private message to " + peerLabel + "…";
    }
    if (clearBtn) {
      clearBtn.classList.toggle("hidden", BP.state.packChatMode !== "pack" || !BP.state.sessionAdmin);
    }
    syncSidebarSelection();
    rerenderPackFeed();
  }

  function wireDmListItem(li, peer) {
    li.classList.add("bp-pack-presence-item--clickable");
    li.setAttribute("role", "button");
    li.tabIndex = 0;
    li.setAttribute("data-pack-dm-peer", peer);
    const label = virtualBotLabel(peer);
    li.setAttribute("aria-label", "Open private message with " + label);
  }

  function setPackMode() {
    BP.state.packChatMode = "pack";
    BP.state.packChatDmPeer = "";
    syncModeUi();
  }

  async function setDmMode(peer) {
    const me = BP.state.sessionUsername || "";
    const dest = String(peer || "").trim();
    if (!dest || dest === me) return;
    BP.state.packChatMode = "dm";
    BP.state.packChatDmPeer = dest;
    clearPeerUnread(dest);
    syncModeUi();
    const openPath = virtualBotOpenPath(dest);
    if (openPath) {
      try {
        await BP.api(openPath);
        await pollPackChat(true);
      } catch {
        /* intro retry on next poll */
      }
    }
  }

  function appendPresenceNameRow(name) {
    const nameRow = document.createElement("span");
    nameRow.className = "bp-pack-presence-name-row";
    const nameEl = document.createElement("span");
    nameEl.className = "bp-pack-presence-name";
    nameEl.textContent = name;
    nameRow.appendChild(nameEl);
    return nameRow;
  }

  function renderPresence(list) {
    if (!presenceEl) return;
    const me = BP.state.sessionUsername || "";
    presenceEl.innerHTML = "";
    (list || []).forEach((row) => {
      const li = document.createElement("li");
      li.className = "bp-pack-presence-item";
      const name = row.username || "";
      if (name && name !== me) {
        wireDmListItem(li, name);
      }
      const dot = document.createElement("span");
      dot.className = "bp-pack-presence-dot" + (row.online ? " bp-pack-presence-dot--on" : "");
      dot.setAttribute("aria-hidden", "true");
      if (row.online) dot.title = "Online";
      const nameRow = appendPresenceNameRow(name);
      const stat = document.createElement("span");
      stat.className = "bp-pack-presence-action muted";
      stat.textContent = name !== me ? "Open PM →" : row.online ? "Online" : "Offline";
      li.appendChild(dot);
      li.appendChild(nameRow);
      li.appendChild(stat);
      if (name && name !== me) applyPeerBadge(li, name);
      presenceEl.appendChild(li);
    });
    (BP.state.packChatPeers || []).forEach((peerRow) => {
      const name = String(peerRow.username || "");
      if (!name || name === me || isVirtualBot(name)) return;
      if (presenceEl.querySelector('[data-pack-dm-peer="' + CSS.escape(name) + '"]')) return;
      const li = document.createElement("li");
      li.className = "bp-pack-presence-item";
      wireDmListItem(li, name);
      const dot = document.createElement("span");
      dot.className = "bp-pack-presence-dot";
      dot.setAttribute("aria-hidden", "true");
      const nameRow = appendPresenceNameRow(name);
      const stat = document.createElement("span");
      stat.className = "bp-pack-presence-action muted";
      stat.textContent = "Open PM →";
      li.appendChild(dot);
      li.appendChild(nameRow);
      li.appendChild(stat);
      applyPeerBadge(li, name);
      presenceEl.appendChild(li);
    });
    function appendVirtualBotRow(botId, displayName, actionLabel) {
      const peer = (BP.state.packChatPeers || []).some((p) => p.username === botId);
      const hasMsg = Object.values(BP.state.packChatById).some((m) => {
        const from = String(m.username);
        const to = String(m.to || "");
        return (from === botId && to === me) || (from === me && to === botId);
      });
      const alwaysShow = virtualBotAlwaysVisible(botId);
      if (!(alwaysShow || peer || hasMsg)) return;
      if (presenceEl.querySelector('[data-pack-dm-peer="' + CSS.escape(botId) + '"]')) return;
      const li = document.createElement("li");
      li.className = "bp-pack-presence-item";
      wireDmListItem(li, botId);
      const dot = document.createElement("span");
      dot.className = "bp-pack-presence-dot bp-pack-presence-dot--sys";
      if (virtualBotAlwaysOnline(botId)) {
        dot.classList.add("bp-pack-presence-dot--on");
        dot.title = "Online";
      }
      dot.setAttribute("aria-hidden", "true");
      const nameRow = appendPresenceNameRow(displayName);
      const stat = document.createElement("span");
      stat.className = "bp-pack-presence-action muted";
      stat.textContent = actionLabel;
      li.appendChild(dot);
      li.appendChild(nameRow);
      li.appendChild(stat);
      applyPeerBadge(li, botId);
      presenceEl.appendChild(li);
    }
    appendVirtualBotRow(BOOKPUP_USER, "BookPup", "Open alerts →");
    appendVirtualBotRow(BUGBOT_USER, "BugBot", "Report bugs →");
    appendVirtualBotRow(FEATURECAT_USER, "FeatureCat", "Request features →");
    syncSidebarSelection();
    syncAllPeerBadges();
  }

  function bumpUnread(fromMsg) {
    if (BP.state.packChatTabActive && messageInCurrentThread(fromMsg)) return;
    const me = BP.state.sessionUsername || "";
    const from = String(fromMsg?.username || "");
    if (fromMsg && from.toLowerCase() === me.toLowerCase()) return;
    const peer = peerFromIncoming(fromMsg);
    if (peer) {
      addUnreadPeer(peer, 1);
      BP.state.packChatUnread = (BP.state.packChatUnread || 0) + 1;
      syncPackBadge();
      syncAllPeerBadges();
      return;
    }
    BP.state.packChatUnread = (BP.state.packChatUnread || 0) + 1;
    syncPackBadge();
  }

  async function pollPackChat(force) {
    if (!BP.state.authHeader && !force) return;
    try {
      const q =
        "/api/pack/chat?after=" +
        encodeURIComponent(BP.state.packChatAfterId) +
        "&del_after=" +
        encodeURIComponent(BP.state.packChatDelAfter);
      const data = await BP.api(q);
      const wasBootstrapped = BP.state.packChatBootstrapped;
      let changed = false;
      (data.removed || []).forEach((id) => {
        removeMessageDom(id);
        changed = true;
      });
      if (Number(data.latest_del_seq) > BP.state.packChatDelAfter) {
        BP.state.packChatDelAfter = Number(data.latest_del_seq);
      }
      (data.messages || []).forEach((msg) => {
        BP.state.packChatById[Number(msg.id)] = msg;
        if (Number(msg.id) > BP.state.packChatAfterId) BP.state.packChatAfterId = Number(msg.id);
        if (wasBootstrapped) bumpUnread(msg);
        changed = true;
      });
      if (Number(data.latest_id) > BP.state.packChatAfterId) BP.state.packChatAfterId = Number(data.latest_id);
      if (data.peers) BP.state.packChatPeers = data.peers;
      if (data.presence) renderPresence(data.presence);
      else if (data.peers) renderPresence([]);
      if (changed) rerenderPackFeed();
      BP.state.packChatBootstrapped = true;
    } catch {
      /* ignore between polls */
    }
  }

  async function sendPackChat() {
    if (!inputEl) return;
    const text = inputEl.value.trim();
    if (!text) return;
    const body = { message: text };
    if (BP.state.packChatMode === "dm" && BP.state.packChatDmPeer) {
      if (BP.state.packChatDmPeer === BOOKPUP_USER) {
        if (hintEl) {
          hintEl.textContent = "BookPup alerts are read-only.";
          hintEl.className = "bp-msg err";
        }
        return;
      }
      body.to = BP.state.packChatDmPeer;
    }
    if (hintEl) {
      hintEl.textContent = "Sending…";
      hintEl.className = "bp-msg muted";
    }
    try {
      await BP.api("/api/pack/chat", {
        method: "POST",
        body: JSON.stringify(body),
      });
      inputEl.value = "";
      if (hintEl) {
        hintEl.textContent = "";
        hintEl.className = "bp-msg muted";
      }
      await pollPackChat(true);
    } catch (err) {
      if (hintEl) {
        hintEl.textContent = err.message || "Could not send";
        hintEl.className = "bp-msg err";
      }
    }
  }

  async function deletePackMessage(id) {
    const msg = BP.state.packChatById[id];
    const me = BP.state.sessionUsername || "";
    if (
      msg &&
      String(msg.username) !== me &&
      !isVirtualBotSender(String(msg.username)) &&
      BP.state.sessionAdmin
    ) {
      if (!window.confirm("Remove this message?")) return;
    }
    try {
      await BP.api("/api/pack/chat/" + encodeURIComponent(String(id)), { method: "DELETE" });
      await pollPackChat(true);
    } catch (err) {
      BP.showAppToast?.("Pack chat", err.message || "Could not delete", "err");
    }
  }

  async function clearPackChat() {
    if (!window.confirm("Clear all pack channel messages? Private messages are kept.")) return;
    try {
      await BP.api("/api/pack/chat/clear", { method: "POST", body: "{}" });
      Object.keys(BP.state.packChatById).forEach((k) => {
        const m = BP.state.packChatById[k];
        if (m && !dmPeer(m)) delete BP.state.packChatById[k];
      });
      await pollPackChat(true);
    } catch (err) {
      BP.showAppToast?.("Pack chat", err.message || "Could not clear", "err");
    }
  }

  function startPackChatPoll() {
    if (BP.state.packChatPollTimer) return;
    void pollPackChat(true);
    BP.state.packChatPollTimer = setInterval(() => pollPackChat(false), POLL_MS);
  }

  function stopPackChatPoll() {
    if (BP.state.packChatPollTimer) {
      clearInterval(BP.state.packChatPollTimer);
      BP.state.packChatPollTimer = null;
    }
  }

  function resetPackChatLocal() {
    stopPackChatPoll();
    BP.state.packChatAfterId = 0;
    BP.state.packChatDelAfter = 0;
    BP.state.packChatById = {};
    BP.state.packChatUnread = 0;
    BP.state.packChatUnreadByPeer = {};
    BP.state.packChatTabActive = false;
    BP.state.packChatBootstrapped = false;
    BP.state.packChatMode = "pack";
    BP.state.packChatDmPeer = "";
    BP.state.packChatPeers = [];
    if (feedEl) feedEl.innerHTML = "";
    if (presenceEl) presenceEl.innerHTML = "";
    syncPackBadge();
    syncModeUi();
  }

  function onPackChatTabActive() {
    BP.state.packChatTabActive = true;
    BP.state.packChatUnread = 0;
    syncPackBadge();
    setPackMode();
    if (!BP.state.packChatBootstrapped) void pollPackChat(true);
    else if (feedEl) feedEl.scrollTop = feedEl.scrollHeight;
  }

  function onPackChatTabInactive() {
    BP.state.packChatTabActive = false;
  }

  modePackBtn?.addEventListener("click", () => setPackMode());
  presenceEl?.addEventListener("click", (ev) => {
    const item = ev.target.closest("[data-pack-dm-peer]");
    if (!item) return;
    setDmMode(item.getAttribute("data-pack-dm-peer"));
  });
  presenceEl?.addEventListener("keydown", (ev) => {
    if (ev.key !== "Enter" && ev.key !== " ") return;
    const item = ev.target.closest("[data-pack-dm-peer]");
    if (!item) return;
    ev.preventDefault();
    setDmMode(item.getAttribute("data-pack-dm-peer"));
  });

  sendBtn?.addEventListener("click", () => void sendPackChat());
  inputEl?.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") {
      ev.preventDefault();
      void sendPackChat();
    }
  });
  feedEl?.addEventListener("click", (ev) => {
    const btn = ev.target.closest("[data-pack-delete]");
    if (!btn) return;
    const id = parseInt(btn.getAttribute("data-pack-delete") || "", 10);
    if (id > 0) void deletePackMessage(id);
  });
  clearBtn?.addEventListener("click", () => void clearPackChat());

  syncModeUi();

  BP.startPackChatPoll = startPackChatPoll;
  BP.stopPackChatPoll = stopPackChatPoll;
  BP.resetPackChatLocal = resetPackChatLocal;
  BP.pollPackChat = pollPackChat;
  BP.onPackChatTabActive = onPackChatTabActive;
  BP.onPackChatTabInactive = onPackChatTabInactive;
})(window.BookPup);