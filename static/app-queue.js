(function (BP) {
  "use strict";
  const CSRF = BP.CSRF;
  const COVER_MAX_BYTES = BP.COVER_MAX_BYTES;
  const queueTabBadge = document.getElementById("queue-tab-badge");
  const queueWatch = new Map();
  let queueRefreshTimer = null;
  const NOTIFIED_DL_MAX = 200;

  function notifiedDlStorageKey() {
    const u = String(BP.state.sessionUsername || "").trim();
    return u ? "bookpupNotifiedDl:" + u : "bookpupNotifiedDl";
  }

  function loadNotifiedDoneJobs() {
    BP.state.notifiedDoneJobs = new Set();
    try {
      const raw = localStorage.getItem(notifiedDlStorageKey());
      if (!raw) return;
      const arr = JSON.parse(raw);
      if (Array.isArray(arr)) {
        arr.forEach((id) => {
          if (id) BP.state.notifiedDoneJobs.add(String(id));
        });
      }
    } catch {
      /* ignore */
    }
  }

  function persistNotifiedDoneJob(jobId) {
    if (!jobId) return;
    const id = String(jobId);
    BP.state.notifiedDoneJobs.add(id);
    try {
      const kept = [...BP.state.notifiedDoneJobs].slice(-NOTIFIED_DL_MAX);
      localStorage.setItem(notifiedDlStorageKey(), JSON.stringify(kept));
    } catch {
      /* ignore */
    }
  }

  function friendlyJobKind(job) {
    const t = job?.type || "";
    if (t === "search") return "Sniff";
    if (t === "download") return "Fetch";
    return "Job";
  }

  function queueToastTitle(job) {
    const kind = friendlyJobKind(job);
    const d = jobDetail(job);
    if (!d || d === "—") return kind;
    const short = d.length > 52 ? d.slice(0, 49) + "…" : d;
    return kind + " · " + short;
  }

  function friendlyIrcLine(msg) {
    const m = String(msg || "").trim();
    if (!m) return "";
    const searchBot = BP.humanizeSearchBotNotice(m);
    if (searchBot) return searchBot;
    if (/^connecting/i.test(m)) return "Connecting to IRC…";
    if (/IRC ready/i.test(m)) return "Connected to IRC.";
    if (/@search/i.test(m)) return "Searching the channel…";
    if (/parsing search/i.test(m)) return "Reading the result list…";
    if (/requesting book/i.test(m)) return "Asking the bot to send the file…";
    if (/Sniff \d+\/\d+/i.test(m)) return m.replace("Sniff", "Sniffing network");
    if (/queued/i.test(m)) return "Waiting in line…";
    if (/running/i.test(m)) return "Still working…";
    return m;
  }

  function friendlyJobError(job) {
    const raw = String(job?.error || job?.search_notice || "").trim();
    if (!raw) return "Something went wrong — try again or pick another row.";
    if (/quota/i.test(raw)) return raw;
    if (/not in #|likely offline/i.test(raw)) {
      return "That bot isn't in channel (likely offline). Try another row or network.";
    }
    if (/hasn't been seen recently/i.test(raw)) {
      return "That bot looks stale on IRC — try another row or network.";
    }
    if (/no dcc from/i.test(raw)) return "Bot didn't offer a file in time — try again or another network.";
    if (/timeout|timed out/i.test(raw)) return "Timed out — IRC or the bot may be slow. Try again.";
    if (/dcc/i.test(raw)) return "Download failed — try another network or row.";
    if (/no match|no results/i.test(raw)) return "No matches on that channel. Try different words or another network.";
    if (/cancel/i.test(raw)) return "Stopped.";
    if (raw.length > 160) return raw.slice(0, 157) + "…";
    return raw;
  }

  function friendlyQueueState(job) {
    const st = job?.state || "";
    if (st === "done") {
      return job.type === "download"
        ? "In Fresh catches — tag from Kennel when you are ready."
        : "Sniff finished — check the results table.";
    }
    if (st === "error") return friendlyJobError(job);
    if (st === "cancelled") return "Cancelled.";
    if (st === "running") return friendlyIrcLine(job.irc_status) || "Working…";
    if (st === "queued") return "Waiting to start…";
    return st || "—";
  }

  function updateIrcStatusPill(irc) {
    BP.state.ircSnap = irc || null;
    const pill = document.getElementById("irc-status-pill");
    if (!pill) return;
    let label = "IRC · …";
    if (irc) {
      if (irc.irc_connected) label = "IRC · Connected";
      else if (irc.irc_worker_alive) label = "IRC · Idle (reconnects on next job)";
      else label = "IRC · Offline";
    }
    pill.textContent = label;
    pill.classList.toggle("bp-irc-pill--ok", !!(irc && irc.irc_connected));
    pill.classList.toggle("bp-irc-pill--idle", !!(irc && !irc.irc_connected && irc.irc_worker_alive));
    BP.syncIrcPanelVisibility?.();
  }

  async function ensureDownloadStashed(job) {
    if (job?.library_item_id) return;
    const who = BP.state.sessionUsername;
    if (job?.owner && who && job.owner !== who) return;
    const stagingId = job?.staging_id || job?.id;
    if (!stagingId || !(job?.raw_bytes || job?.library_item_id)) return;
    try {
      await BP.api("/api/library/save/" + encodeURIComponent(stagingId), {
        method: "POST",
        body: JSON.stringify({ title: job.title || "" }),
      });
    } catch (err) {
      const msg = err?.message || "";
      if (!/already have this file/i.test(msg)) throw err;
    }
  }

  function announceDownloadDone(job) {
    if (job?.type !== "download" || job?.state !== "done" || !job?.id) return;
    if (BP.state.notifiedDoneJobs.has(job.id)) return;
    persistNotifiedDoneJob(job.id);
    BP.markUxFetchComplete?.();
    BP.markUxStashComplete?.();
    BP.maybePromptFetchNotify?.();
    const raw = job.title || jobDetail(job) || "Your file";
    const short = raw.length > 56 ? raw.slice(0, 53) + "…" : raw;
    void ensureDownloadStashed(job)
      .catch(() => {})
      .finally(() => {
        void BP.loadLibrary?.();
      });
    BP.showAppToast("Fresh catch", short + " is in your kennel — tag when you are ready.", "ok", [
      { label: "Fresh catches", onClick: () => BP.goToFreshCatches() },
    ]);
    if (typeof Notification === "undefined") return;
    if (localStorage.getItem("bookpupNotifyDl") !== "1") return;
    if (Notification.permission !== "granted") return;
    try {
      new Notification("BookPup — fetch ready", {
        body: short + " is in Fresh catches.",
        tag: "bookpup-dl-" + job.id,
      });
    } catch (_e) {
      /* ignore */
    }
  }

  let queueSegFilter = "all";

  function queueMatchesSeg(job) {
    const st = job?.state || "";
    if (queueSegFilter === "attention") return st === "error" || st === "cancelled";
    if (queueSegFilter === "active") return st === "queued" || st === "running";
    return true;
  }

  function bindQueueSegments() {
    const root = document.getElementById("queue-segments");
    if (!root || root.dataset.bound === "1") return;
    root.dataset.bound = "1";
    root.querySelectorAll("[data-queue-seg]").forEach((btn) => {
      btn.addEventListener("click", () => {
        queueSegFilter = btn.getAttribute("data-queue-seg") || "all";
        root.querySelectorAll(".bp-queue-seg").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        loadQueueTab();
      });
    });
  }
  bindQueueSegments();

  function trackQueueJobs(jobs) {
    (jobs || []).forEach((job) => {
      if (!job || !job.id) return;
      const snap = { state: job.state, irc: job.irc_status || "" };
      const prev = queueWatch.get(job.id);
      if (!prev) {
        queueWatch.set(job.id, snap);
        if ((snap.state === "running" || snap.state === "queued") && snap.irc) {
          BP.showQueueToast(job, friendlyIrcLine(snap.irc));
        } else if (snap.state === "done" && job.type === "download") {
          announceDownloadDone(job);
          BP.tryCompletePendingFetch?.(job, { backfill: true });
        }
        return;
      }
      if (prev.state !== snap.state) {
        const kind =
          snap.state === "error" || snap.state === "cancelled"
            ? "err"
            : snap.state === "done"
              ? "ok"
              : "info";
        if (snap.state === "done" && job.type === "download") {
          announceDownloadDone(job);
        } else {
          BP.showQueueToast(job, friendlyQueueState(job), kind);
        }
      } else if (snap.irc && snap.irc !== prev.irc) {
        BP.showQueueToast(job, friendlyIrcLine(snap.irc));
      }
      queueWatch.set(job.id, snap);
    });
  }

  function scheduleQueueRefresh(intervalMs) {
    if (queueRefreshTimer) {
      clearInterval(queueRefreshTimer);
      queueRefreshTimer = null;
    }
    queueRefreshTimer = setInterval(refreshQueue, intervalMs);
  }

  function updateQueueBadge(count) {
    if (!queueTabBadge) return;
    const n = Number(count) || 0;
    if (n < 1) {
      queueTabBadge.classList.add("hidden");
      queueTabBadge.textContent = "";
      queueTabBadge.removeAttribute("aria-label");
      return;
    }
    queueTabBadge.textContent = n > 99 ? "99+" : String(n);
    queueTabBadge.classList.remove("hidden");
    queueTabBadge.setAttribute("aria-label", n + " job(s) in queue");
  }

  async function refreshQueue() {
    try {
      const q = await BP.api("/api/queue");
      trackQueueJobs(q.jobs || []);
      updateQueueBadge(q.count);
      updateIrcStatusPill(q.irc);
      const pending = (q.jobs || []).some(
        (j) => j.state === "queued" || j.state === "running"
      );
      BP.state.queueHasActiveJob = pending || !!q.active;
      scheduleQueueRefresh(pending ? 2500 : 8000);
      if (!q.active && !q.count) {
        queueStatus.textContent = "";
        return;
      }
      let line = "Nothing fetching right now.";
      if (q.active) {
        const live = friendlyIrcLine(q.active.irc_status) || "Working…";
        const kind = friendlyJobKind(q.active);
        line = `${kind} in progress — ${live}`;
      }
      const extra = q.queued && q.queued.length ? ` (${q.queued.length} more waiting)` : "";
      if (q.failed_count) line += ` · ${q.failed_count} failed — open Fetch queue to dismiss`;
      queueStatus.textContent = line + extra;
      if (q.done_search) {
        BP.tryIngestDoneSearch?.(q.done_search);
      } else {
        void BP.syncActiveSearchResults?.();
      }
      if (q.done_download) {
        BP.tryCompletePendingFetch?.(q.done_download, { backfill: true });
      }
    } catch {
      queueStatus.textContent = "";
      updateQueueBadge(0);
      scheduleQueueRefresh(8000);
    }
  }

  async function pollJob(jobId, onDone, hooks) {
    clearInterval(BP.state.pollTimer);
    const intervalMs = hooks?.intervalMs || 1500;
    const searchMsgEl = () => document.getElementById("search-msg");

    async function tick() {
      await refreshQueue();
      try {
        let job = await BP.api("/api/jobs/" + encodeURIComponent(jobId));
        if (job.state === "done") {
          clearInterval(BP.state.pollTimer);
          if (job.type === "search") {
            try {
              job = await BP.api("/api/jobs/" + encodeURIComponent(jobId));
            } catch {
              /* use slim job */
            }
          }
          onDone(job);
        } else if (job.state === "cancelled") {
          clearInterval(BP.state.pollTimer);
          hooks?.onFail?.(job);
          const el = searchMsgEl();
          if (el) {
            el.textContent = "Search cancelled";
            el.className = "bp-msg muted";
          }
        } else if (job.state === "error") {
          clearInterval(BP.state.pollTimer);
          hooks?.onFail?.(job);
          const el = searchMsgEl();
          if (el) {
            el.textContent = job.error || "Job failed";
            el.className = "bp-msg err";
          }
        } else if (hooks?.onProgress) {
          hooks.onProgress(job);
        }
      } catch (err) {
        const msg = err.message || "";
        if (/unreadable|Expecting value|JSON/i.test(msg)) {
          return;
        }
        clearInterval(BP.state.pollTimer);
        hooks?.onFail?.();
        const el = searchMsgEl();
        if (el) {
          el.textContent = msg;
          el.className = "bp-msg err";
        }
      }
    }

    await tick();
    BP.state.pollTimer = setInterval(tick, intervalMs);
  }

  let queueTabActive = false;
  let queueTabTimer = null;

  function jobDetail(job) {
    if (job.type === "search") return job.query || "—";
    if (job.title) return job.title;
    if (job.command) return job.command;
    return "—";
  }

  function ago(ts) {
    if (!ts) return "—";
    const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
    if (s < 60) return s + "s";
    if (s < 3600) return Math.floor(s / 60) + "m";
    return Math.floor(s / 3600) + "h";
  }

  function jobReason(job) {
    if (job.error || job.search_notice) return friendlyJobError(job);
    return "";
  }

  function queueStateLabel(job) {
    const st = job?.state || "";
    if (st === "done") return "Done";
    if (st === "error") return "Problem";
    if (st === "cancelled") return "Cancelled";
    if (st === "running") return "In progress";
    if (st === "queued") return "Waiting";
    return st;
  }

  async function loadQueueTab() {
    const tbody = document.querySelector("#queue-table tbody");
    const msg = document.getElementById("queue-tab-msg");
    try {
      const data = await BP.api("/api/jobs");
      const rows = (data.jobs || []).filter(queueMatchesSeg);
      tbody.innerHTML = "";
      if (!data.jobs?.length) {
        msg.textContent = "No jobs — run a sniff from the Sniff tab.";
        msg.className = "bp-msg muted";
        return;
      }
      if (!rows.length) {
        msg.textContent = "No jobs in this view — try another filter.";
        msg.className = "bp-msg muted";
        return;
      }
      trackQueueJobs(data.jobs);
      const failed = (data.jobs || []).filter((j) => j.state === "error" || j.state === "cancelled").length;
      msg.textContent =
        rows.length + " shown · " + data.jobs.length + " total" + (failed ? ` · ${failed} need attention` : "") + ".";
      msg.className = failed ? "bp-msg err" : "bp-msg muted";
      rows.forEach((job) => {
        const tr = document.createElement("tr");
        const reason = jobReason(job);
        const stateClass = job.state === "error" ? " bp-queue-failed" : "";
        const active = job.state === "queued" || job.state === "running";
        const live = active ? friendlyIrcLine(job.irc_status) || "…" : "—";
        tr.innerHTML =
          "<td class=\"" +
          stateClass +
          "\">" +
          BP.escapeHtml(queueStateLabel(job)) +
          "</td><td>" +
          BP.escapeHtml(friendlyJobKind(job)) +
          "</td><td>" +
          BP.escapeHtml(jobDetail(job)) +
          "</td><td>" +
          BP.escapeHtml(ago(job.created_at)) +
          '</td><td class="bp-queue-live">' +
          BP.escapeHtml(live) +
          '</td><td class="' +
          (reason ? "bp-queue-failed" : "") +
          '">' +
          BP.escapeHtml(reason || "—") +
          "</td><td></td>";
        const actions = tr.cells[6];
        if (active) {
          const cancel = document.createElement("button");
          cancel.type = "button";
          cancel.className = "bp-btn cancel-job";
          cancel.textContent = "Cancel";
          cancel.addEventListener("click", async () => {
            try {
              await BP.api("/api/jobs/" + encodeURIComponent(job.id) + "/cancel", {
                method: "POST",
                body: "{}",
              });
              loadQueueTab();
              refreshQueue();
            } catch (err) {
              msg.textContent = err.message;
              msg.className = "bp-msg err";
            }
          });
          actions.appendChild(cancel);
        } else if (job.state === "error") {
          const retry = document.createElement("button");
          retry.type = "button";
          retry.className = "bp-btn";
          retry.textContent = "Retry";
          retry.addEventListener("click", async () => {
            try {
              await BP.api("/api/jobs/" + encodeURIComponent(job.id) + "/retry", {
                method: "POST",
                body: "{}",
              });
              loadQueueTab();
              refreshQueue();
            } catch (err) {
              msg.textContent = err.message;
              msg.className = "bp-msg err";
            }
          });
          actions.appendChild(retry);
        }
        if (job.state === "error" || job.state === "cancelled") {
          const dismiss = document.createElement("button");
          dismiss.type = "button";
          dismiss.className = "bp-btn dismiss-job";
          dismiss.textContent = "Dismiss";
          dismiss.addEventListener("click", async () => {
            try {
              await BP.api("/api/jobs/" + encodeURIComponent(job.id) + "/dismiss", {
                method: "POST",
                body: "{}",
              });
              loadQueueTab();
              refreshQueue();
            } catch (err) {
              msg.textContent = err.message;
              msg.className = "bp-msg err";
            }
          });
          actions.appendChild(dismiss);
        }
        tbody.appendChild(tr);
      });
    } catch (err) {
      msg.textContent = err.message;
      msg.className = "bp-msg err";
    }
  }

  function startQueueTabPoll() {
    if (queueTabTimer) return;
    loadQueueTab();
    queueTabTimer = setInterval(loadQueueTab, 2000);
  }

  function stopQueueTabPoll() {
    if (queueTabTimer) {
      clearInterval(queueTabTimer);
      queueTabTimer = null;
    }
  }
  // exports
  BP.ago = ago;
  BP.announceDownloadDone = announceDownloadDone;
  BP.friendlyIrcLine = friendlyIrcLine;
  BP.friendlyJobError = friendlyJobError;
  BP.friendlyJobKind = friendlyJobKind;
  BP.friendlyQueueState = friendlyQueueState;
  BP.jobDetail = jobDetail;
  BP.jobReason = jobReason;
  BP.loadQueueTab = loadQueueTab;
  BP.pollJob = pollJob;
  BP.queueStateLabel = queueStateLabel;
  BP.queueToastTitle = queueToastTitle;
  BP.refreshQueue = refreshQueue;
  BP.scheduleQueueRefresh = scheduleQueueRefresh;
  BP.startQueueTabPoll = startQueueTabPoll;
  BP.stopQueueTabPoll = stopQueueTabPoll;
  BP.updateIrcStatusPill = updateIrcStatusPill;
  BP.trackQueueJobs = trackQueueJobs;
  BP.updateQueueBadge = updateQueueBadge;
  BP.loadNotifiedDoneJobs = loadNotifiedDoneJobs;
  BP.persistNotifiedDoneJob = persistNotifiedDoneJob;
})(window.BookPup);
