(function (BP) {
  "use strict";
  const CSRF = BP.CSRF;
  const COVER_MAX_BYTES = BP.COVER_MAX_BYTES;
  function loadAccountTab() {
    const userEl = document.getElementById("account-current-user");
    const msg = document.getElementById("account-tab-msg");
    if (userEl) userEl.value = BP.state.sessionUsername || "";
    if (msg) {
      msg.textContent = "";
      msg.className = "bp-msg muted";
    }
    const opdsEl = document.getElementById("account-opds");
    if (opdsEl) {
      if (BP.state.sessionOpdsUrl) {
        opdsEl.classList.remove("hidden");
        opdsEl.textContent =
          "OPDS (catalogued bones only): " +
          BP.state.sessionOpdsUrl +
          " — use your BookPup username and password.";
      } else {
        opdsEl.classList.add("hidden");
        opdsEl.textContent = "";
      }
    }
    const notifyCb = document.getElementById("notify-dl-enable");
    if (notifyCb && notifyCb.dataset.bound !== "1") {
      notifyCb.dataset.bound = "1";
      notifyCb.checked = localStorage.getItem("bookpupNotifyDl") === "1";
      notifyCb.addEventListener("change", () => {
        localStorage.setItem("bookpupNotifyDl", notifyCb.checked ? "1" : "0");
        if (notifyCb.checked && typeof Notification !== "undefined" && Notification.permission === "default") {
          Notification.requestPermission();
        }
      });
    }
  }

  const accountForm = document.getElementById("account-form");
  if (accountForm) {
    accountForm.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const msg = document.getElementById("account-tab-msg");
      try {
        const data = await BP.api("/api/account", {
          method: "POST",
          body: JSON.stringify({
            current_password: document.getElementById("account-current-password").value,
            new_username: document.getElementById("account-new-username").value.trim() || null,
            new_password: document.getElementById("account-new-password").value || null,
          }),
        });
        BP.state.sessionUsername = data.username || BP.state.sessionUsername;
        BP.state.sessionAdmin = !!data.admin;
        const tab = document.getElementById("accounts-tab");
        const adminBlock = document.getElementById("accounts-admin-block");
        if (tab) tab.textContent = BP.state.sessionAdmin ? "Pack roster" : "Your tag";
        BP.syncTabMoreAccountsLabel?.();
        if (adminBlock) adminBlock.classList.toggle("hidden", !BP.state.sessionAdmin);
        document.getElementById("account-current-user").value = BP.state.sessionUsername;
        accountForm.reset();
        if (msg) {
          msg.textContent = "Your tag is updated.";
          msg.className = "bp-msg";
        }
      } catch (err) {
        if (msg) {
          msg.textContent = err.message;
          msg.className = "bp-msg err";
        }
      }
    });
  }

  function formatBugTs(ts) {
    const d = new Date((Number(ts) || 0) * 1000);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  }

  function renderAdminInboxList(rows, listEl) {
    listEl.textContent = "";
    rows.forEach((row) => {
      const li = document.createElement("li");
      li.className = "bp-bug-inbox-item";
      const head = document.createElement("p");
      head.className = "bp-bug-inbox-head";
      head.textContent = (row.from || "?") + " · " + formatBugTs(row.ts);
      const body = document.createElement("p");
      body.className = "bp-bug-inbox-body";
      body.textContent = String(row.text || "");
      const actions = document.createElement("p");
      actions.className = "bp-lib-actions";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "bp-btn";
      btn.textContent = "Dismiss";
      btn.dataset.inboxRowId = String(row.id);
      li.appendChild(head);
      li.appendChild(body);
      li.appendChild(actions);
      actions.appendChild(btn);
      listEl.appendChild(li);
    });
  }

  async function loadAdminBugInbox() {
    if (!BP.state.sessionAdmin) return;
    const msg = document.getElementById("admin-bug-inbox-msg");
    const list = document.getElementById("admin-bug-inbox-list");
    if (!msg || !list) return;
    try {
      const data = await BP.api("/api/admin/bug-inbox");
      const rows = data.reports || [];
      if (!rows.length) {
        msg.textContent = "No bug reports yet.";
        msg.className = "bp-msg muted";
        list.textContent = "";
        return;
      }
      msg.textContent = rows.length + " report(s) from the pack.";
      msg.className = "bp-msg muted";
      renderAdminInboxList(rows, list);
      list.querySelectorAll("button[data-inbox-row-id]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const id = btn.getAttribute("data-inbox-row-id");
          void (async () => {
            try {
              await BP.api("/api/admin/bug-inbox/" + encodeURIComponent(String(id)), {
                method: "DELETE",
              });
              await loadAdminBugInbox();
              BP.showAppToast?.("Bug inbox", "Report dismissed", "ok");
            } catch (err) {
              BP.showAppToast?.("Bug inbox", err.message || "Could not dismiss", "err");
            }
          })();
        });
      });
    } catch (err) {
      msg.textContent = err.message || "Could not load bug inbox";
      msg.className = "bp-msg err";
      list.textContent = "";
    }
  }

  async function loadAdminFeatureInbox() {
    if (!BP.state.sessionAdmin) return;
    const msg = document.getElementById("admin-feature-inbox-msg");
    const list = document.getElementById("admin-feature-inbox-list");
    if (!msg || !list) return;
    try {
      const data = await BP.api("/api/admin/feature-inbox");
      const rows = data.reports || [];
      if (!rows.length) {
        msg.textContent = "No feature requests yet.";
        msg.className = "bp-msg muted";
        list.textContent = "";
        return;
      }
      msg.textContent = rows.length + " request(s) from the pack.";
      msg.className = "bp-msg muted";
      renderAdminInboxList(rows, list);
      list.querySelectorAll("button[data-inbox-row-id]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const id = btn.getAttribute("data-inbox-row-id");
          void (async () => {
            try {
              await BP.api("/api/admin/feature-inbox/" + encodeURIComponent(String(id)), {
                method: "DELETE",
              });
              await loadAdminFeatureInbox();
              BP.showAppToast?.("Feature inbox", "Request dismissed", "ok");
            } catch (err) {
              BP.showAppToast?.("Feature inbox", err.message || "Could not dismiss", "err");
            }
          })();
        });
      });
    } catch (err) {
      msg.textContent = err.message || "Could not load feature inbox";
      msg.className = "bp-msg err";
      list.textContent = "";
    }
  }

  async function loadAdminDigest() {
    if (!BP.state.sessionAdmin) return;
    const summary = document.getElementById("admin-digest-summary");
    const list = document.getElementById("admin-digest-list");
    if (!summary || !list) return;
    try {
      const d = await BP.api("/api/admin/digest");
      const pups = d.pups || [];
      const jobs = d.jobs || {};
      const irc = d.irc || {};
      const ircLine = irc.irc_connected
        ? "IRC connected"
        : irc.irc_worker_alive
          ? "IRC idle (worker up)"
          : "IRC worker not running";
      summary.textContent =
        `${pups.length} pup(s) · ${jobs.active || 0} active job(s) · ${jobs.failed_or_cancelled || 0} need attention · ${ircLine}`;
      summary.className = "bp-msg muted";
      list.textContent = "";
      pups
        .slice()
        .sort((a, b) => (b.used_percent || 0) - (a.used_percent || 0))
        .forEach((p) => {
          const li = document.createElement("li");
          const pct = p.used_percent != null ? p.used_percent + "% kennel" : "";
          li.textContent = `${p.username}: ${BP.bytes(p.used_bytes || 0)} / ${BP.bytes(p.quota_bytes || 0)} (${pct})`;
          list.appendChild(li);
        });
      const recent = (jobs.recent_7d || []).slice(0, 8);
      if (recent.length) {
        const h = document.createElement("li");
        h.className = "bp-digest-recent-title";
        h.textContent = "Recent jobs (7 days)";
        list.appendChild(h);
        recent.forEach((j) => {
          const li = document.createElement("li");
          const label = j.title || j.type || "job";
          li.textContent = `${j.owner || "?"} · ${j.type} · ${j.state} · ${label}`;
          list.appendChild(li);
        });
      }
    } catch (err) {
      summary.textContent = err.message || "Could not load digest";
      summary.className = "bp-msg err";
      list.textContent = "";
    }
  }

  const adminBackupBtn = document.getElementById("admin-backup-btn");
  if (adminBackupBtn) {
    adminBackupBtn.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/admin/backup", {
          headers: { ...CSRF, ...(BP.state.authHeader ? { Authorization: BP.state.authHeader } : {}) },
        });
        if (!res.ok) throw new Error(res.statusText || "Backup failed");
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download =
          res.headers.get("Content-Disposition")?.match(/filename="([^"]+)"/)?.[1] ||
          "bookpup-backup.zip";
        a.click();
        URL.revokeObjectURL(url);
        BP.showAppToast("Backup", "Household backup downloaded", "ok");
      } catch (err) {
        BP.showAppToast("Backup", err.message || "Backup failed", "err");
      }
    });
  }

  async function loadAccountsTab() {
    if (!BP.state.sessionAdmin) return;
    const msg = document.getElementById("accounts-tab-msg");
    const tbody = document.querySelector("#accounts-table tbody");
    if (!tbody) return;
    try {
      const data = await BP.api("/api/admin/accounts");
      const rows = data.accounts || [];
      tbody.innerHTML = "";
      rows.forEach((acct) => {
        const tr = document.createElement("tr");
        const used = BP.bytes(acct.used_bytes || 0);
        const quota = BP.bytes(acct.quota_bytes || 0);
        const role = acct.admin ? "admin" : "user";
        const status = acct.enabled ? "enabled" : "disabled";
        tr.innerHTML =
          "<td>" +
          BP.escapeHtml(acct.username) +
          "</td><td>" +
          BP.escapeHtml(used) +
          "</td><td>" +
          BP.escapeHtml(quota) +
          '</td><td class="muted">' +
          BP.escapeHtml(role) +
          "</td><td>" +
          BP.escapeHtml(status) +
          "</td><td></td>";
        const actions = tr.cells[5];
        const login = document.createElement("button");
        login.type = "button";
        login.className = "bp-btn";
        login.textContent = "Set login";
        login.addEventListener("click", () => {
          const newUser = window.prompt(
            "New username for " + acct.username + " (leave blank to keep)",
            ""
          );
          if (newUser === null) return;
          const newPass = window.prompt(
            "New password (leave blank to keep; cannot view existing)",
            ""
          );
          if (newPass === null) return;
          const body = {};
          const nu = newUser.trim();
          const np = newPass;
          if (nu && nu !== acct.username) body.new_username = nu;
          if (np) body.password = np;
          if (!body.new_username && !body.password) return;
          BP.api("/api/admin/accounts/" + encodeURIComponent(acct.username), {
            method: "POST",
            body: JSON.stringify(body),
          })
            .then(() => loadAccountsTab())
            .catch((err) => {
              if (msg) {
                msg.textContent = err.message;
                msg.className = "bp-msg err";
              }
            });
        });
        actions.appendChild(login);
        const wipe = document.createElement("button");
        wipe.type = "button";
        wipe.className = "bp-btn bp-btn--danger";
        wipe.textContent = "Wipe";
        wipe.addEventListener("click", () => BP.openWipeAccountModal?.(acct.username));
        actions.appendChild(wipe);
        if (acct.username !== BP.state.sessionUsername) {
          const edit = document.createElement("button");
          edit.type = "button";
          edit.className = "bp-btn";
          edit.textContent = "Quota";
          edit.addEventListener("click", () => {
            const gb = window.prompt(
              "Library quota (GB) for " + acct.username,
              String((acct.quota_bytes || 0) / (1024 * 1024 * 1024))
            );
            if (gb === null) return;
            const qb = Math.round(parseFloat(gb) * 1024 * 1024 * 1024);
            if (!Number.isFinite(qb) || qb < 0) return;
            BP.api("/api/admin/accounts/" + encodeURIComponent(acct.username), {
              method: "POST",
              body: JSON.stringify({ quota_bytes: qb }),
            })
              .then(() => loadAccountsTab())
              .catch((err) => {
                if (msg) {
                  msg.textContent = err.message;
                  msg.className = "bp-msg err";
                }
              });
          });
          actions.appendChild(edit);
          const del = document.createElement("button");
          del.type = "button";
          del.className = "bp-btn";
          del.textContent = "Remove";
          del.addEventListener("click", () => {
            if (!window.confirm("Remove account " + acct.username + "?")) return;
            BP.api("/api/admin/accounts/" + encodeURIComponent(acct.username), {
              method: "DELETE",
            })
              .then(() => loadAccountsTab())
              .catch((err) => {
                if (msg) {
                  msg.textContent = err.message;
                  msg.className = "bp-msg err";
                }
              });
          });
          actions.appendChild(del);
        }
        tbody.appendChild(tr);
      });
      if (msg) {
        msg.textContent = rows.length ? rows.length + " pup(s) in the pack." : "No pups yet.";
        msg.className = "bp-msg muted";
      }
    } catch (err) {
      if (msg) {
        msg.textContent = err.message;
        msg.className = "bp-msg err";
      }
    }
  }

  function wipeDisclaimerHtml(warnings, targetUser, isSelf) {
    const w = warnings || {};
    const who = BP.escapeHtml(targetUser || "this account");
    const head = isSelf
      ? "<p><strong>This cannot be undone.</strong> You will lose:</p>"
      : `<p><strong>This cannot be undone.</strong> You are wiping <strong>${who}</strong>. They will lose:</p>`;
    const lines = [
      head,
      "<ul>",
      "<li>All books in the kennel (fresh catches and catalogued library)</li>",
      "<li>Cover art, KOReader sync data, and reading positions</li>",
      "<li>IRC search drafts, saved searches, and queue history for that account</li>",
    ];
    if (isSelf) {
      lines.push("<li>Browser-side BookPup preferences on this device</li>");
    }
    lines.push(
      "</ul>",
      isSelf
        ? "<p>Your login (username and password), admin role, and storage quota are <strong>not</strong> changed.</p>"
        : "<p>That pup&rsquo;s login, role, and quota are <strong>not</strong> changed. This browser&rsquo;s preferences are untouched.</p>"
    );
    const extra = [];
    if (w.active_jobs > 0) {
      extra.push(
        `${w.active_jobs} active queue job${w.active_jobs === 1 ? "" : "s"} will be cancelled`
      );
    }
    if (w.staged_library > 0) {
      extra.push(
        `${w.staged_library} fresh catch${w.staged_library === 1 ? "" : "es"} will be deleted`
      );
    }
    if (w.import_sessions > 0) {
      extra.push(
        `${w.import_sessions} in-progress import${w.import_sessions === 1 ? "" : "s"} will be discarded`
      );
    }
    if (extra.length) {
      lines.push(`<p class="bp-msg err">Right now: ${extra.join("; ")}.</p>`);
    }
    return lines.join("");
  }

  let wipePhrase = "";
  let wipeTarget = null;

  function bindWipeAccount() {
    const openBtn = document.getElementById("account-wipe-open");
    const modal = document.getElementById("wipe-modal");
    const form = document.getElementById("wipe-form");
    const disclaimer = document.getElementById("wipe-disclaimer");
    const phraseDisplay = document.getElementById("wipe-phrase-display");
    const phraseInput = document.getElementById("wipe-phrase-input");
    const passInput = document.getElementById("wipe-password");
    const passLabel = document.getElementById("wipe-password-label");
    const titleEl = document.getElementById("wipe-modal-title");
    const msg = document.getElementById("wipe-modal-msg");
    const submitBtn = document.getElementById("wipe-submit-btn");

    function closeWipeModal() {
      if (!modal) return;
      modal.classList.add("hidden");
      document.body.classList.remove("bp-reader-open");
      wipePhrase = "";
      wipeTarget = null;
    }

    async function openWipeAccountModal(targetUser) {
      if (!modal) return;
      wipeTarget = (targetUser || BP.state.sessionUsername || "").trim();
      const isSelf = wipeTarget === BP.state.sessionUsername;
      if (msg) {
        msg.textContent = "";
        msg.className = "bp-msg muted";
      }
      if (phraseInput) phraseInput.value = "";
      if (passInput) passInput.value = "";
      if (submitBtn) submitBtn.disabled = false;
      if (titleEl) {
        titleEl.textContent = isSelf
          ? "Wipe account"
          : "Wipe " + wipeTarget + "\u2019s kennel";
      }
      if (passLabel) {
        passLabel.textContent = isSelf ? "Current password" : "Your admin password";
      }
      if (submitBtn) {
        submitBtn.textContent = isSelf ? "Wipe my account" : "Wipe this pup";
      }
      try {
        const previewUrl = isSelf
          ? "/api/account/wipe-preview"
          : "/api/admin/accounts/" + encodeURIComponent(wipeTarget) + "/wipe-preview";
        const data = await BP.api(previewUrl);
        wipePhrase = data.phrase || "";
        wipeTarget = data.target || wipeTarget;
        if (disclaimer) {
          disclaimer.innerHTML = wipeDisclaimerHtml(data.warnings, wipeTarget, isSelf);
        }
        if (phraseDisplay) phraseDisplay.textContent = wipePhrase;
        modal.classList.remove("hidden");
        document.body.classList.add("bp-reader-open");
        phraseInput?.focus();
      } catch (err) {
        const tabMsg = document.getElementById(
          isSelf ? "account-tab-msg" : "accounts-tab-msg"
        );
        if (tabMsg) {
          tabMsg.textContent = err.message || "Could not prepare wipe";
          tabMsg.className = "bp-msg err";
        }
      }
    }

    BP.openWipeAccountModal = openWipeAccountModal;

    openBtn?.addEventListener("click", () => openWipeAccountModal(BP.state.sessionUsername));
    document.getElementById("wipe-modal-close")?.addEventListener("click", closeWipeModal);
    document.getElementById("wipe-cancel-btn")?.addEventListener("click", closeWipeModal);
    modal?.addEventListener("click", (ev) => {
      if (ev.target === modal) closeWipeModal();
    });
    document.addEventListener("keydown", (ev) => {
      if (ev.key !== "Escape") return;
      if (!modal || modal.classList.contains("hidden")) return;
      closeWipeModal();
    });
    form?.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const normalized = (phraseInput?.value || "")
        .trim()
        .split(/\s+/)
        .filter(Boolean)
        .join(" ");
      if (normalized !== wipePhrase) {
        if (msg) {
          msg.textContent = "Phrase does not match. Copy it exactly from the box above.";
          msg.className = "bp-msg err";
        }
        return;
      }
      if (submitBtn) submitBtn.disabled = true;
      const target = wipeTarget || BP.state.sessionUsername;
      const isSelf = target === BP.state.sessionUsername;
      const postUrl = isSelf
        ? "/api/account/wipe"
        : "/api/admin/accounts/" + encodeURIComponent(target) + "/wipe";
      try {
        await BP.api(postUrl, {
          method: "POST",
          body: JSON.stringify({
            phrase: normalized,
            current_password: passInput?.value || "",
          }),
        });
        closeWipeModal();
        if (isSelf) {
          BP.clearBookpupClientPrefs?.();
          BP.resetIrcFeedLocal?.();
          window.location.reload();
          return;
        }
        BP.showAppToast?.("Wipe", `Kennel cleared for ${target}`, "ok");
        loadAccountsTab();
        BP.loadAdminDigest?.();
        BP.loadAdminBugInbox?.();
        BP.loadAdminFeatureInbox?.();
        if (target === BP.state.sessionUsername) {
          BP.loadLibrary?.();
        }
      } catch (err) {
        if (submitBtn) submitBtn.disabled = false;
        if (msg) {
          msg.textContent = err.message || "Wipe failed";
          msg.className = "bp-msg err";
        }
      }
    });
  }

  bindWipeAccount();

  const accountsCreateForm = document.getElementById("accounts-create-form");
  if (accountsCreateForm) {
    accountsCreateForm.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const msg = document.getElementById("accounts-tab-msg");
      try {
        const gb = parseFloat(document.getElementById("acct-quota-gb").value || "2");
        const qb = Math.round(gb * 1024 * 1024 * 1024);
        await BP.api("/api/admin/accounts", {
          method: "POST",
          body: JSON.stringify({
            username: document.getElementById("acct-user").value.trim(),
            password: document.getElementById("acct-pass").value,
            quota_bytes: qb,
            admin: document.getElementById("acct-admin").checked,
          }),
        });
        accountsCreateForm.reset();
        document.getElementById("acct-quota-gb").value = "2";
        loadAccountsTab();
        if (msg) {
          msg.textContent = "New pup added to the pack.";
          msg.className = "bp-msg muted";
        }
      } catch (err) {
        if (msg) {
          msg.textContent = err.message;
          msg.className = "bp-msg err";
        }
      }
    });
  }

  // exports
  BP.loadAccountTab = loadAccountTab;
  BP.loadAccountsTab = loadAccountsTab;
  BP.loadAdminDigest = loadAdminDigest;
  BP.loadAdminBugInbox = loadAdminBugInbox;
  BP.loadAdminFeatureInbox = loadAdminFeatureInbox;
})(window.BookPup);
