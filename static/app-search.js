(function (BP) {
  "use strict";
  const CSRF = BP.CSRF;
  const COVER_MAX_BYTES = BP.COVER_MAX_BYTES;
  const SEARCH_CHANNEL_KEY = BP.SEARCH_CHANNEL_KEY || "bookpupSearchChannel";
  const searchForm = document.getElementById("search-form");
  const searchMsg = document.getElementById("search-msg");
  const queueStatus = document.getElementById("queue-status");
  const resultsWrap = document.getElementById("results-wrap");
  const resultsBody = document.querySelector("#results-table tbody");
  const filterInput = document.getElementById("filter");
  const draftQueryEl = document.getElementById("draft-query");
  const draftChannelEl = document.getElementById("draft-channel");
  const draftRowsEl = document.getElementById("draft-rows");
  const savedSearchEmpty = document.getElementById("saved-search-empty");
  const savedSearchList = document.getElementById("saved-search-list");
  const savedSearchName = document.getElementById("saved-search-name");
  const savedSearchSaveBtn = document.getElementById("saved-search-save");
  const savedSearchMsg = document.getElementById("saved-search-msg");
  const formSchedEnabled = document.getElementById("sniff-form-schedule-enabled");
  const formSchedInterval = document.getElementById("sniff-form-schedule-interval");
  const formSchedStatus = document.getElementById("sniff-form-schedule-status");
  const formSchedHelp = document.getElementById("sniff-schedule-help");
  const formSchedHelpWrap = document.getElementById("sniff-schedule-help-wrap");
  const formSchedPanel = document.getElementById("sniff-form-schedule");
  const formSchedHint = document.getElementById("sniff-form-schedule-hint");
  let resultRows = [];
  const SNIFF_BATCH_MAX = 5;
  const SNIFF_PAGE_SIZE_KEY = "bookpupSniffPageSize";
  let sniffSelected = new Set();
  let sniffPage = 1;
  let sniffPageSize = parseInt(localStorage.getItem(SNIFF_PAGE_SIZE_KEY), 10) || 50;
  let workspaceSaved = [];
  let draftSyncTimer = null;
  let suppressDraftSync = false;

  function clearSniffQueryInput() {
    const queryEl = document.getElementById("query");
    if (queryEl) queryEl.value = "";
  }

  function channelDisplayLabel(channelId) {
    const id = (channelId || "").trim();
    if (!id) return "—";
    const sel = document.getElementById("channel");
    if (sel) {
      const opt = sel.querySelector('option[value="' + CSS.escape(id) + '"]');
      if (opt) return opt.textContent || id;
    }
    if (id === "all") return "Every ebook net";
    if (id === "xdcc:index") return "XDCC index";
    if (id === "soulseek:slskd") return "Soulseek";
    if (id === "irchighway:ebooks") return "IRCHighway #ebooks";
    return id;
  }

  const savedSearchPanel = document.getElementById("saved-search-panel");

  function syncSniffResultsLayout() {
    if (!resultsWrap) return;
    const hasRows = resultRows.length > 0;
    resultsWrap.classList.toggle("bp-results-rows-empty", !hasRows);
    if (savedSearchPanel && !hasRows) savedSearchPanel.open = true;
  }

  function updateResultsPanelVisibility() {
    if (!resultsWrap) return;
    const rows = typeof resultRows !== "undefined" ? resultRows.length : 0;
    const saved = workspaceSaved.length;
    const draftRows = draftRowsEl ? parseInt(draftRowsEl.textContent || "0", 10) : 0;
    const draftQ = (draftQueryEl?.textContent || "").trim();
    const hasDraft = draftRows > 0 || (draftQ && draftQ !== "No sniff yet");
    if (rows > 0 || saved > 0 || hasDraft) {
      resultsWrap.classList.remove("hidden");
    }
    syncSniffResultsLayout();
  }

  function updateDraftMeta(query, channel, count) {
    const q = (query || "").trim();
    if (draftQueryEl) {
      draftQueryEl.textContent = q || "No sniff yet";
    }
    if (draftChannelEl) {
      draftChannelEl.textContent = channel ? channelDisplayLabel(channel) : "—";
    }
    const n = typeof count === "number" ? count : resultRows.length;
    if (draftRowsEl) {
      draftRowsEl.textContent = String(n);
    }
    updateFormSchedule();
  }

  function applyDraft(draft) {
    if (!draft || !Array.isArray(draft.results)) return;
    suppressDraftSync = true;
    resultRows = draft.results;
    if (filterInput) filterInput.value = draft.filter || "";
    const channelEl = document.getElementById("channel");
    if (channelEl && draft.channel && channelEl.querySelector('option[value="' + draft.channel + '"]')) {
      channelEl.value = draft.channel;
      localStorage.setItem(SEARCH_CHANNEL_KEY, draft.channel);
      BP.syncIrcChatChannel();
    }
    BP.state.activeSearchJob = draft.job_id || null;
    if (resultRows.length) {
      resultsWrap.classList.remove("hidden");
      searchMsg.textContent = `${resultRows.length} matches (open results)`;
      searchMsg.className = "bp-msg muted";
    }
    updateDraftMeta(draft.query, draft.channel, resultRows.length);
    renderResults(resultRows);
    updateResultsPanelVisibility();
    suppressDraftSync = false;
  }

  async function pushDraftPatch(patch) {
    try {
      const data = await BP.api("/api/search/workspace/draft", {
        method: "POST",
        body: JSON.stringify(patch),
      });
      if (data.draft) {
        if (data.draft.job_id) BP.state.activeSearchJob = data.draft.job_id;
        updateDraftMeta(data.draft.query, data.draft.channel, data.draft.result_count);
      }
    } catch (err) {
      if (savedSearchMsg) {
        savedSearchMsg.textContent = err.message || "Could not sync draft";
        savedSearchMsg.className = "bp-msg err";
      }
    }
  }

  function scheduleDraftSync(patch) {
    if (suppressDraftSync) return;
    clearTimeout(draftSyncTimer);
    draftSyncTimer = setTimeout(() => pushDraftPatch(patch), 450);
  }

  function syncDraftFromUi(fullResults) {
    const queryEl = document.getElementById("query");
    const channelEl = document.getElementById("channel");
    scheduleDraftSync({
      query: queryEl?.value?.trim() || "",
      channel: channelEl?.value || "",
      filter: filterInput?.value || "",
      ...(fullResults
        ? { results: resultRows, job_id: BP.state.activeSearchJob || undefined }
        : {}),
    });
  }

  const SCHEDULE_INTERVALS = [
    { hours: 6, label: "Every 6 hours" },
    { hours: 12, label: "Every 12 hours" },
    { hours: 24, label: "Daily" },
    { hours: 168, label: "Weekly" },
  ];

  function formatScheduleWhen(ts) {
    if (!ts || ts <= 0) return "";
    const d = new Date(ts * 1000);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  }

  async function patchSavedSchedule(id, body) {
    try {
      const data = await BP.api("/api/search/saved/" + encodeURIComponent(id) + "/schedule", {
        method: "POST",
        body: JSON.stringify(body),
      });
      renderSavedSearchList(data.workspace?.saved);
      if (savedSearchMsg) {
        savedSearchMsg.textContent = body.enabled ? "Scheduled sniff enabled." : "Scheduled sniff off.";
        savedSearchMsg.className = "bp-msg muted";
      }
      if (formSchedStatus && !formSchedStatus.classList.contains("err")) {
        formSchedStatus.className = "bp-msg muted bp-form-schedule-status";
      }
    } catch (err) {
      if (savedSearchMsg) {
        savedSearchMsg.textContent = err.message;
        savedSearchMsg.className = "bp-msg err";
      }
      if (formSchedStatus) {
        formSchedStatus.textContent = err.message;
        formSchedStatus.className = "bp-msg err bp-form-schedule-status";
      }
      void loadSearchWorkspace();
    }
  }

  function findMatchingBookmark() {
    const q = document.getElementById("query")?.value?.trim() || "";
    const ch = document.getElementById("channel")?.value || "";
    if (!q) return null;
    const matches = workspaceSaved.filter((s) => s.query === q && s.channel === ch);
    if (!matches.length) return null;
    return matches.reduce((a, b) => ((b.saved_at || 0) > (a.saved_at || 0) ? b : a));
  }

  function scheduleIntervalShort(hours) {
    const h = hours || 24;
    const opt = SCHEDULE_INTERVALS.find((o) => o.hours === h);
    if (!opt) return `${h}h`;
    return opt.label.replace(/^Every /, "");
  }

  function scheduleStatusParts(sched) {
    const parts = [];
    if (sched?.enabled) {
      if (sched.running) parts.push("Running…");
      else if (sched.next_run_at) parts.push("Next ~" + formatScheduleWhen(sched.next_run_at));
      if (sched.last_run_at) parts.push("Last " + formatScheduleWhen(sched.last_run_at));
    }
    if (sched?.last_error) parts.push(sched.last_error);
    return parts;
  }

  let suppressFormSchedEvents = false;

  function updateFormSchedule() {
    if (!formSchedEnabled) return;
    const match = findMatchingBookmark();
    const sched = match?.schedule || {};
    const hasRows = resultRows.length > 0;
    suppressFormSchedEvents = true;
    formSchedEnabled.checked = !!(sched.enabled && match);
    formSchedEnabled.disabled = !hasRows;
    formSchedInterval.disabled = !hasRows || !formSchedEnabled.checked;
    const wantH = sched.interval_hours || 24;
    formSchedInterval.value = String(
      SCHEDULE_INTERVALS.some((o) => o.hours === wantH) ? wantH : 24
    );
    suppressFormSchedEvents = false;
    if (formSchedStatus?.classList.contains("err")) return;
    if (formSchedStatus) formSchedStatus.className = "bp-msg muted bp-form-schedule-status";
    if (formSchedHint) {
      if (sched.enabled && match) {
        formSchedHint.textContent = `On · ${scheduleIntervalShort(sched.interval_hours)}`;
        formSchedHint.classList.remove("hidden");
        formSchedHint.setAttribute("aria-hidden", "false");
      } else {
        formSchedHint.textContent = "";
        formSchedHint.classList.add("hidden");
        formSchedHint.setAttribute("aria-hidden", "true");
      }
    }
    if (!hasRows) {
      if (formSchedStatus) {
        formSchedStatus.textContent = "Sniff first — schedule needs open results to bookmark.";
      }
      return;
    }
    const parts = scheduleStatusParts(sched);
    if (!match) {
      if (formSchedStatus) {
        formSchedStatus.textContent =
          "No bookmark for this query yet — enabling creates one automatically.";
      }
      return;
    }
    if (formSchedStatus) {
      const nameBit = match.name ? `Bookmark “${match.name}”.` : "";
      formSchedStatus.textContent = [nameBit, parts.join(" · ")].filter(Boolean).join(" ");
    }
  }

  async function ensureBookmarkForFormSchedule() {
    const match = findMatchingBookmark();
    if (match) return match.id;
    const q = document.getElementById("query")?.value?.trim() || "";
    if (!resultRows.length) throw new Error("Open results have no rows to bookmark.");
    await pushDraftPatch({
      query: q,
      channel: document.getElementById("channel")?.value || "",
      filter: filterInput?.value || "",
      results: resultRows,
      job_id: BP.state.activeSearchJob || undefined,
    });
    const autoName = (q.slice(0, 60) || "Scheduled sniff").trim();
    const data = await BP.api("/api/search/saved", {
      method: "POST",
      body: JSON.stringify({ name: autoName }),
    });
    renderSavedSearchList(data.workspace?.saved);
    return data.id;
  }

  async function patchFormSchedule(body) {
    try {
      let id = findMatchingBookmark()?.id;
      if (!id && body.enabled) {
        id = await ensureBookmarkForFormSchedule();
      }
      if (!id) return;
      await patchSavedSchedule(id, body);
      if (body.enabled && formSchedPanel) formSchedPanel.open = true;
      updateFormSchedule();
    } catch (err) {
      if (formSchedStatus) {
        formSchedStatus.textContent = err.message;
        formSchedStatus.className = "bp-msg err bp-form-schedule-status";
      }
      suppressFormSchedEvents = true;
      if (formSchedEnabled) formSchedEnabled.checked = false;
      if (formSchedInterval) formSchedInterval.disabled = true;
      suppressFormSchedEvents = false;
    }
  }

  function renderSavedSearchList(saved) {
    workspaceSaved = Array.isArray(saved) ? saved.slice() : [];
    if (!savedSearchList) return;
    savedSearchList.textContent = "";
    if (savedSearchEmpty) {
      savedSearchEmpty.classList.toggle("hidden", workspaceSaved.length > 0);
    }
    workspaceSaved.forEach((item, idx) => {
      const li = document.createElement("li");
      li.className = "bp-saved-item";
      const title = document.createElement("span");
      title.className = "bp-saved-item-title";
      const q = (item.query || "—").slice(0, 48);
      const rows = item.result_count || 0;
      title.textContent = item.name + " — " + rows + " rows — sniff: " + q;
      const actions = document.createElement("span");
      actions.className = "bp-saved-item-actions";
      const loadBtn = document.createElement("button");
      loadBtn.type = "button";
      loadBtn.className = "bp-btn";
      loadBtn.textContent = "Load";
      loadBtn.addEventListener("click", () => loadSavedSearch(item.id));
      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "bp-btn";
      delBtn.textContent = "Remove";
      delBtn.addEventListener("click", () => removeSavedSearch(item.id));
      const upBtn = document.createElement("button");
      upBtn.type = "button";
      upBtn.className = "bp-btn";
      upBtn.textContent = "↑";
      upBtn.disabled = idx === 0;
      upBtn.addEventListener("click", () => moveSavedSearch(item.id, -1));
      const downBtn = document.createElement("button");
      downBtn.type = "button";
      downBtn.className = "bp-btn";
      downBtn.textContent = "↓";
      downBtn.disabled = idx === workspaceSaved.length - 1;
      downBtn.addEventListener("click", () => moveSavedSearch(item.id, 1));
      actions.append(loadBtn, delBtn, upBtn, downBtn);

      const sched = item.schedule || {};
      const schedRow = document.createElement("div");
      schedRow.className = "bp-saved-schedule";
      const schedLabel = document.createElement("label");
      schedLabel.className = "bp-check bp-saved-schedule-check";
      const schedToggle = document.createElement("input");
      schedToggle.type = "checkbox";
      schedToggle.checked = !!sched.enabled;
      schedToggle.setAttribute("aria-label", "Scheduled sniff for " + (item.name || "bookmark"));
      const intervalSel = document.createElement("select");
      intervalSel.className = "bp-saved-schedule-interval";
      intervalSel.disabled = !sched.enabled;
      SCHEDULE_INTERVALS.forEach((opt) => {
        const o = document.createElement("option");
        o.value = String(opt.hours);
        o.textContent = opt.label;
        intervalSel.appendChild(o);
      });
      const wantH = sched.interval_hours || 24;
      intervalSel.value = String(
        SCHEDULE_INTERVALS.some((o) => o.hours === wantH) ? wantH : 24
      );
      schedToggle.addEventListener("change", () => {
        intervalSel.disabled = !schedToggle.checked;
        void patchSavedSchedule(item.id, {
          enabled: schedToggle.checked,
          interval_hours: parseInt(intervalSel.value, 10) || 24,
        });
      });
      intervalSel.addEventListener("change", () => {
        if (!schedToggle.checked) return;
        void patchSavedSchedule(item.id, {
          enabled: true,
          interval_hours: parseInt(intervalSel.value, 10) || 24,
        });
      });
      schedLabel.append(schedToggle, document.createTextNode(" Scheduled sniff"));
      const status = document.createElement("p");
      status.className = "bp-msg muted bp-saved-schedule-status";
      const parts = [];
      if (sched.enabled) {
        if (sched.running) parts.push("Running…");
        else if (sched.next_run_at) parts.push("Next ~" + formatScheduleWhen(sched.next_run_at));
        if (sched.last_run_at) parts.push("Last " + formatScheduleWhen(sched.last_run_at));
      }
      if (sched.last_error) parts.push(sched.last_error);
      status.textContent = parts.join(" · ");
      schedRow.append(schedLabel, intervalSel, status);

      li.append(title, actions, schedRow);
      savedSearchList.appendChild(li);
    });
    updateResultsPanelVisibility();
    updateFormSchedule();
  }

  let workspaceLoadToken = 0;

  async function loadSearchWorkspace() {
    const token = ++workspaceLoadToken;
    try {
      const ws = await BP.api("/api/search/workspace");
      if (token !== workspaceLoadToken) return;
      renderSavedSearchList(ws.saved);
      if (
        ws.draft &&
        ws.draft.results &&
        ws.draft.results.length &&
        !resultRows.length &&
        !BP.state.searchPollTimer && !BP.state.fetchPollTimer
      ) {
        applyDraft(ws.draft);
      } else if (ws.draft) {
        updateDraftMeta(ws.draft.query, ws.draft.channel, 0);
      }
      if (ws.draft?.job_id && !BP.state.searchPollTimer && !BP.state.fetchPollTimer) {
        BP.state.activeSearchJob = ws.draft.job_id;
      }
      if (!resultRows.length && BP.state.activeSearchJob && !BP.state.searchPollTimer) {
        void syncActiveSearchResults();
      }
      if (!BP.state.fetchPollTimer) {
        void syncActiveDownload();
      }
      if (savedSearchMsg && !savedSearchMsg.classList.contains("err")) {
        savedSearchMsg.textContent = "";
      }
      updateResultsPanelVisibility();
    } catch {
      /* ignore */
    }
  }

  async function loadSavedSearch(id) {
    if (!id) return;
    if (savedSearchMsg) {
      savedSearchMsg.textContent = "Loading saved search…";
      savedSearchMsg.className = "bp-msg muted";
    }
    try {
      const data = await BP.api("/api/search/saved/" + encodeURIComponent(id) + "/load", {
        method: "POST",
        body: "{}",
      });
      applyDraft(data.draft);
      if (savedSearchMsg) {
        savedSearchMsg.textContent = "Loaded into open results.";
        savedSearchMsg.className = "bp-msg muted";
      }
    } catch (err) {
      if (savedSearchMsg) {
        savedSearchMsg.textContent = err.message;
        savedSearchMsg.className = "bp-msg err";
      }
    }
  }

  async function removeSavedSearch(id) {
    try {
      const data = await BP.api("/api/search/saved/" + encodeURIComponent(id), { method: "DELETE" });
      renderSavedSearchList(data.workspace?.saved);
      if (savedSearchMsg) {
        savedSearchMsg.textContent = "Removed.";
        savedSearchMsg.className = "bp-msg muted";
      }
    } catch (err) {
      if (savedSearchMsg) {
        savedSearchMsg.textContent = err.message;
        savedSearchMsg.className = "bp-msg err";
      }
    }
  }

  async function moveSavedSearch(id, delta) {
    const ids = workspaceSaved.map((x) => x.id);
    const i = ids.indexOf(id);
    if (i < 0) return;
    const j = i + delta;
    if (j < 0 || j >= ids.length) return;
    ids.splice(i, 1);
    ids.splice(j, 0, id);
    try {
      const data = await BP.api("/api/search/saved/reorder", {
        method: "POST",
        body: JSON.stringify({ order: ids }),
      });
      renderSavedSearchList(data.workspace?.saved);
    } catch (err) {
      if (savedSearchMsg) {
        savedSearchMsg.textContent = err.message;
        savedSearchMsg.className = "bp-msg err";
      }
    }
  }

  savedSearchSaveBtn?.addEventListener("click", async () => {
    const name = (savedSearchName?.value || "").trim();
    if (!name) {
      if (savedSearchMsg) {
        savedSearchMsg.textContent = "Enter a bookmark name first.";
        savedSearchMsg.className = "bp-msg err";
      }
      return;
    }
    if (!resultRows.length) {
      if (savedSearchMsg) {
        savedSearchMsg.textContent = "Open results have no rows to bookmark.";
        savedSearchMsg.className = "bp-msg err";
      }
      return;
    }
    try {
      await pushDraftPatch({
        query: document.getElementById("query")?.value?.trim() || "",
        channel: document.getElementById("channel")?.value || "",
        filter: filterInput?.value || "",
        results: resultRows,
        job_id: BP.state.activeSearchJob || undefined,
      });
      const data = await BP.api("/api/search/saved", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      if (savedSearchName) savedSearchName.value = "";
      renderSavedSearchList(data.workspace?.saved);
      if (savedSearchMsg) {
        savedSearchMsg.textContent = `Bookmarked “${data.name}”.`;
        savedSearchMsg.className = "bp-msg muted";
      }
    } catch (err) {
      if (savedSearchMsg) {
        savedSearchMsg.textContent = err.message;
        savedSearchMsg.className = "bp-msg err";
      }
    }
  });

  const SNIFF_EPUB_KEY = "bookpupSniffEpubOnly";
  const SNIFF_FOREIGN_KEY = "bookpupSniffHideForeign";
  const SNIFF_PICK_KEY = "bookpupSniffHighlightPick";

  const SNIFF_TITLE_STOP = new Set([
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "in",
    "to",
    "for",
    "on",
    "at",
    "by",
    "with",
    "from",
    "vol",
    "volume",
    "book",
    "books",
    "edition",
    "ed",
    "part",
    "pt",
    "no",
    "nr",
    "pdf",
    "epub",
    "mobi",
    "azw3",
    "cbz",
    "txt",
    "retail",
    "repack",
    "fixed",
    "ret",
  ]);

  function normSniffTitle(text) {
    let s = String(text || "").toLowerCase();
    s = s.replace(/\s+(?:epub|pdf|mobi|azw3?|cbz|cbr|cb7|txt|prc|fb2|djvu|chm|rtf|lit|md|html?)(?:\s|$)/gi, " ");
    return s
      .replace(/[^a-z0-9]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function rowIsXdcc(r) {
    return String(r?.download_kind || "").toLowerCase() === "xdcc" || String(r?.command || "").toLowerCase().startsWith("!xdcc");
  }

  function sniffRowKey(r) {
    const xdcc = r.xdcc;
    const botSlot =
      rowIsXdcc(r) && xdcc && xdcc.botname != null
        ? `${xdcc.botname}|${xdcc.slot}`
        : "";
    return (
      (r.download_kind || "") +
      "|" +
      (r.network || "") +
      "|" +
      botSlot +
      "|" +
      (r.command || "") +
      "|" +
      normSniffTitle(r.title)
    );
  }

  function humanizeSearchBotNotice(text) {
    const t = String(text || "").trim();
    if (!t) return "";
    const hit = /Your search for ["“]([^"”]+)["”] returned (\d+) match/i.exec(t);
    if (hit) {
      const sec = /Search took ([\d.]+) seconds?/i.exec(t);
      const timing = sec ? ` Took about ${sec[1]}s.` : "";
      return `Found ${hit[2]} match(es) for “${hit[1]}”.${timing}`;
    }
    if (/^Notice:/i.test(t) && /SearchBot/i.test(t) && /Sending results to you as/i.test(t)) {
      return "Search bot is sending the result list…";
    }
    if (/^Notice:/i.test(t) && /SearchBot/i.test(t)) {
      return t
        .replace(/^Notice:\s*/i, "")
        .replace(/<<[^>]+>>\s*/g, "")
        .trim();
    }
    return "";
  }

  function humanizeIrcFeedText(text) {
    const friendly = humanizeSearchBotNotice(text);
    return friendly || String(text || "");
  }

  function sniffSignificantTokens(text) {
    return normSniffTitle(text)
      .split(" ")
      .filter((t) => t.length >= 3 && !SNIFF_TITLE_STOP.has(t) && !/^\d+$/.test(t));
  }

  function sniffTitlesLikelySame(irc, lib) {
    const na = normSniffTitle(irc);
    const nb = normSniffTitle(lib);
    if (!na || !nb) return false;
    if (na === nb) return true;
    const sigA = sniffSignificantTokens(irc);
    const sigB = sniffSignificantTokens(lib);
    if (!sigA.length || !sigB.length) return na === nb;
    const setA = new Set(sigA);
    const setB = new Set(sigB);
    const shared = [...setA].filter((t) => setB.has(t));
    if (!shared.length) return false;
    const minSide = Math.min(setA.size, setB.size);
    const need = Math.max(2, Math.ceil(0.65 * minSide));
    if (shared.length < need) return false;
    const longest = Math.max(...shared.map((t) => t.length));
    if (longest < 5) {
      const same =
        shared.length >= 2 &&
        [...setA].every((t) => setB.has(t)) &&
        [...setB].every((t) => setA.has(t));
      if (!same) return false;
    }
    if (minSide >= 4 && shared.length < Math.ceil(0.5 * minSide + 0.5)) return false;
    return true;
  }

  function libraryCatalog() {
    return typeof BP.getLibraryItems === "function" ? BP.getLibraryItems() : [];
  }

  function kennelHitLabel(hit) {
    if (!hit) return "";
    let label = hit.title || "In kennel";
    if (hit.format) label += " · " + String(hit.format).toUpperCase();
    if (hit.pubdate) label += " (" + hit.pubdate + ")";
    else if (hit.series) label += " · " + hit.series;
    return label;
  }

  function libraryHitForSniffTitle(title) {
    const libraryItemsCache = libraryCatalog();
    if (!title || !libraryItemsCache.length) return null;
    let best = null;
    let bestScore = 0;
    for (const item of libraryItemsCache) {
      const t = item.title || "";
      let matched = sniffTitlesLikelySame(title, t);
      if (!matched && item.authors) {
        matched = sniffTitlesLikelySame(title, t + " " + item.authors);
      }
      if (!matched) continue;
      const sigI = new Set(sniffSignificantTokens(title));
      const sigL = new Set(sniffSignificantTokens(t));
      const inter = [...sigI].filter((x) => sigL.has(x));
      const score = inter.length * 10 + (inter.length ? Math.max(...inter.map((x) => x.length)) : 0);
      if (score > bestScore) {
        bestScore = score;
        best = item;
      }
    }
    return best;
  }

  function parseSizeHint(hint) {
    const m = String(hint || "").match(/([\d.]+)\s*([kmgt])?\s*b/i);
    if (!m) return 0;
    let n = parseFloat(m[1]);
    const u = (m[2] || "").toLowerCase();
    if (u === "k") n *= 1024;
    else if (u === "m") n *= 1024 * 1024;
    else if (u === "g") n *= 1024 * 1024 * 1024;
    return n;
  }

  function sniffRowScore(r) {
    let s = parseSizeHint(r.size_hint) / 1e6;
    if (/\.epub\b/i.test(r.title || "")) s += 40;
    if (String(r.command || "").toLowerCase().startsWith("!get ")) s += 35;
    return s;
  }

  function sniffQualityFilters(rows) {
    let out = rows.slice();
    const epubOnly = document.getElementById("sniff-epub-only");
    if (epubOnly && epubOnly.checked) {
      out = out.filter((r) => {
        const title = r.title || "";
        const cmd = r.command || "";
        if (rowIsXdcc(r)) return /\.epub\b/i.test(title);
        return /\.epub\b/i.test(title) || /\.epub\b/i.test(cmd);
      });
    }
    const hideForeign = document.getElementById("sniff-hide-foreign");
    if (hideForeign && hideForeign.checked) {
      const getTitles = new Set();
      out.forEach((r) => {
        if (String(r.command || "").toLowerCase().startsWith("!get ")) {
          getTitles.add(normSniffTitle(r.title));
        }
      });
      out = out.filter((r) => {
        const srv = String(r.server || "").toLowerCase();
        const foreign = srv === "bsk" || srv === "horla" || srv === "oatmeal";
        if (!foreign) return true;
        if (String(r.command || "").toLowerCase().startsWith("!get ")) return true;
        return getTitles.has(normSniffTitle(r.title));
      });
    }
    return out;
  }

  function shortSniffNetwork(network) {
    const n = String(network || "").trim();
    if (!n) return "—";
    const abbr = { IRCHighway: "IH", Undernet: "UN", Rizon: "Riz" };
    return abbr[n] || n;
  }

  function shortSniffBot(server) {
    return String(server || "").trim();
  }

  function sniffFilterBlockers() {
    const parts = [];
    const q = (filterInput?.value || "").trim();
    if (q) parts.push(`filter “${q}”`);
    if (document.getElementById("sniff-epub-only")?.checked) parts.push("EPUB only");
    if (document.getElementById("sniff-hide-foreign")?.checked) parts.push("Hide risky foreign bots");
    if (document.getElementById("sniff-hide-kennel")?.checked) parts.push("Hide in-kennel matches");
    return parts;
  }

  function updateSniffWipeBtn() {
    const btn = document.getElementById("sniff-results-wipe");
    if (!btn) return;
    const n = getDisplayRows(resultRows).length;
    btn.disabled = n === 0;
    btn.textContent = n ? `Wipe matches (${n})` : "Wipe matches";
  }

  function wipeFilteredSniffResults() {
    const visible = getDisplayRows(resultRows);
    if (!visible.length) return;
    const drop = new Set(visible.map((r) => sniffRowKey(r)));
    const removed = visible.length;
    resultRows = resultRows.filter((r) => !drop.has(sniffRowKey(r)));
    drop.forEach((k) => sniffSelected.delete(k));
    sniffPage = 1;
    renderResults(resultRows);
    syncDraftFromUi(false);
    updateSniffWipeBtn();
  }

  function maybeRelaxEpubFilterForIrc(rows) {
    if (!rows.length) return false;
    const epubEl = document.getElementById("sniff-epub-only");
    if (!epubEl?.checked) return false;
    if (getDisplayRows(rows).length > 0) return false;
    const hasNonEpub = rows.some((r) => !/\.epub\b/i.test(String(r.title || "")));
    if (!hasNonEpub) return false;
    epubEl.checked = false;
    localStorage.setItem(SNIFF_EPUB_KEY, "0");
    BP.showAppToast?.(
      "Sniff",
      "EPUB only hid every row — turned off (IRC hits are often MOBI/CBZ).",
      "info"
    );
    return true;
  }

  async function ingestCompletedSearch(job, meta) {
    let full = job || {};
    if (
      full.type === "search" &&
      (!Array.isArray(full.results) || !full.results.length) &&
      ((full.result_count || 0) > 0 || full.state === "done")
    ) {
      full = await BP.api("/api/jobs/" + encodeURIComponent(full.id));
    }
    const rows = Array.isArray(full.results) ? full.results : [];
    if (!rows.length) {
      if ((full.result_count || 0) > 0) {
        throw new Error("Search finished but results could not be loaded — refresh and try again.");
      }
      return false;
    }
    sniffPage = 1;
    resultRows = rows;
    BP.state.activeSearchJob = full.id;
    if (resultsWrap) resultsWrap.classList.remove("hidden");
    const relaxed = maybeRelaxEpubFilterForIrc(resultRows);
    renderResults(resultRows);
    if (relaxed) renderResults(resultRows);
    const shown = getDisplayRows(resultRows).length;
    const blockers = sniffFilterBlockers();
    const hideNote =
      resultRows.length && shown < resultRows.length && blockers.length
        ? ` · ${shown} shown (${blockers.join(", ")})`
        : "";
    const note =
      full.search_notice && !resultRows.length ? ` · ${full.search_notice}` : "";
    if (searchMsg) {
      searchMsg.textContent = `${resultRows.length} matches${hideNote}${note}`;
      searchMsg.className = full.search_notice && !resultRows.length ? "bp-msg err" : "bp-msg muted";
    }
    const query = (meta && meta.query) || full.query || "";
    const channel = (meta && meta.channel) || full.channel || "";
    updateDraftMeta(query, channel, resultRows.length);
    updateResultsPanelVisibility();
    void pushDraftPatch({
      query,
      channel,
      filter: filterInput?.value || "",
      results: resultRows,
      job_id: full.id,
    });
    return true;
  }

  function sniffMatchesDoneJob(done) {
    if (!done || done.state !== "done") return false;
    const active = String(BP.state.activeSearchJob || "");
    if (active && active === String(done.id || "")) return true;
    const qv = (document.getElementById("query")?.value || "").trim().toLowerCase();
    const dq = String(done.query || "").trim().toLowerCase();
    if (qv && dq && qv === dq) return true;
    const ch = String(done.channel || "");
    const count = done.result_count || (Array.isArray(done.results) ? done.results.length : 0);
    if (
      count > 0 &&
      !resultRows.length &&
      (ch === "soulseek:slskd" || ch === "xdcc:index")
    ) {
      const updated = Number(done.updated_at || 0);
      if (updated && Date.now() / 1000 - updated < 900) return true;
    }
    return false;
  }

  function tryIngestDoneSearch(done) {
    if (!done || !sniffMatchesDoneJob(done)) return;
    const expect = done.result_count || (Array.isArray(done.results) ? done.results.length : 0);
    if (!expect) return;
    if (resultRows.length >= expect && resultRows.length > 0) return;
    BP.state.activeSearchJob = done.id;
    void ingestCompletedSearch(done, {
      query: done.query || document.getElementById("query")?.value?.trim(),
      channel: done.channel || document.getElementById("channel")?.value,
    });
  }

  BP.tryIngestDoneSearch = tryIngestDoneSearch;

  function sniffProgressLine(job) {
    const status = (job && job.irc_status) || "";
    if (status) {
      return typeof BP.friendlyIrcLine === "function" ? BP.friendlyIrcLine(status) : status;
    }
    if (job?.state === "queued") return "Waiting in IRC queue…";
    if (job?.state === "running") return "Connecting on IRC…";
    return "Waking IRC link…";
  }

  function pollSearchUntilDone(jobId, onDone, hooks) {
    const id = String(jobId || "").trim();
    if (!id) return;
    clearInterval(BP.state.searchPollTimer);
    BP.state.pollTimer = null;
    const intervalMs = (hooks && hooks.intervalMs) || 1200;
    async function tick() {
      await BP.refreshQueue?.();
      try {
        let job = await BP.api("/api/jobs/" + encodeURIComponent(id));
        if (job.state === "done") {
          clearInterval(BP.state.searchPollTimer);
          BP.state.searchPollTimer = null;
          if (job.type === "search") {
            try {
              job = await BP.api("/api/jobs/" + encodeURIComponent(id));
            } catch {
              /* keep partial */
            }
          }
          onDone(job);
        } else if (job.state === "cancelled") {
          clearInterval(BP.state.searchPollTimer);
          BP.state.searchPollTimer = null;
          hooks?.onFail?.(job);
          if (searchMsg) {
            searchMsg.textContent = "Search cancelled";
            searchMsg.className = "bp-msg muted";
          }
        } else if (job.state === "error") {
          clearInterval(BP.state.searchPollTimer);
          BP.state.searchPollTimer = null;
          hooks?.onFail?.(job);
          if (searchMsg) {
            searchMsg.textContent = job.error || "Search failed";
            searchMsg.className = "bp-msg err";
          }
        } else {
          hooks?.onProgress?.(job);
          if (searchMsg && (!hooks?.onProgress || !job.irc_status)) {
            searchMsg.textContent = sniffProgressLine(job);
            searchMsg.className = "bp-msg muted";
          }
        }
      } catch (err) {
        const msg = err?.message || "";
        if (/unreadable|Expecting value|JSON/i.test(msg)) return;
        console.warn("pollSearchUntilDone", err);
      }
    }
    void tick();
    BP.state.searchPollTimer = setInterval(tick, intervalMs);
    BP.state.pollTimer = BP.state.searchPollTimer;
  }

  function fetchMatchesDoneJob(job) {
    if (!job || job.type !== "download" || job.state !== "done") return false;
    const pending = BP.state.pendingFetch;
    if (pending?.jobId && String(job.id) === String(pending.jobId)) return true;
    return false;
  }

  function fetchBackfillAllowed(job) {
    if (!job || job.type !== "download" || job.state !== "done") return false;
    if (!(job.raw_bytes || job.staging_id)) return false;
    if (BP.state.notifiedDoneJobs.has(job.id)) return false;
    if (fetchMatchesDoneJob(job)) return true;
    return true;
  }

  function applyFetchDone(job, row, tr) {
    if (!job || job.state !== "done") return;
    if (tr) setFetchRowState(tr, "done");
    if (searchMsg) {
      searchMsg.textContent = "Fetch complete — see Fresh catches in Kennel.";
      searchMsg.className = "bp-msg muted";
    }
    BP.markUxFetchComplete?.();
    if (!BP.state.notifiedDoneJobs.has(job.id)) {
      BP.announceDownloadDone?.(job);
    }
    clearInterval(BP.state.fetchPollTimer);
    BP.state.fetchPollTimer = null;
    BP.state.pendingFetch = null;
  }

  function tryCompletePendingFetch(job, opts) {
    const backfill = !!(opts && opts.backfill);
    if (!fetchMatchesDoneJob(job) && !(backfill && fetchBackfillAllowed(job))) return;
    if (job.type === "download" && !(job.raw_bytes || job.staging_id)) {
      void BP.api("/api/jobs/" + encodeURIComponent(job.id))
        .then((full) => tryCompletePendingFetch(full, opts))
        .catch(() => {});
      return;
    }
    const pending = BP.state.pendingFetch || {};
    applyFetchDone(job, pending.row, pending.tr);
  }

  BP.tryCompletePendingFetch = tryCompletePendingFetch;

  function pollFetchUntilDone(jobId, row, tr) {
    const id = String(jobId || "").trim();
    if (!id) return;
    BP.state.pendingFetch = { jobId: id, row, tr };
    clearInterval(BP.state.fetchPollTimer);
    const intervalMs = 1200;
    async function tick() {
      await BP.refreshQueue?.();
      try {
        const job = await BP.api("/api/jobs/" + encodeURIComponent(id));
        if (job.state === "done") {
          clearInterval(BP.state.fetchPollTimer);
          BP.state.fetchPollTimer = null;
          applyFetchDone(job, row, tr);
        } else if (job.state === "cancelled" || job.state === "error") {
          clearInterval(BP.state.fetchPollTimer);
          BP.state.fetchPollTimer = null;
          BP.state.pendingFetch = null;
          if (tr) setFetchRowState(tr, "fetch");
          if (searchMsg) {
            searchMsg.textContent = job.error || "Fetch stopped";
            searchMsg.className = job.state === "error" ? "bp-msg err" : "bp-msg muted";
          }
        }
      } catch (err) {
        console.warn("pollFetchUntilDone", err);
      }
    }
    void tick();
    BP.state.fetchPollTimer = setInterval(tick, intervalMs);
  }

  async function syncActiveDownload() {
    const id = BP.state.pendingFetch?.jobId;
    if (id) {
      try {
        const job = await BP.api("/api/jobs/" + encodeURIComponent(id));
        if (job.type === "download" && job.state === "done") {
          tryCompletePendingFetch(job);
          return;
        }
      } catch (err) {
        console.warn("syncActiveDownload", err);
      }
    }
    try {
      const q = await BP.api("/api/queue");
      if (q.done_download) tryCompletePendingFetch(q.done_download, { backfill: true });
    } catch (err) {
      console.warn("syncActiveDownload(queue)", err);
    }
  }

  BP.syncActiveDownload = syncActiveDownload;

  async function syncActiveSearchResults() {
    const jid = BP.state.activeSearchJob;
    if (!jid) return;
    try {
      const job = await BP.api("/api/jobs/" + encodeURIComponent(jid));
      if (job.type !== "search" || job.state !== "done") return;
      tryIngestDoneSearch(job);
    } catch (err) {
      console.warn("syncActiveSearchResults", err);
    }
  }

  function getDisplayRows(rows) {
    const q = (filterInput?.value || "").toLowerCase();
    const hideKennel = document.getElementById("sniff-hide-kennel");
    let filtered = rows.filter((r) => {
      if (!q) return true;
      const title = (r.title && r.title.toLowerCase()) || "";
      const server = (r.server && r.server.toLowerCase()) || "";
      const network = (r.network && r.network.toLowerCase()) || "";
      const ft = typeof BP.sniffFileType === "function" ? BP.sniffFileType(r.title) : null;
      const typeQ = ft && (ft.label.toLowerCase().includes(q) || ft.ext.includes(q));
      return title.includes(q) || server.includes(q) || network.includes(q) || typeQ;
    });
    filtered = sniffQualityFilters(filtered);
    if (hideKennel && hideKennel.checked) {
      filtered = filtered.filter((r) => !libraryHitForSniffTitle(r.title));
    }
    const channelSel = document.getElementById("channel");
    const onUndernet =
      channelSel &&
      (String(channelSel.value || "").startsWith("undernet:") ||
        rows.some((r) => r.irc_target === "undernet:bookz"));
    if (onUndernet) {
      filtered.sort((a, b) => {
        const aGet = String(a.command || "").toLowerCase().startsWith("!get ");
        const bGet = String(b.command || "").toLowerCase().startsWith("!get ");
        if (aGet !== bGet) return aGet ? -1 : 1;
        return 0;
      });
    }
    return filtered;
  }

  function sniffPageCount(total) {
    return Math.max(1, Math.ceil(total / sniffPageSize) || 1);
  }

  function clampSniffPage(total) {
    const pages = sniffPageCount(total);
    if (sniffPage > pages) sniffPage = pages;
    if (sniffPage < 1) sniffPage = 1;
  }

  function updateSniffPager(total) {
    const pager = document.getElementById("sniff-pager");
    const status = document.getElementById("sniff-page-status");
    const prev = document.getElementById("sniff-page-prev");
    const next = document.getElementById("sniff-page-next");
    if (!pager) return;
    const show = total > 0;
    pager.classList.toggle("hidden", !show);
    if (!show) return;
    const pages = sniffPageCount(total);
    const start = (sniffPage - 1) * sniffPageSize + 1;
    const end = Math.min(total, sniffPage * sniffPageSize);
    if (status) {
      status.textContent =
        pages > 1
          ? `${start}–${end} of ${total} · page ${sniffPage}/${pages}`
          : `${total} row${total === 1 ? "" : "s"}`;
    }
    if (prev) prev.disabled = sniffPage <= 1;
    if (next) next.disabled = sniffPage >= pages;
  }

  function sniffBestPickKeys(rows) {
    const highlight = document.getElementById("sniff-highlight-pick");
    if (!highlight || !highlight.checked) return new Set();
    const best = new Map();
    rows.forEach((r) => {
      const key = normSniffTitle(r.title);
      if (!key) return;
      const score = sniffRowScore(r);
      const prev = best.get(key);
      if (!prev || score > prev.score) best.set(key, { score, row: r });
    });
    const keys = new Set();
    best.forEach((v) => {
      keys.add(
        (v.row.network || "") +
          "|" +
          (v.row.command || "") +
          "|" +
          normSniffTitle(v.row.title)
      );
    });
    return keys;
  }

  function bindSniffFilter(id, storageKey) {
    const el = document.getElementById(id);
    if (!el) return;
    el.checked = localStorage.getItem(storageKey) === "1";
    el.addEventListener("change", () => {
      localStorage.setItem(storageKey, el.checked ? "1" : "0");
      sniffPage = 1;
      renderResults(resultRows);
    });
  }

  function updateFetchSelectedUi() {
    const btn = document.getElementById("fetch-selected-btn");
    const picksBtn = document.getElementById("fetch-picks-btn");
    const n = sniffSelected.size;
    if (btn) {
      btn.disabled = n === 0;
      btn.textContent = n ? `Fetch selected (${n})` : "Fetch selected";
    }
    if (picksBtn) {
      const visible = getDisplayRows(resultRows);
      const pickKeys = sniffBestPickKeys(visible);
      const pickCount = visible.filter((r) => pickKeys.has(sniffRowKey(r))).length;
      picksBtn.disabled = !pickCount || !BP.state.activeSearchJob;
      picksBtn.textContent = pickCount ? `Queue highlighted picks (${Math.min(pickCount, SNIFF_BATCH_MAX)})` : "Queue highlighted picks";
    }
    const selectAll = document.getElementById("sniff-select-all");
    const filtered = getDisplayRows(resultRows);
    clampSniffPage(filtered.length);
    const pageRows = filtered.slice(
      (sniffPage - 1) * sniffPageSize,
      sniffPage * sniffPageSize
    );
    const visibleKeys = pageRows.map((r) => sniffRowKey(r));
    const selectedVisible = visibleKeys.filter((k) => sniffSelected.has(k)).length;
    if (selectAll && visibleKeys.length) {
      selectAll.checked = selectedVisible === visibleKeys.length;
      selectAll.indeterminate = selectedVisible > 0 && selectedVisible < visibleKeys.length;
    } else if (selectAll) {
      selectAll.checked = false;
      selectAll.indeterminate = false;
    }
  }

  async function queueSelectedFetches() {
    const msg = document.getElementById("fetch-selected-msg");
    if (!BP.state.activeSearchJob || !resultRows.length) {
      if (msg) {
        msg.textContent = "Run a sniff first so rows are tied to a search job.";
        msg.className = "bp-msg err";
      }
      return;
    }
    const rows = getDisplayRows(resultRows).filter((r) => sniffSelected.has(sniffRowKey(r)));
    const batch = rows.slice(0, SNIFF_BATCH_MAX);
    if (!batch.length) {
      if (msg) {
        msg.textContent = "Select one or more rows in the table first.";
        msg.className = "bp-msg err";
      }
      return;
    }
    if (
      !window.confirm(
        `Queue ${batch.length} fetch(es)? IRC runs one at a time; others wait in the queue.`
      )
    ) {
      return;
    }
    if (msg) {
      msg.textContent = "Queuing…";
      msg.className = "bp-msg muted";
    }
    try {
      const data = await BP.api(
        "/api/jobs/" + encodeURIComponent(BP.state.activeSearchJob) + "/select-batch",
        {
          method: "POST",
          body: JSON.stringify({ rows: batch, max: SNIFF_BATCH_MAX }),
        }
      );
      const n = (data.jobs || []).length;
      batch.forEach((r) => sniffSelected.delete(sniffRowKey(r)));
      updateFetchSelectedUi();
      renderResults(resultRows);
      if (msg) {
        msg.textContent = n
          ? `Queued ${n} fetch(es). Watch Fetch queue.`
          : "Nothing queued.";
        msg.className = data.errors && data.errors.length ? "bp-msg err" : "bp-msg muted";
      }
      BP.showAppToast("Fetch", `Queued ${n} job(s)`, n ? "ok" : "info");
      BP.refreshQueue();
    } catch (err) {
      if (msg) {
        msg.textContent = err.message;
        msg.className = "bp-msg err";
      }
    }
  }

  document.getElementById("fetch-selected-btn")?.addEventListener("click", () => void queueSelectedFetches());

  async function queueHighlightedPicks() {
    if (!BP.state.activeSearchJob || !resultRows.length) return;
    const visible = getDisplayRows(resultRows);
    const pickKeys = sniffBestPickKeys(visible);
    const picks = visible.filter((r) => pickKeys.has(sniffRowKey(r))).slice(0, SNIFF_BATCH_MAX);
    if (!picks.length) {
      BP.showAppToast("Fetch", "Turn on best-pick highlight or run a sniff first.", "info");
      return;
    }
    sniffSelected.clear();
    picks.forEach((r) => sniffSelected.add(sniffRowKey(r)));
    updateFetchSelectedUi();
    renderResults(resultRows);
    await queueSelectedFetches();
  }

  document.getElementById("fetch-picks-btn")?.addEventListener("click", () => void queueHighlightedPicks());

  document.getElementById("sniff-select-all")?.addEventListener("change", (ev) => {
    const on = ev.target.checked;
    const filtered = getDisplayRows(resultRows);
    const pageRows = filtered.slice(
      (sniffPage - 1) * sniffPageSize,
      sniffPage * sniffPageSize
    );
    if (on) {
      pageRows.forEach((r) => {
        if (sniffSelected.size >= SNIFF_BATCH_MAX) return;
        sniffSelected.add(sniffRowKey(r));
      });
      if (sniffSelected.size >= SNIFF_BATCH_MAX && pageRows.length > SNIFF_BATCH_MAX) {
        BP.showAppToast("Fetch", `At most ${SNIFF_BATCH_MAX} rows at a time.`, "info");
      }
    } else {
      pageRows.forEach((r) => sniffSelected.delete(sniffRowKey(r)));
    }
    updateFetchSelectedUi();
    renderResults(resultRows);
  });

  bindSniffFilter("sniff-epub-only", SNIFF_EPUB_KEY);
  bindSniffFilter("sniff-hide-foreign", SNIFF_FOREIGN_KEY);
  const sniffPickEl = document.getElementById("sniff-highlight-pick");
  if (sniffPickEl) {
    const stored = localStorage.getItem(SNIFF_PICK_KEY);
    sniffPickEl.checked = stored === null || stored === "1";
    sniffPickEl.addEventListener("change", () => {
      localStorage.setItem(SNIFF_PICK_KEY, sniffPickEl.checked ? "1" : "0");
      renderResults(resultRows);
    });
  }

  function renderResults(rows) {
    BP.state._resultRows = rows;
    if (!resultsBody) return;
    resultsBody.innerHTML = "";
    const filtered = getDisplayRows(rows);
    clampSniffPage(filtered.length);
    const picks = sniffBestPickKeys(filtered);
    const pageRows = filtered.slice(
      (sniffPage - 1) * sniffPageSize,
      sniffPage * sniffPageSize
    );
    pageRows.forEach((r) => {
      const tr = document.createElement("tr");
      const pickKey = sniffRowKey(r);
      if (picks.has(pickKey)) tr.classList.add("bp-sniff-pick");
      const hit = libraryHitForSniffTitle(r.title);
      const hitId = "sniff-hit-" + sniffRowKey(r).replace(/[^\w-]/g, "-");
      const kennelNote = hit
        ? '<span class="bp-sniff-kennel"><span class="bp-sniff-kennel-tag">In kennel</span> ' +
          '<button type="button" class="bp-link-btn sniff-kennel-link" data-lib-id="' +
          BP.escapeHtml(hit.id) +
          '">' +
          BP.escapeHtml(kennelHitLabel(hit)) +
          "</button></span>"
        : "";
      const fetchLabel = hit ? "Fetch again" : "Fetch";
      const fetchClass = hit ? "bp-btn dl-row dl-row--again" : "bp-btn dl-row";
      const netFull = String(r.network || "—");
      const botFull = String(r.server || "");
      const fileType = typeof BP.sniffFileType === "function" ? BP.sniffFileType(r.title) : { label: "—", ext: "", title: "" };
      const typeBadge =
        fileType.label && fileType.label !== "—"
          ? '<span class="bp-sniff-type-badge" title="' +
            BP.escapeHtml(fileType.title || fileType.label) +
            '">' +
            BP.escapeHtml(fileType.label) +
            "</span>"
          : "";
      tr.innerHTML =
        '<td class="bp-col-select"><input type="checkbox" class="sniff-row-check" aria-label="Select row" /></td>' +
        '<td class="bp-col-net" title="' +
        BP.escapeHtml(netFull) +
        '">' +
        BP.escapeHtml(shortSniffNetwork(r.network)) +
        '</td><td class="bp-col-bot" title="' +
        BP.escapeHtml(botFull) +
        '">' +
        BP.escapeHtml(shortSniffBot(r.server)) +
        '</td><td class="bp-sniff-title-cell">' +
        '<div class="bp-sniff-title-line">' +
        typeBadge +
        '<span class="bp-sniff-title-text" id="' +
        hitId +
        '-title">' +
        BP.escapeHtml(r.title || "") +
        "</span></div>" +
        kennelNote +
        "</td><td>" +
        BP.escapeHtml(r.size_hint || "—") +
        '</td><td><button type="button" class="' +
        fetchClass +
        '"' +
        (hit ? ' aria-describedby="' + hitId + '-title"' : "") +
        ">" +
        fetchLabel +
        "</button></td>";
      if (hit) tr.classList.add("bp-sniff-in-kennel");
      const rowCheck = tr.querySelector(".sniff-row-check");
      if (rowCheck) {
        rowCheck.checked = sniffSelected.has(pickKey);
        rowCheck.addEventListener("change", () => {
          if (rowCheck.checked) {
            if (sniffSelected.size >= SNIFF_BATCH_MAX) {
              rowCheck.checked = false;
              BP.showAppToast("Fetch", `At most ${SNIFF_BATCH_MAX} rows at a time.`, "info");
              return;
            }
            sniffSelected.add(pickKey);
          } else {
            sniffSelected.delete(pickKey);
          }
          updateFetchSelectedUi();
        });
      }
      const dlBtn = tr.querySelector(".dl-row");
      if (dlBtn) dlBtn.addEventListener("click", () => startDownload(r, tr));
      tr.querySelector(".sniff-kennel-link")?.addEventListener("click", () => BP.focusLibraryItem?.(hit.id));
      resultsBody.appendChild(tr);
    });
    updateSniffPager(filtered.length);
    updateFetchSelectedUi();
    const filterNote = document.getElementById("sniff-filter-note");
    if (filterNote) {
      const blockers = sniffFilterBlockers();
      if (rows.length && filtered.length === 0 && blockers.length) {
        filterNote.textContent = `No rows shown — ${blockers.join(", ")}. (${rows.length} in this sniff.)`;
        filterNote.classList.remove("hidden");
      } else if (rows.length && filtered.length < rows.length && blockers.length) {
        filterNote.textContent = `Showing ${filtered.length} of ${rows.length} (${blockers.join(", ")}).`;
        filterNote.classList.remove("hidden");
      } else {
        filterNote.textContent = "";
        filterNote.classList.add("hidden");
      }
    }
    updateSniffWipeBtn();
    syncSniffResultsLayout();
  }

  filterInput.addEventListener("input", () => {
    sniffPage = 1;
    renderResults(resultRows);
    syncDraftFromUi(false);
  });

  document.getElementById("query")?.addEventListener("input", () => updateFormSchedule());
  document.getElementById("channel")?.addEventListener("change", () => updateFormSchedule());

  formSchedEnabled?.addEventListener("change", () => {
    if (suppressFormSchedEvents) return;
    if (formSchedInterval) formSchedInterval.disabled = !formSchedEnabled.checked;
    void patchFormSchedule({
      enabled: formSchedEnabled.checked,
      interval_hours: parseInt(formSchedInterval?.value, 10) || 24,
    });
  });
  formSchedInterval?.addEventListener("change", () => {
    if (suppressFormSchedEvents || !formSchedEnabled?.checked) return;
    void patchFormSchedule({
      enabled: true,
      interval_hours: parseInt(formSchedInterval.value, 10) || 24,
    });
  });
  formSchedHelp?.addEventListener("click", (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    const open = formSchedHelpWrap?.classList.toggle("is-open");
    formSchedHelp.setAttribute("aria-expanded", open ? "true" : "false");
  });
  document.addEventListener("click", (ev) => {
    if (!formSchedHelpWrap?.classList.contains("is-open")) return;
    if (formSchedHelpWrap.contains(ev.target)) return;
    formSchedHelpWrap.classList.remove("is-open");
    formSchedHelp?.setAttribute("aria-expanded", "false");
  });
  formSchedHelp?.addEventListener("blur", () => {
    window.setTimeout(() => {
      if (formSchedHelpWrap && !formSchedHelpWrap.matches(":focus-within")) {
        formSchedHelpWrap.classList.remove("is-open");
        formSchedHelp?.setAttribute("aria-expanded", "false");
      }
    }, 120);
  });

  document.getElementById("sniff-results-wipe")?.addEventListener("click", () => {
    wipeFilteredSniffResults();
  });

  const sniffPageSizeEl = document.getElementById("sniff-page-size");
  if (sniffPageSizeEl) {
    sniffPageSizeEl.value = String(sniffPageSize);
    if (!sniffPageSizeEl.querySelector('option[value="' + sniffPageSize + '"]')) {
      sniffPageSizeEl.value = "50";
      sniffPageSize = 50;
    }
    sniffPageSizeEl.addEventListener("change", () => {
      sniffPageSize = parseInt(sniffPageSizeEl.value, 10) || 50;
      localStorage.setItem(SNIFF_PAGE_SIZE_KEY, String(sniffPageSize));
      sniffPage = 1;
      renderResults(resultRows);
    });
  }
  document.getElementById("sniff-page-prev")?.addEventListener("click", () => {
    if (sniffPage > 1) {
      sniffPage -= 1;
      renderResults(resultRows);
    }
  });
  document.getElementById("sniff-page-next")?.addEventListener("click", () => {
    const total = getDisplayRows(resultRows).length;
    if (sniffPage < sniffPageCount(total)) {
      sniffPage += 1;
      renderResults(resultRows);
    }
  });


  function ingestWalkTrailResults(rows, query) {
    resultRows = rows;
    BP.state.activeSearchJob = "walk-trail-practice";
    if (resultsWrap) resultsWrap.classList.remove("hidden");
    renderResults(rows);
    if (searchMsg) {
      searchMsg.textContent = rows.length + ' practice match(es) for "' + query + '".';
      searchMsg.className = "bp-msg muted";
    }
  }

  searchForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (BP.walkTrailActive) {
      const queryEl = document.getElementById("query");
      const channelElWalk = document.getElementById("channel");
      const body = {
        query: queryEl?.value.trim() || "",
        channel: channelElWalk?.value || "",
      };
      if (!body.query) return;
      if (body.channel !== "irchighway:ebooks") {
        if (searchMsg) {
          searchMsg.textContent = "Walk the Trail uses Main trail only.";
          searchMsg.className = "bp-msg err";
        }
        return;
      }
      if (filterInput) filterInput.value = "";
      resultRows = [];
      renderResults([]);
      if (resultsWrap) resultsWrap.classList.remove("hidden");
      await BP.walkTrailOnSearch?.(body);
      return;
    }
    const channelEl = document.getElementById("channel");
    const channelVal = channelEl?.value || "";
    if (channelVal === "xdcc:index") {
      searchMsg.textContent = "Querying XDCC index…";
    } else if (channelVal === "soulseek:slskd") {
      searchMsg.textContent = "Querying Soulseek…";
    } else if (channelVal === "all") {
      searchMsg.textContent = "Sniffing all IRC networks…";
    } else {
      searchMsg.textContent = "Waking IRC link…";
    }
    searchMsg.className = "bp-msg muted";
    BP.markUxSniffStarted?.();
    if (filterInput) filterInput.value = "";
    resultRows = [];
    renderResults([]);
    updateFormSchedule();
    if (resultsWrap) resultsWrap.classList.remove("hidden");
    try {
      const queryEl = document.getElementById("query");
      const channelEl = document.getElementById("channel");
      const body = {
        query: queryEl.value.trim(),
        channel: channelEl.value,
      };
      if (!body.query) return;
      BP.rememberSearchQuery(body.query);
      localStorage.setItem(SEARCH_CHANNEL_KEY, body.channel);
      const data = await BP.api("/api/search", { method: "POST", body: JSON.stringify(body) });
      const jobId = String(data?.job?.id || "").trim();
      if (!jobId) {
        searchMsg.textContent = "Search started without a job id — try again.";
        searchMsg.className = "bp-msg err";
        return;
      }
      BP.state.activeSearchJob = jobId;
      void BP.refreshQueue?.();
      const applySearchDone = (job) => {
        void ingestCompletedSearch(job, { query: body.query, channel: body.channel }).catch((err) => {
          console.error("applySearchDone", err);
          if (searchMsg) {
            searchMsg.textContent = err.message || "Could not show results (see console)";
            searchMsg.className = "bp-msg err";
          }
        });
      };
      if (data.job.state === "done") {
        if (Array.isArray(data.job.results)) {
          applySearchDone(data.job);
        } else {
          void BP.api("/api/jobs/" + encodeURIComponent(data.job.id))
            .then(applySearchDone)
            .catch(() => applySearchDone(data.job));
        }
        BP.refreshQueue?.();
      } else if (data.job.state === "error") {
        searchMsg.textContent = data.job.error || "Search failed";
        searchMsg.className = "bp-msg err";
      } else {
        const pollMs =
          body.channel === "xdcc:index" ? 600 : body.channel === "soulseek:slskd" ? 1200 : 1500;
        pollSearchUntilDone(jobId, applySearchDone, {
          intervalMs: pollMs,
          onProgress: (job) => {
            const partial = Array.isArray(job.results) ? job.results : [];
            if (partial.length) {
              void ingestCompletedSearch(job, { query: body.query, channel: body.channel });
            } else if (searchMsg) {
              searchMsg.textContent =
                body.channel === "xdcc:index"
                  ? job.irc_status || "Querying XDCC index…"
                  : body.channel === "soulseek:slskd"
                    ? job.irc_status || "Querying Soulseek…"
                    : sniffProgressLine(job);
              searchMsg.className = "bp-msg muted";
            }
          },
        });
      }
    } catch (err) {
      searchMsg.textContent = err.message;
      searchMsg.className = "bp-msg err";
    }
  });

  function setFetchRowState(tr, state) {
    const btn = tr?.querySelector(".dl-row");
    if (!btn) return;
    btn.removeAttribute("aria-busy");
    btn.classList.remove("bp-btn--loading", "bp-btn--done");
    if (state === "loading") {
      btn.disabled = true;
      btn.classList.add("bp-btn--loading");
      btn.setAttribute("aria-busy", "true");
      btn.textContent = "";
    } else if (state === "done") {
      btn.disabled = true;
      btn.classList.add("bp-btn--done");
      btn.textContent = "Done";
    } else {
      btn.disabled = false;
      btn.textContent = "Fetch";
    }
  }

  async function startDownload(row, tr) {
    if (BP.walkTrailActive) {
      if (row.walk_trail) {
        await BP.walkTrailOnFetch?.(row, tr);
        return;
      }
      BP.showAppToast("Walk the Trail", "Fetch the practice .mobi row for your query.", "info");
      return;
    }
    if (!BP.state.activeSearchJob) return;
    if (tr) setFetchRowState(tr, "loading");
    searchMsg.textContent = "Unleashing the fetch…";
    try {
      const data = await BP.api("/api/jobs/" + encodeURIComponent(BP.state.activeSearchJob) + "/select", {
        method: "POST",
        body: JSON.stringify({
          command: row.command,
          title: row.title,
          irc_target: row.irc_target || undefined,
          download_kind: row.download_kind || undefined,
          xdcc: row.xdcc || undefined,
          soulseek: row.soulseek || undefined,
        }),
      });
      const fetchId = String(data?.job?.id || "").trim();
      if (!fetchId) {
        if (tr) setFetchRowState(tr, "fetch");
        searchMsg.textContent = "Fetch started without a job id.";
        searchMsg.className = "bp-msg err";
        return;
      }
      void BP.refreshQueue?.();
      pollFetchUntilDone(fetchId, row, tr);
    } catch (err) {
      if (tr) setFetchRowState(tr, "fetch");
      searchMsg.textContent = err.message;
      searchMsg.className = "bp-msg err";
    }
  }

  const TOSS_CONFIRM_PHRASES = [
    "bury the bone",
    "drop this bone",
    "not in my kennel",
    "scratch this fetch",
    "lose the trail",
    "bury it deep",
    "dig it out",
    "pass on this one",
  ];

  async function confirmToss(title, opts) {
    if (typeof BP.openTossModal === "function") {
      return BP.openTossModal(title, opts);
    }
    const phrase = TOSS_CONFIRM_PHRASES[Math.floor(Math.random() * TOSS_CONFIRM_PHRASES.length)];
    const hint = title ? ` (${title})` : "";
    const typed = window.prompt(`Toss this from your kennel${hint}?\n\nType exactly: ${phrase}`);
    return typed === phrase;
  }

  async function tossLibraryItem(itemId) {
    await BP.api("/api/library/" + encodeURIComponent(itemId), { method: "DELETE" });
    BP.loadLibrary();
  }

  // exports
  BP.applyDraft = applyDraft;
  BP.bindSniffFilter = bindSniffFilter;
  BP.wipeFilteredSniffResults = wipeFilteredSniffResults;
  BP.channelDisplayLabel = channelDisplayLabel;
  BP.clearSniffQueryInput = clearSniffQueryInput;
  BP.confirmToss = confirmToss;
  BP.ingestWalkTrailResults = ingestWalkTrailResults;
  BP.humanizeIrcFeedText = humanizeIrcFeedText;
  BP.humanizeSearchBotNotice = humanizeSearchBotNotice;
  BP.libraryHitForSniffTitle = libraryHitForSniffTitle;
  BP.loadSavedSearch = loadSavedSearch;
  BP.loadSearchWorkspace = loadSearchWorkspace;
  BP.moveSavedSearch = moveSavedSearch;
  BP.normSniffTitle = normSniffTitle;
  BP.parseSizeHint = parseSizeHint;
  BP.pushDraftPatch = pushDraftPatch;
  BP.queueSelectedFetches = queueSelectedFetches;
  BP.removeSavedSearch = removeSavedSearch;
  BP.renderResults = renderResults;
  BP.renderSavedSearchList = renderSavedSearchList;
  BP.scheduleDraftSync = scheduleDraftSync;
  BP.setFetchRowState = setFetchRowState;
  BP.sniffBestPickKeys = sniffBestPickKeys;
  BP.sniffQualityFilters = sniffQualityFilters;
  BP.sniffRowKey = sniffRowKey;
  BP.sniffRowScore = sniffRowScore;
  BP.sniffSignificantTokens = sniffSignificantTokens;
  BP.sniffTitlesLikelySame = sniffTitlesLikelySame;
  BP.startDownload = startDownload;
  BP.syncDraftFromUi = syncDraftFromUi;
  BP.tossLibraryItem = tossLibraryItem;
  BP.updateDraftMeta = updateDraftMeta;
  BP.updateFetchSelectedUi = updateFetchSelectedUi;
  BP.updateResultsPanelVisibility = updateResultsPanelVisibility;
  BP.ingestCompletedSearch = ingestCompletedSearch;
  BP.syncActiveSearchResults = syncActiveSearchResults;
})(window.BookPup);
