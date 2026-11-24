(function (BP) {
  "use strict";

  const POLL_MS = 2000;
  const feedEl = document.getElementById("pack-chat-feed");
  const presenceEl = document.getElementById("pack-presence-list");
  const inputEl = document.getElementById("pack-chat-input");
  const hintEl = document.getElementById("pack-chat-msg");
  const sendBtn = document.getElementById("pack-chat-send");
  const clearBtn = document.getElementById("pack-chat-clear");
  const badgeEl = document.getElementById("pack-tab-badge");

  if (!BP.state.packChatAfterId) BP.state.packChatAfterId = 0;
  if (!BP.state.packChatDelAfter) BP.state.packChatDelAfter = 0;
  if (!BP.state.packChatById) BP.state.packChatById = {};
  if (BP.state.packChatUnread == null) BP.state.packChatUnread = 0;
  if (BP.state.packChatTabActive == null) BP.state.packChatTabActive = false;
  if (BP.state.packChatBootstrapped == null) BP.state.packChatBootstrapped = false;

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

  function syncPackBadge() {
    if (!badgeEl) return;
    const n = BP.state.packChatUnread || 0;
    badgeEl.classList.toggle("hidden", n < 1);
    badgeEl.textContent = n > 9 ? "9+" : String(n);
  }

  function canDeleteMessage(msg) {
    const me = BP.state.sessionUsername || "";
    if (!me || !msg) return false;
    if (String(msg.username) === me) return true;
    return !!BP.state.sessionAdmin;
  }

  function removeMessageDom(id) {
    const mid = Number(id);
    delete BP.state.packChatById[mid];
    const node = feedEl?.querySelector('[data-pack-msg-id="' + mid + '"]');
    node?.remove();
  }

  function renderMessageDom(msg) {
    if (!feedEl || !msg) return;
    const id = Number(msg.id);
    if (!id) return;
    let row = feedEl.querySelector('[data-pack-msg-id="' + id + '"]');
    if (!row) {
      row = document.createElement("div");
      row.className = "bp-irc-line bp-pack-chat-line";
      row.setAttribute("data-pack-msg-id", String(id));
      feedEl.appendChild(row);
    }
    const who = String(msg.username || "?");
    const delBtn = canDeleteMessage(msg)
      ? '<button type="button" class="bp-btn bp-btn--ghost bp-pack-chat-delete" data-pack-delete="' +
        id +
        '" aria-label="Delete message">Remove</button>'
      : "";
    row.innerHTML =
      '<span class="bp-irc-meta">' +
      BP.escapeHtml(formatTs(msg.ts)) +
      "</span> " +
      "<strong>" +
      BP.escapeHtml(who) +
      "</strong>: " +
      BP.escapeHtml(String(msg.text || "")) +
      " " +
      delBtn;
    BP.state.packChatById[id] = msg;
  }

  function rerenderPackFeed() {
    if (!feedEl) return;
    feedEl.innerHTML = "";
    const rows = Object.values(BP.state.packChatById).sort((a, b) => Number(a.id) - Number(b.id));
    rows.forEach((m) => renderMessageDom(m));
    feedEl.scrollTop = feedEl.scrollHeight;
  }

  function renderPresence(list) {
    if (!presenceEl) return;
    presenceEl.innerHTML = "";
    (list || []).forEach((row) => {
      const li = document.createElement("li");
      li.className = "bp-pack-presence-item";
      const dot = document.createElement("span");
      dot.className = "bp-pack-presence-dot" + (row.online ? " bp-pack-presence-dot--on" : "");
      dot.setAttribute("aria-hidden", "true");
      const name = document.createElement("span");
      name.textContent = row.username || "";
      const stat = document.createElement("span");
      stat.className = "muted bp-pack-presence-stat";
      stat.textContent = row.online ? "Online" : "Offline";
      li.appendChild(dot);
      li.appendChild(name);
      li.appendChild(stat);
      presenceEl.appendChild(li);
    });
  }

  function bumpUnread(fromMsg) {
    if (BP.state.packChatTabActive) return;
    const me = BP.state.sessionUsername || "";
    if (fromMsg && String(fromMsg.username) === me) return;
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
        renderMessageDom(msg);
        if (Number(msg.id) > BP.state.packChatAfterId) BP.state.packChatAfterId = Number(msg.id);
        if (wasBootstrapped && !BP.state.packChatTabActive) bumpUnread(msg);
        changed = true;
      });
      if (Number(data.latest_id) > BP.state.packChatAfterId) BP.state.packChatAfterId = Number(data.latest_id);
      if (data.presence) renderPresence(data.presence);
      if (changed && BP.state.packChatTabActive && feedEl) {
        feedEl.scrollTop = feedEl.scrollHeight;
      }
      BP.state.packChatBootstrapped = true;
    } catch {
      /* ignore between polls */
    }
  }

  async function sendPackChat() {
    if (!inputEl) return;
    const text = inputEl.value.trim();
    if (!text) return;
    if (hintEl) {
      hintEl.textContent = "Sending…";
      hintEl.className = "bp-msg muted";
    }
    try {
      await BP.api("/api/pack/chat", {
        method: "POST",
        body: JSON.stringify({ message: text }),
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
    if (msg && String(msg.username) !== me && BP.state.sessionAdmin) {
      if (!window.confirm("Remove this message for the whole pack?")) return;
    }
    try {
      await BP.api("/api/pack/chat/" + encodeURIComponent(String(id)), { method: "DELETE" });
      await pollPackChat(true);
    } catch (err) {
      BP.showAppToast?.("Pack chat", err.message || "Could not delete", "err");
    }
  }

  async function clearPackChat() {
    if (!window.confirm("Clear all pack chat messages for everyone?")) return;
    try {
      await BP.api("/api/pack/chat/clear", { method: "POST", body: "{}" });
      BP.state.packChatById = {};
      BP.state.packChatAfterId = 0;
      if (feedEl) feedEl.innerHTML = "";
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
    BP.state.packChatTabActive = false;
    BP.state.packChatBootstrapped = false;
    if (feedEl) feedEl.innerHTML = "";
    if (presenceEl) presenceEl.innerHTML = "";
    syncPackBadge();
  }

  function onPackChatTabActive() {
    BP.state.packChatTabActive = true;
    BP.state.packChatUnread = 0;
    syncPackBadge();
    if (!BP.state.packChatBootstrapped) {
      void pollPackChat(true);
    } else if (feedEl) {
      feedEl.scrollTop = feedEl.scrollHeight;
    }
    if (clearBtn) clearBtn.classList.toggle("hidden", !BP.state.sessionAdmin);
  }

  function onPackChatTabInactive() {
    BP.state.packChatTabActive = false;
  }

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

  BP.startPackChatPoll = startPackChatPoll;
  BP.stopPackChatPoll = stopPackChatPoll;
  BP.resetPackChatLocal = resetPackChatLocal;
  BP.pollPackChat = pollPackChat;
  BP.onPackChatTabActive = onPackChatTabActive;
  BP.onPackChatTabInactive = onPackChatTabInactive;
})(window.BookPup);