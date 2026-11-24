(function (BP) {
  "use strict";

  const REACTIONS = [
    { key: "paw", label: "🐾" },
    { key: "heart", label: "♥" },
    { key: "laugh", label: "😄" },
  ];

  if (BP.state.packChatReplyParentId == null) BP.state.packChatReplyParentId = null;
  if (!BP.state.packChatPendingAttach) BP.state.packChatPendingAttach = null;

  const replyBanner = document.getElementById("pack-chat-reply-banner");
  const pendingAttachEl = document.getElementById("pack-chat-pending-attach");
  const attachBtn = document.getElementById("pack-chat-attach-btn");
  const attachMenu = document.getElementById("pack-attach-menu");
  const bookModal = document.getElementById("pack-attach-book-modal");
  const inviteModal = document.getElementById("pack-attach-invite-modal");

  function composeContextAllowsAttach() {
    if (BP.state.packChatMode === "dm") {
      const p = BP.state.packChatDmPeer || "";
      if (p === "bookpup" || p === "bugbot" || p === "featurecat") return false;
    }
    return true;
  }

  function syncAttachChrome() {
    const ok = composeContextAllowsAttach();
    attachBtn?.classList.toggle("hidden", !ok);
    if (!ok) {
      BP.state.packChatPendingAttach = null;
      updatePendingAttachUi();
      cancelReply();
    }
  }

  function cancelReply() {
    BP.state.packChatReplyParentId = null;
    if (replyBanner) {
      replyBanner.classList.add("hidden");
      replyBanner.textContent = "";
    }
  }

  function startReply(msgId) {
    const msg = BP.state.packChatById[msgId];
    if (!msg) return;
    BP.state.packChatReplyParentId = msgId;
    if (replyBanner) {
      replyBanner.classList.remove("hidden");
      replyBanner.innerHTML =
        'Replying to <strong>' +
        BP.escapeHtml(String(msg.username)) +
        '</strong>: “' +
        BP.escapeHtml(String(msg.text || "").slice(0, 80)) +
        '…” <button type="button" class="bp-link-btn" id="pack-chat-reply-cancel">Cancel</button>';
      document.getElementById("pack-chat-reply-cancel")?.addEventListener("click", cancelReply);
    }
    document.getElementById("pack-chat-input")?.focus();
  }

  function updatePendingAttachUi() {
    if (!pendingAttachEl) return;
    const p = BP.state.packChatPendingAttach;
    if (!p) {
      pendingAttachEl.classList.add("hidden");
      pendingAttachEl.replaceChildren();
      syncAttachButtonState();
      return;
    }
    pendingAttachEl.classList.remove("hidden");
    pendingAttachEl.replaceChildren();
    const label = document.createElement("span");
    if (p.type === "library_book") {
      label.textContent =
        "Attached: " +
        (p.title || "book") +
        (p.intent === "offer_copy" ? " (send copy)" : " (recommend)");
    } else if (p.type === "kennel_invite") {
      label.textContent = "Attached: Kennel invite for " + (p.requester || "?");
    }
    const clear = document.createElement("button");
    clear.type = "button";
    clear.className = "bp-pack-pending-clear";
    clear.setAttribute("aria-label", "Remove attachment");
    clear.textContent = "Remove";
    clear.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      clearPendingAttach();
    });
    pendingAttachEl.append(label, clear);
    syncAttachButtonState();
  }

  function clearPendingAttach() {
    BP.state.packChatPendingAttach = null;
    updatePendingAttachUi();
    syncAttachButtonState();
    attachMenu?.classList.add("hidden");
  }

  function syncAttachButtonState() {
    if (!attachBtn) return;
    const on = !!BP.state.packChatPendingAttach;
    attachBtn.textContent = on ? "Unattach" : "Attach…";
    attachBtn.classList.toggle("bp-pack-attach-btn--active", on);
    attachBtn.setAttribute("aria-pressed", on ? "true" : "false");
    if (on) {
      attachBtn.title = "Remove pending attachment";
    } else {
      attachBtn.title = "Attach catalogued book or kennel invite";
    }
  }

  function attachmentCardHtml(att, msgId, idx) {
    const actions = att.actions || {};
    let inner = "";
    if (att.type === "kennel_invite") {
      const owner = BP.escapeHtml(att.owner || "");
      const req = BP.escapeHtml(att.requester || "");
      const st = BP.escapeHtml(att.status || "");
      inner =
        '<div class="bp-pack-card bp-pack-card--invite">' +
        "<strong>Kennel invite</strong> — " +
        owner +
        " → " +
        req +
        " <span class='muted'>(" +
        st +
        ")</span>";
      if (actions.can_accept_invite) {
        inner +=
          '<p class="bp-pack-card-actions"><button type="button" class="bp-btn" data-pack-invite-accept="' +
          att.grant_id +
          '" data-mode="lend">Accept lend</button> ' +
          '<button type="button" class="bp-btn" data-pack-invite-accept="' +
          att.grant_id +
          '" data-mode="give">Accept give</button> ' +
          '<button type="button" class="bp-btn" data-pack-invite-decline="' +
          att.grant_id +
          '">Decline</button></p>';
      }
      if (actions.can_browse) {
        inner +=
          '<p><button type="button" class="bp-btn" data-pack-browse-owner="' +
          BP.escapeHtml(att.owner || "") +
          '">Open kennel</button></p>';
      }
      inner += "</div>";
    } else if (att.type === "library_book") {
      const title = BP.escapeHtml(att.title || "Untitled");
      const auth = BP.escapeHtml(att.authors || "");
      inner =
        '<div class="bp-pack-card bp-pack-card--book">' +
        "<strong>" +
        title +
        "</strong>" +
        (auth ? " · " + auth : "") +
        (att.item_gone ? ' <span class="muted">(gone)</span>' : "");
      inner += '<p class="bp-pack-card-actions">';
      if (actions.can_open_kennel) {
        inner +=
          '<button type="button" class="bp-btn" data-pack-lib-open="' +
          BP.escapeHtml(att.owner || "") +
          '" data-item="' +
          BP.escapeHtml(att.item_id || "") +
          '">Open Kennel</button> ';
      }
      if (actions.can_read) {
        inner +=
          '<button type="button" class="bp-btn" data-pack-lib-read="' +
          BP.escapeHtml(att.owner || "") +
          '" data-item="' +
          BP.escapeHtml(att.item_id || "") +
          '">Read</button> ';
      }
      if (actions.can_claim_copy) {
        inner +=
          '<button type="button" class="bp-btn primary" data-pack-claim="' +
          msgId +
          '" data-idx="' +
          idx +
          '">Add to my kennel</button> ';
      }
      if (actions.can_ask) {
        inner +=
          '<button type="button" class="bp-btn" data-pack-ask="1" data-from="' +
          BP.escapeHtml(att.owner || "") +
          '" data-title="' +
          title +
          '">Ask for this book</button>';
      }
      if (att.claimed_by) {
        inner += ' <span class="muted">Claimed by ' + BP.escapeHtml(att.claimed_by) + "</span>";
      }
      inner += "</p></div>";
    }
    return inner;
  }

  function reactionsHtml(msg) {
    const rx = msg.reactions || {};
    const me = BP.state.sessionUsername || "";
    const mid = Number(msg.id);
    let bar = '<div class="bp-pack-reactions">';
    REACTIONS.forEach((r) => {
      const users = rx[r.key] || [];
      const on = users.includes(me);
      bar +=
        '<button type="button" class="bp-pack-react' +
        (on ? " bp-pack-react--on" : "") +
        '" data-pack-react="' +
        mid +
        '" data-emoji="' +
        r.key +
        '" aria-pressed="' +
        (on ? "true" : "false") +
        '" title="' +
        r.key +
        '">' +
        r.label +
        (users.length ? '<span class="bp-pack-react-count">' + users.length + "</span>" : "") +
        "</button>";
    });
    bar += "</div>";
    return bar;
  }

  BP.renderPackMessageRowV2 = function renderPackMessageRowV2(msg) {
    const feedEl = document.getElementById("pack-chat-feed");
    if (!feedEl || !msg) return;
    const id = Number(msg.id);
    if (!id) return;
    let row = feedEl.querySelector('[data-pack-msg-id="' + id + '"]');
    if (!row) {
      row = document.createElement("div");
      row.setAttribute("data-pack-msg-id", String(id));
      feedEl.appendChild(row);
    }
    const from = String(msg.username || "?");
    const isVirtualBotSender =
      from === "bookpup" || from === "bugbot" || from === "featurecat";
    row.className =
      "bp-irc-line bp-pack-chat-line" +
      (isVirtualBotSender ? " bp-pack-chat-line--sys" : "") +
      (msg.parent_id ? " bp-pack-chat-line--reply" : "");
    const whoLabel =
      from === "bookpup"
        ? "BookPup"
        : from === "bugbot"
          ? "BugBot"
          : from === "featurecat"
            ? "FeatureCat"
            : from;
    let body = '<div class="bp-pack-chat-line-main">';
    if (msg.parent && msg.parent.text_snippet) {
      body +=
        '<p class="bp-pack-reply-quote muted">↩ ' +
        BP.escapeHtml(String(msg.parent.username || "")) +
        ": " +
        BP.escapeHtml(msg.parent.text_snippet) +
        "</p>";
    }
    body += '<div class="bp-pack-chat-head-row">';
    body +=
      '<span class="bp-irc-meta">' +
      (msg.ts ? new Date(msg.ts * 1000).toLocaleString() : "") +
      "</span> ";
    body += "<strong>" + BP.escapeHtml(whoLabel) + "</strong>";
    if (!isVirtualBotSender && BP.state.sessionUsername) {
      body +=
        ' <button type="button" class="bp-pack-msg-link" data-pack-reply="' + id + '">Reply</button>';
    }
    body += "</div>";
    if (msg.text) {
      body += '<p class="bp-pack-chat-line-body"><span class="bp-pack-chat-text">' +
        BP.escapeHtml(String(msg.text)) +
        "</span></p>";
    }
    (msg.attachments || []).forEach((att, idx) => {
      body += attachmentCardHtml(att, id, idx);
    });
    body += '<div class="bp-pack-chat-footer">';
    body += reactionsHtml(msg);
    if (BP.canDeletePackMessage?.(msg)) {
      body +=
        '<button type="button" class="bp-pack-msg-link bp-pack-msg-link--danger" data-pack-delete="' +
        id +
        '" aria-label="Remove message">Remove</button>';
    }
    body += "</div></div>";
    row.innerHTML = body;
  };

  const origRerender = BP.rerenderPackFeedHook;
  BP.hookPackChatV2 = function () {
    const feedEl = document.getElementById("pack-chat-feed");
    if (!feedEl) return;
  };

  BP.packChatSendExtras = function (body) {
    if (BP.state.packChatReplyParentId) {
      body.parent_id = BP.state.packChatReplyParentId;
    }
    const p = BP.state.packChatPendingAttach;
    if (p) {
      body.attachments = [p.raw || p];
    }
    return body;
  };

  BP.packChatAfterSend = function () {
    clearPendingAttach();
    cancelReply();
  };

  async function openBookPicker() {
    if (!bookModal) return;
    const list = document.getElementById("pack-attach-book-list");
    if (!list) return;
    list.innerHTML = "<p class='muted'>Loading…</p>";
    bookModal.classList.remove("hidden");
    let items = BP.getLibraryItems ? BP.getLibraryItems() : [];
    const reg = items.filter((it) => {
      const src = String(it.source || "").toLowerCase();
      return src === "registered" || src === "calibre_import";
    });
    if (!reg.length) {
      try {
        const lib = await BP.api("/api/library");
        items = lib.items || [];
      } catch {
        items = [];
      }
    }
    const catalog = (items.length ? items : reg).filter((it) => {
      const src = String(it.source || "").toLowerCase();
      return src === "registered" || src === "calibre_import";
    });
    list.innerHTML = "";
    if (!catalog.length) {
      list.innerHTML = "<p class='muted'>No catalogued bones in your kennel.</p>";
      return;
    }
    catalog.forEach((it) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "bp-btn bp-pack-pick-book";
      btn.textContent = (it.title || "Untitled") + (it.authors ? " · " + it.authors : "");
      btn.addEventListener("click", () => {
        const intent =
          document.querySelector('input[name="pack-book-intent"]:checked')?.value || "recommend";
        BP.state.packChatPendingAttach = {
          type: "library_book",
          item_id: it.id,
          intent,
          title: it.title,
          raw: { type: "library_book", item_id: it.id, intent },
        };
        updatePendingAttachUi();
        syncAttachButtonState();
        bookModal.classList.add("hidden");
      });
      list.appendChild(btn);
    });
  }

  function openInvitePicker() {
    if (!inviteModal) return;
    inviteModal.classList.remove("hidden");
    const sel = document.getElementById("pack-invite-user");
    if (!sel) return;
    sel.innerHTML = "";
    const me = BP.state.sessionUsername || "";
    (BP.state.sessionRoster || []).forEach((name) => {
      if (!name || name === me) return;
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      sel.appendChild(opt);
    });
    if (BP.state.packChatMode === "dm" && BP.state.packChatDmPeer) {
      sel.value = BP.state.packChatDmPeer;
    }
  }

  attachBtn?.addEventListener("click", () => {
    if (BP.state.packChatPendingAttach) {
      clearPendingAttach();
      return;
    }
    attachMenu?.classList.toggle("hidden");
  });
  document.getElementById("pack-attach-book")?.addEventListener("click", () => {
    attachMenu?.classList.add("hidden");
    void openBookPicker();
  });
  document.getElementById("pack-attach-kennel")?.addEventListener("click", () => {
    attachMenu?.classList.add("hidden");
    openInvitePicker();
  });
  document.getElementById("pack-attach-book-close")?.addEventListener("click", () => {
    bookModal?.classList.add("hidden");
  });
  document.getElementById("pack-invite-save")?.addEventListener("click", () => {
    const requester = document.getElementById("pack-invite-user")?.value || "";
    const mode = document.getElementById("pack-invite-mode")?.value || "";
    if (!requester) return;
    const raw = { type: "kennel_invite", requester };
    if (mode) raw.mode_suggested = mode;
    BP.state.packChatPendingAttach = {
      type: "kennel_invite",
      requester,
      raw,
    };
    updatePendingAttachUi();
    syncAttachButtonState();
    inviteModal?.classList.add("hidden");
  });
  document.getElementById("pack-attach-invite-close")?.addEventListener("click", () => {
    inviteModal?.classList.add("hidden");
  });

  document.getElementById("pack-chat-feed")?.addEventListener("click", async (ev) => {
    const reply = ev.target.closest("[data-pack-reply]");
    if (reply) {
      startReply(parseInt(reply.getAttribute("data-pack-reply"), 10));
      return;
    }
    const react = ev.target.closest("[data-pack-react]");
    if (react) {
      const mid = react.getAttribute("data-pack-react");
      const emoji = react.getAttribute("data-emoji");
      try {
        await BP.api("/api/pack/chat/" + encodeURIComponent(mid) + "/reactions", {
          method: "POST",
          body: JSON.stringify({ emoji }),
        });
        await BP.pollPackChat(true);
      } catch (err) {
        BP.showAppToast?.("Pack chat", err.message, "err");
      }
      return;
    }
    const acc = ev.target.closest("[data-pack-invite-accept]");
    if (acc) {
      const gid = acc.getAttribute("data-pack-invite-accept");
      const mode = acc.getAttribute("data-mode");
      try {
        await BP.api("/api/library/shares/" + gid + "/accept-invite", {
          method: "POST",
          body: JSON.stringify({ mode }),
        });
        await BP.pollPackChat(true);
        BP.showAppToast?.("Pack chat", "Kennel invite accepted", "ok");
      } catch (err) {
        BP.showAppToast?.("Pack chat", err.message, "err");
      }
      return;
    }
    const dec = ev.target.closest("[data-pack-invite-decline]");
    if (dec) {
      try {
        await BP.api("/api/library/shares/" + dec.getAttribute("data-pack-invite-decline") + "/decline-invite", {
          method: "POST",
          body: "{}",
        });
        await BP.pollPackChat(true);
      } catch (err) {
        BP.showAppToast?.("Pack chat", err.message, "err");
      }
      return;
    }
    const claim = ev.target.closest("[data-pack-claim]");
    if (claim) {
      try {
        await BP.api("/api/pack/chat/attachments/claim-copy", {
          method: "POST",
          body: JSON.stringify({
            message_id: parseInt(claim.getAttribute("data-pack-claim"), 10),
            attachment_index: parseInt(claim.getAttribute("data-idx"), 10),
          }),
        });
        await BP.pollPackChat(true);
        BP.loadLibrary?.();
        BP.showAppToast?.("Pack chat", "Book added to your kennel", "ok");
      } catch (err) {
        BP.showAppToast?.("Pack chat", err.message, "err");
      }
      return;
    }
    const browse = ev.target.closest("[data-pack-browse-owner]");
    if (browse) {
      const owner = browse.getAttribute("data-pack-browse-owner");
      const sel = document.getElementById("lib-browse-select");
      if (sel) {
        sel.value = owner;
        sel.dispatchEvent(new Event("change"));
      }
      BP.activateTab?.(BP.tabButton?.("library"));
      return;
    }
    const readBtn = ev.target.closest("[data-pack-lib-read]");
    if (readBtn) {
      const owner = readBtn.getAttribute("data-pack-lib-read");
      const itemId = readBtn.getAttribute("data-item");
      const items = BP.getLibraryItems?.() || [];
      let item = items.find((it) => it.id === itemId);
      if (!item && owner) {
        try {
          const path =
            owner !== BP.state.sessionUsername
              ? "/api/library/shares/" + encodeURIComponent(owner) + "/catalog"
              : "/api/library";
          const lib = await BP.api(path);
          item = (lib.items || []).find((it) => it.id === itemId);
        } catch {
          item = null;
        }
      }
      if (item && BP.openLibraryReader) {
        await BP.openLibraryReader(item);
      }
      return;
    }
    const openLib = ev.target.closest("[data-pack-lib-open]");
    if (openLib) {
      const owner = openLib.getAttribute("data-pack-lib-open");
      const sel = document.getElementById("lib-browse-select");
      if (sel && owner && owner !== BP.state.sessionUsername) {
        sel.value = owner;
        sel.dispatchEvent(new Event("change"));
      }
      BP.activateTab?.(BP.tabButton?.("library"));
      return;
    }
    const ask = ev.target.closest("[data-pack-ask]");
    if (ask) {
      const from = ask.getAttribute("data-pack-ask-from") || ask.getAttribute("data-from");
      const title = ask.getAttribute("data-pack-ask-title") || ask.getAttribute("data-title");
      if (from) {
        BP.setPackChatDmMode?.(from);
        const input = document.getElementById("pack-chat-input");
        if (input) input.value = "Could I get a copy of “" + title + "”?";
      }
    }
  });

  const origSync = null;
  BP.syncPackChatAttachUi = syncAttachChrome;
  syncAttachChrome();
})(window.BookPup);