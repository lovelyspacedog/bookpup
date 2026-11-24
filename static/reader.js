(function () {
  "use strict";

  const modal = document.getElementById("reader-modal");
  const titleEl = document.getElementById("reader-title");
  const bodyEl = document.getElementById("reader-body");
  const msgEl = document.getElementById("reader-msg");
  const closeBtn = document.getElementById("reader-close");
  const prevBtn = document.getElementById("reader-prev");
  const nextBtn = document.getElementById("reader-next");
  const epubNav = document.getElementById("reader-epub-nav");
  const progressFill = document.getElementById("reader-progress-fill");
  const progressLabel = document.getElementById("reader-progress-label");
  const bookmarkBtn = document.getElementById("reader-bookmark");
  const bookmarksEl = document.getElementById("reader-bookmarks");
  const spreadBtn = document.getElementById("reader-dual-page");
  const studyToggle = document.getElementById("reader-study-toggle");
  const studyPanel = document.getElementById("reader-study");
  const studyStatus = document.getElementById("reader-study-status");
  const studySummarize = document.getElementById("reader-study-summarize");
  const studySummary = document.getElementById("reader-study-summary");
  const studyQuestion = document.getElementById("reader-study-question");
  const studyAskBtn = document.getElementById("reader-study-ask");
  const studyAnswer = document.getElementById("reader-study-answer");

  const CSRF = { "X-Bookpup": "1" };

  let activeBook = null;
  let activeRendition = null;
  let activeBlobUrl = null;
  let stopResize = null;
  let stopProgress = null;
  let epubHost = null;
  let epubScrolled = false;
  let epubLayoutH = 320;
  let keyHandler = null;
  let activeItemId = null;
  let activeFormat = null;
  let activeAuthHeader = null;
  let activeSharedOwner = null;
  let readingState = null;
  let saveTimer = null;
  let epubSpread = localStorage.getItem("bookpupEpubSpread") === "always" ? "always" : "none";
  let activeTxtLength = 0;
  let readerAiReady = false;
  let studyBusy = false;
  const studyHistory = [];
  let comicPage = 0;
  let comicPageCount = 0;
  const COMIC_FMTS = new Set(["cbz", "cbr", "cb7"]);
  const SCROLL_FMTS = new Set(["txt", "md", "html"]);

  function inlineMarkdown(text) {
    let t = escapeHtml(text);
    t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
    t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    t = t.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, href) => {
      const safe = String(href).replace(/"/g, "%22");
      return '<a href="' + safe + '" rel="noopener noreferrer">' + label + "</a>";
    });
    return t;
  }

  function markdownToHtml(src) {
    const lines = String(src || "").split("\n");
    const out = [];
    let inCode = false;
    const codeBuf = [];
    for (const line of lines) {
      if (line.startsWith("```")) {
        if (inCode) {
          out.push("<pre><code>" + escapeHtml(codeBuf.join("\n")) + "</code></pre>");
          codeBuf.length = 0;
          inCode = false;
        } else {
          inCode = true;
        }
        continue;
      }
      if (inCode) {
        codeBuf.push(line);
        continue;
      }
      const hm = line.match(/^(#{1,6})\s+(.*)$/);
      if (hm) {
        const lvl = hm[1].length;
        out.push("<h" + lvl + ">" + inlineMarkdown(hm[2]) + "</h" + lvl + ">");
        continue;
      }
      if (!line.trim()) {
        out.push("");
        continue;
      }
      out.push("<p>" + inlineMarkdown(line) + "</p>");
    }
    if (inCode && codeBuf.length) {
      out.push("<pre><code>" + escapeHtml(codeBuf.join("\n")) + "</code></pre>");
    }
    return out.join("\n");
  }

  function stripUnsafeHtml(html) {
    return String(html || "")
      .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "")
      .replace(/\s+on\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, "");
  }

  function scrollableReaderEl() {
    return bodyEl.querySelector(".bp-reader-txt, .bp-reader-md, .bp-reader-html-frame");
  }

  function scrollRatioFor(el) {
    if (!el) return 0;
    if (el.classList.contains("bp-reader-html-frame")) {
      const doc = el.contentDocument;
      if (!doc) return 0;
      const root = doc.scrollingElement || doc.documentElement;
      const max = root.scrollHeight - root.clientHeight;
      return max > 0 ? root.scrollTop / max : 0;
    }
    const max = el.scrollHeight - el.clientHeight;
    return max > 0 ? el.scrollTop / max : 0;
  }

  function applyScrollRatio(el, ratio) {
    if (!el) return;
    const r = Math.max(0, Math.min(1, ratio || 0));
    if (el.classList.contains("bp-reader-html-frame")) {
      const doc = el.contentDocument;
      if (!doc) return;
      const root = doc.scrollingElement || doc.documentElement;
      const max = root.scrollHeight - root.clientHeight;
      root.scrollTop = Math.round(max * r);
      return;
    }
    const max = el.scrollHeight - el.clientHeight;
    el.scrollTop = Math.round(max * r);
  }
  let comicDebugActions = null;
  let comicDebugOverlay = null;

  function clearComicDebugUi() {
    comicDebugActions?.remove();
    comicDebugActions = null;
    comicDebugOverlay?.remove();
    comicDebugOverlay = null;
  }

  function openComicDebug(stderr) {
    comicDebugOverlay?.remove();
    const panel = document.createElement("div");
    panel.className = "bp-comic-debug-panel";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Comic debug output");
    const head = document.createElement("div");
    head.className = "bp-comic-debug-head";
    const title = document.createElement("span");
    title.textContent = "Tool output";
    const closeDbg = document.createElement("button");
    closeDbg.type = "button";
    closeDbg.className = "bp-btn";
    closeDbg.textContent = "Close";
    closeDbg.onclick = () => panel.remove();
    head.append(title, closeDbg);
    const ta = document.createElement("textarea");
    ta.className = "bp-comic-debug-log";
    ta.readOnly = true;
    ta.spellcheck = false;
    ta.value = stderr || "(empty)";
    panel.append(head, ta);
    modal.appendChild(panel);
    comicDebugOverlay = panel;
    ta.focus();
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function authHeaders(authHeader) {
    return { ...CSRF, ...(authHeader ? { Authorization: authHeader } : {}) };
  }

  function catalogOwnerQuery() {
    return activeSharedOwner ? "?owner=" + encodeURIComponent(activeSharedOwner) : "";
  }

  let activeOffline = false;

  async function fetchReading(itemId, authHeader) {
    const offline = window.BookPup?.offlineBooks;
    if (activeOffline && offline) {
      return offline.getReadingState(itemId);
    }
    const res = await fetch(
      "/api/library/" + encodeURIComponent(itemId) + "/reading" + catalogOwnerQuery(),
      {
      headers: authHeaders(authHeader),
    }
    );
    if (!res.ok) return { bookmarks: [], location: null };
    return res.json();
  }

  function currentLocationSnapshot() {
    if (activeFormat === "epub" && activeRendition) {
      const loc = activeRendition.currentLocation();
      const cfi = loc?.start?.cfi || null;
      const pct =
        typeof loc?.start?.percentage === "number" ? loc.start.percentage : null;
      if (epubScrolled) {
        const t = activeScrollTarget();
        const scroll = t && t.max > 0 ? t.top / t.max : pct ?? 0;
        return { type: "epub", flow: "scrolled", scroll, cfi, percentage: pct };
      }
      return { type: "epub", flow: "paginated", cfi, percentage: pct };
    }
    if (SCROLL_FMTS.has(activeFormat)) {
      const el = scrollableReaderEl();
      if (!el) return null;
      return { type: activeFormat, scroll: scrollRatioFor(el) };
    }
    if (activeFormat === "pdf") {
      const page = readingState?.location?.type === "pdf" ? readingState.location.page : 1;
      return { type: "pdf", page: page || 1 };
    }
    if (COMIC_FMTS.has(activeFormat)) {
      return { type: activeFormat, page: comicPage, pages: comicPageCount };
    }
    return null;
  }

  async function saveReadingLocation(authHeader) {
    if (!activeItemId) return;
    const loc = currentLocationSnapshot();
    if (!loc) return;
    const offline = window.BookPup?.offlineBooks;
    if ((activeOffline || !navigator.onLine) && offline) {
      try {
        await offline.setReadingState(activeItemId, { location: loc });
        await offline.enqueueReadingSync(activeItemId, loc);
      } catch {
        /* best effort */
      }
      return;
    }
    try {
      await fetch("/api/library/" + encodeURIComponent(activeItemId) + "/reading", {
        method: "POST",
        headers: { ...authHeaders(authHeader), "Content-Type": "application/json" },
        body: JSON.stringify({
          location: loc,
          ...(activeSharedOwner ? { owner: activeSharedOwner } : {}),
        }),
      });
    } catch (_e) {
      /* best effort */
    }
  }

  function scheduleSaveReading(authHeader) {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => saveReadingLocation(authHeader), 1200);
  }

  function restoreScrollRatio(ratio) {
    const t = activeScrollTarget();
    if (!t || typeof ratio !== "number") return;
    t.el.scrollTop = Math.round(t.max * Math.max(0, Math.min(1, ratio)));
    refreshScrollProgress();
  }

  function renderBookmarks(authHeader) {
    if (!bookmarksEl) return;
    const marks = (readingState && readingState.bookmarks) || [];
    if (!marks.length) {
      bookmarksEl.classList.add("hidden");
      bookmarksEl.innerHTML = "";
      return;
    }
    bookmarksEl.classList.remove("hidden");
    bookmarksEl.innerHTML =
      '<p class="bp-reader-bookmarks-title">Bookmarks</p><ul class="bp-reader-bookmarks-list"></ul>';
    const ul = bookmarksEl.querySelector("ul");
    marks.forEach((mark) => {
      const li = document.createElement("li");
      li.innerHTML =
        '<button type="button" class="bp-btn bp-bookmark-go"></button> ' +
        '<button type="button" class="bp-btn bp-bookmark-del" aria-label="Remove">×</button>';
      const go = li.querySelector(".bp-bookmark-go");
      go.textContent = mark.label || "Bookmark";
      go.addEventListener("click", () => goToLocation(mark.location, authHeader));
      li.querySelector(".bp-bookmark-del").addEventListener("click", () =>
        deleteBookmark(mark.id, authHeader)
      );
      ul.appendChild(li);
    });
  }

  async function goToLocation(loc, authHeader) {
    if (!loc || !loc.type) return;
    if (loc.type === "epub" && activeRendition) {
      if (loc.cfi) {
        try {
          await activeRendition.display(loc.cfi);
        } catch (_e) {}
      }
      if (loc.flow === "scrolled" || epubScrolled) {
        const ratio =
          typeof loc.scroll === "number"
            ? loc.scroll
            : typeof loc.percentage === "number"
              ? loc.percentage
              : null;
        if (ratio != null) restoreScrollRatio(ratio);
      }
      return;
    }
    if (SCROLL_FMTS.has(loc.type)) {
      applyScrollRatio(scrollableReaderEl(), loc.scroll);
      return;
    }
    if (loc.type === "pdf" && activeBlobUrl) {
      const iframe = bodyEl.querySelector(".bp-reader-pdf");
      if (iframe) iframe.src = activeBlobUrl + "#page=" + (loc.page || 1);
    }
  }

  async function deleteBookmark(bookmarkId, authHeader) {
    if (!activeItemId) return;
    await fetch(
      "/api/library/" +
        encodeURIComponent(activeItemId) +
        "/bookmarks/" +
        encodeURIComponent(bookmarkId) +
        catalogOwnerQuery(),
      { method: "DELETE", headers: authHeaders(authHeader) }
    );
    readingState = await fetchReading(activeItemId, authHeader);
    renderBookmarks(authHeader);
  }

  async function addBookmark(authHeader) {
    if (!activeItemId) return;
    const loc = currentLocationSnapshot();
    if (!loc) return;
    const label = window.prompt("Bookmark label", "Here") || "Bookmark";
    const res = await fetch("/api/library/" + encodeURIComponent(activeItemId) + "/bookmarks", {
      method: "POST",
      headers: { ...authHeaders(authHeader), "Content-Type": "application/json" },
      body: JSON.stringify({
        label: label,
        location: loc,
        ...(activeSharedOwner ? { owner: activeSharedOwner } : {}),
      }),
    });
    if (!res.ok) return;
    const data = await res.json();
    readingState = data.reading || (await fetchReading(activeItemId, authHeader));
    renderBookmarks(authHeader);
  }

  function cleanup() {
    if (activeRendition) {
      try {
        activeRendition.destroy();
      } catch (_e) {}
      activeRendition = null;
    }
    if (activeBook) {
      try {
        activeBook.destroy();
      } catch (_e) {}
      activeBook = null;
    }
    if (activeBlobUrl) {
      URL.revokeObjectURL(activeBlobUrl);
      activeBlobUrl = null;
    }
    if (stopResize) {
      stopResize();
      stopResize = null;
    }
    if (stopProgress) {
      stopProgress();
      stopProgress = null;
    }
    if (keyHandler) {
      modal.removeEventListener("keydown", keyHandler);
      keyHandler = null;
    }
    epubHost = null;
    epubScrolled = false;
    if (progressFill) progressFill.style.width = "0%";
    if (progressLabel) progressLabel.textContent = "0%";
    bodyEl.innerHTML = "";
    bodyEl.classList.remove("bp-reader-body--scroll", "bp-reader-body--comic");
    epubNav.classList.add("hidden");
    epubNav.classList.remove("bp-reader-epub-nav--comic");
    if (prevBtn) prevBtn.classList.remove("hidden");
    if (nextBtn) nextBtn.classList.remove("hidden");
    if (spreadBtn) {
      spreadBtn.classList.add("hidden");
      spreadBtn.setAttribute("aria-pressed", "false");
      spreadBtn.onclick = null;
    }
    msgEl.textContent = "";
    msgEl.className = "bp-msg muted";
    if (bookmarksEl) {
      bookmarksEl.classList.add("hidden");
      bookmarksEl.innerHTML = "";
    }
    if (studyPanel) studyPanel.classList.add("hidden");
    if (studyToggle) studyToggle.setAttribute("aria-expanded", "false");
    if (studySummary) {
      studySummary.classList.add("hidden");
      studySummary.textContent = "";
    }
    if (studyAnswer) {
      studyAnswer.classList.add("hidden");
      studyAnswer.textContent = "";
    }
    if (studyStatus) studyStatus.textContent = "";
    studyHistory.length = 0;
    activeTxtLength = 0;
    readerAiReady = false;
    clearTimeout(saveTimer);
    activeItemId = null;
    activeFormat = null;
    activeOffline = false;
    activeAuthHeader = null;
    activeSharedOwner = null;
    readingState = null;
    clearComicDebugUi();
  }

  function fail(msg, debugStderr) {
    clearComicDebugUi();
    msgEl.textContent = msg;
    msgEl.className = "bp-msg err";
    if (debugStderr) {
      const row = document.createElement("p");
      row.className = "bp-comic-debug-actions";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "bp-btn";
      btn.textContent = "Debug…";
      btn.onclick = () => openComicDebug(debugStderr);
      row.appendChild(btn);
      msgEl.insertAdjacentElement("afterend", row);
      comicDebugActions = row;
    }
  }

  async function closeReader() {
    clearTimeout(saveTimer);
    if (activeItemId && activeAuthHeader) await saveReadingLocation(activeAuthHeader);
    cleanup();
    modal.classList.add("hidden");
    document.body.classList.remove("bp-reader-open");
  }

  closeBtn.addEventListener("click", () => void closeReader());
  modal.addEventListener("click", (ev) => {
    if (ev.target === modal) void closeReader();
  });

  function aiContextPayload() {
    if (activeFormat === "epub" && activeRendition) {
      const loc = activeRendition.currentLocation();
      const start = loc && loc.start;
      const payload = { format: "epub" };
      if (start && typeof start.index === "number") payload.spine_index = start.index;
      if (start && start.href) payload.href = start.href;
      return payload;
    }
    if (activeFormat === "txt") {
      const pre = bodyEl.querySelector(".bp-reader-txt");
      if (!pre) return { format: "txt", offset: 0 };
      const len = activeTxtLength || pre.textContent.length;
      const max = pre.scrollHeight - pre.clientHeight;
      const ratio = max > 0 ? pre.scrollTop / max : 0;
      return { format: "txt", offset: Math.floor(ratio * len) };
    }
    return null;
  }

  function setStudyBusy(on) {
    studyBusy = on;
    if (studySummarize) studySummarize.disabled = on;
    if (studyAskBtn) studyAskBtn.disabled = on;
    if (studyQuestion) studyQuestion.disabled = on;
  }

  async function fetchReaderAiStatus(itemId, authHeader) {
    const res = await fetch(
      "/api/library/" + encodeURIComponent(itemId) + "/ai/status",
      { headers: authHeaders(authHeader) }
    );
    if (!res.ok) return { ready: false };
    return res.json();
  }

  async function postReaderAi(pathSuffix, authHeader, body) {
    const ctx = aiContextPayload();
    if (!ctx) throw new Error("Study works for EPUB and TXT only");
    const res = await fetch(
      "/api/library/" + encodeURIComponent(activeItemId) + pathSuffix,
      {
        method: "POST",
        headers: { ...authHeaders(authHeader), "Content-Type": "application/json" },
        body: JSON.stringify({ ...ctx, ...body }),
      }
    );
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || res.statusText || "Request failed");
    return data;
  }

  async function runSummarize(authHeader) {
    if (studyBusy || !activeItemId) return;
    setStudyBusy(true);
    if (studyStatus) studyStatus.textContent = "Loading model / summarizing (may take 1–2 min on first use)…";
    try {
      const data = await postReaderAi("/ai/summarize", authHeader, {});
      if (studySummary) {
        studySummary.textContent = data.summary || "";
        studySummary.classList.remove("hidden");
      }
      if (studyStatus) {
        studyStatus.textContent = data.cached ? "Loaded cached summary." : "Summary ready.";
      }
    } catch (err) {
      if (studyStatus) studyStatus.textContent = err.message || String(err);
    } finally {
      setStudyBusy(false);
    }
  }

  async function runAsk(authHeader) {
    if (studyBusy || !activeItemId || !studyQuestion) return;
    const q = studyQuestion.value.trim();
    if (!q) return;
    setStudyBusy(true);
    if (studyStatus) studyStatus.textContent = "Loading model / thinking…";
    try {
      const data = await postReaderAi("/ai/ask", authHeader, {
        question: q,
        history: studyHistory.slice(-4),
      });
      const answer = data.answer || "";
      if (studyAnswer) {
        studyAnswer.textContent = answer;
        studyAnswer.classList.remove("hidden");
      }
      studyHistory.push({ role: "user", content: q });
      studyHistory.push({ role: "assistant", content: answer });
      studyQuestion.value = "";
      if (studyStatus) studyStatus.textContent = data.cached ? "Cached answer." : "Answer ready.";
    } catch (err) {
      if (studyStatus) studyStatus.textContent = err.message || String(err);
    } finally {
      setStudyBusy(false);
    }
  }

  function exportStudyNotes() {
    const title = titleEl?.textContent || "Study notes";
    const lines = ["# " + title, ""];
    const sum = studySummary?.textContent?.trim();
    if (sum) {
      lines.push("## Summary", "", sum, "");
    }
    if (studyHistory.length) {
      lines.push("## Q&A", "");
      studyHistory.forEach((turn) => {
        const who = turn.role === "assistant" ? "BookPup" : "You";
        lines.push("**" + who + ":** " + (turn.content || ""), "");
      });
    }
    if (sum) {
      const words = new Set();
      sum.split(/\s+/).forEach((w) => {
        const c = w.replace(/[^a-zA-Z'-]/g, "");
        if (c.length >= 8) words.add(c);
      });
      if (words.size) {
        lines.push("## Longer words (vocab skim)", "", [...words].sort().join(", "), "");
      }
    }
    if (lines.length <= 2) {
      if (studyStatus) studyStatus.textContent = "Nothing to export yet — summarize or ask first.";
      return;
    }
    const md = lines.join("\n");
    navigator.clipboard
      .writeText(md)
      .then(() => {
        if (studyStatus) studyStatus.textContent = "Study notes copied to clipboard.";
      })
      .catch(() => {
        if (studyStatus) studyStatus.textContent = "Could not copy — select text manually.";
      });
  }

  document.getElementById("reader-study-export")?.addEventListener("click", exportStudyNotes);

  if (studyToggle && studyPanel) {
    studyToggle.addEventListener("click", () => {
      const open = studyPanel.classList.toggle("hidden");
      studyToggle.setAttribute("aria-expanded", open ? "false" : "true");
    });
  }
  if (studySummarize) {
    studySummarize.addEventListener("click", () => runSummarize(activeAuthHeader));
  }
  if (studyAskBtn) {
    studyAskBtn.addEventListener("click", () => runAsk(activeAuthHeader));
  }
  if (studyQuestion) {
    studyQuestion.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") {
        ev.preventDefault();
        runAsk(activeAuthHeader);
      }
    });
  }

  function withTimeout(promise, ms, label) {
    return Promise.race([
      promise,
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error(label + " timed out after " + ms / 1000 + "s")), ms)
      ),
    ]);
  }

  function fetchHeaders(authHeader) {
    return {
      ...(authHeader ? { Authorization: authHeader } : {}),
      Accept: "application/epub+zip,application/pdf,text/plain,*/*",
    };
  }

  async function fetchReadBlob(readUrl, authHeader) {
    const res = await fetch(readUrl, { headers: fetchHeaders(authHeader) });
    if (!res.ok) {
      const hint = await res.text().catch(() => "");
      throw new Error((res.statusText || "Could not load book") + (hint ? ": " + hint.slice(0, 120) : ""));
    }
    const blob = await res.blob();
    if (blob.size < 16) throw new Error("Downloaded file is empty");
    return blob;
  }

  async function readerBodyHeight() {
    await new Promise((r) => requestAnimationFrame(r));
    await new Promise((r) => requestAnimationFrame(r));
    let h = bodyEl.clientHeight;
    if (h < 200) {
      const modalBox = modal.getBoundingClientRect();
      let used = modal.querySelector(".bp-reader-head")?.offsetHeight || 0;
      used += msgEl.offsetHeight || 0;
      if (!epubNav.classList.contains("hidden")) {
        used += epubNav.offsetHeight || 0;
      }
      used += 28;
      h = Math.floor(modalBox.height - used);
    }
    return Math.max(320, h);
  }

  function bindReaderResize(host, layoutHRef) {
    let t = 0;
    const ro = new ResizeObserver(() => {
      clearTimeout(t);
      t = setTimeout(() => {
        const next = Math.max(320, bodyEl.clientHeight);
        if (Math.abs(next - layoutHRef.value) < 20) return;
        layoutHRef.value = next;
        epubLayoutH = next;
        host.style.height = next + "px";
        if (activeRendition) activeRendition.resize("100%", next);
      }, 120);
    });
    ro.observe(bodyEl);
    return () => {
      clearTimeout(t);
      ro.disconnect();
    };
  }

  function epubFlow() {
    return "paginated";
  }

  function setProgress(ratio) {
    if (!progressFill || !progressLabel) return;
    const pct = Math.max(0, Math.min(100, Math.round(ratio * 100)));
    progressFill.style.width = pct + "%";
    progressLabel.textContent = pct + "%";
  }

  function epubIframe() {
    return epubHost ? epubHost.querySelector("iframe") : null;
  }

  const SCROLL_MIN = 48;

  function scrollTargetCandidates() {
    const list = [];
    if (epubHost) {
      const inner = epubHost.querySelector(".epub-container");
      if (inner) list.push(inner);
      list.push(epubHost);
    }
    if (bodyEl.classList.contains("bp-reader-body--scroll")) list.push(bodyEl);
    const ifr = epubIframe();
    const doc = ifr?.contentDocument;
    if (doc) {
      list.push(doc.scrollingElement, doc.documentElement, doc.body);
    }
    return list.filter(Boolean);
  }

  function activeScrollTarget() {
    let best = null;
    for (const el of scrollTargetCandidates()) {
      const max = el.scrollHeight - el.clientHeight;
      if (max < SCROLL_MIN) continue;
      const top = el.scrollTop;
      if (!best || max > best.max) best = { el, max, top };
    }
    return best;
  }

  function refreshScrollProgress() {
    const t = activeScrollTarget();
    if (!t) {
      setProgress(0);
      return;
    }
    setProgress(t.top / t.max);
  }

  function scrollEpubStep(dir) {
    const t = activeScrollTarget();
    if (!t?.el) return;
    const step = Math.max(240, Math.floor(epubLayoutH * 0.88)) * dir;
    const next = Math.max(0, Math.min(t.max, t.top + step));
    t.el.scrollTop = next;

    const ifr = epubIframe();
    const win = ifr?.contentWindow;
    if (win && Math.abs(t.el.scrollTop - next) < 2) {
      const root = win.document.scrollingElement || win.document.documentElement;
      if (root && root.scrollHeight - root.clientHeight >= SCROLL_MIN) {
        const winNext = Math.max(0, Math.min(root.scrollHeight - root.clientHeight, root.scrollTop + step));
        win.scrollTo(0, winNext);
      }
    }

    refreshScrollProgress();
  }

  function bindEpubProgress(flow) {
    if (flow === "scrolled") {
      const offs = [];
      const onAnyScroll = () => {
        refreshScrollProgress();
        scheduleSaveReading(activeAuthHeader);
      };
      const attach = (el) => {
        if (!el || el._bpScrollBound) return;
        el.addEventListener("scroll", onAnyScroll, { passive: true });
        el._bpScrollBound = true;
        offs.push(() => el.removeEventListener("scroll", onAnyScroll));
      };
      const wire = () => {
        if (epubHost) attach(epubHost);
        attach(bodyEl);
        const win = epubIframe()?.contentWindow;
        if (win) {
          win.addEventListener("scroll", onAnyScroll, { passive: true });
          offs.push(() => win.removeEventListener("scroll", onAnyScroll));
        }
        refreshScrollProgress();
      };
      wire();
      const poll = setInterval(wire, 400);
      return () => {
        clearInterval(poll);
        offs.forEach((fn) => fn());
      };
    }

    const onRelocated = (loc) => {
      const p = loc?.start?.percentage;
      if (typeof p === "number") setProgress(p);
      scheduleSaveReading(activeAuthHeader);
    };
    activeRendition.on("relocated", onRelocated);
    activeBook.locations
      .generate(1200)
      .then(() => {
        const loc = activeRendition.currentLocation();
        if (loc?.start?.percentage != null) setProgress(loc.start.percentage);
      })
      .catch(() => {});

    return () => {
      try {
        activeRendition.off("relocated", onRelocated);
      } catch (_e) {}
    };
  }

  function goEpubPrev() {
    if (!activeRendition) return;
    if (epubScrolled) scrollEpubStep(-1);
    else activeRendition.prev();
  }

  function goEpubNext() {
    if (!activeRendition) return;
    if (epubScrolled) scrollEpubStep(1);
    else activeRendition.next();
  }

  function updateSpreadButton() {
    if (!spreadBtn) return;
    const dual = epubSpread === "always";
    spreadBtn.textContent = dual ? "Single page" : "Dual page";
    spreadBtn.setAttribute("aria-pressed", dual ? "true" : "false");
    spreadBtn.classList.toggle("bp-btn--active", dual);
    spreadBtn.disabled = epubScrolled || !activeRendition;
    spreadBtn.classList.toggle("hidden", epubScrolled);
  }

  async function setupReaderAi(meta, authHeader) {
    if (!meta?.id || (meta.format !== "epub" && meta.format !== "txt")) return;
    const ai = await fetchReaderAiStatus(meta.id, authHeader);
    readerAiReady = !!ai.ready;
    if (studyStatus) {
      studyStatus.textContent = readerAiReady
        ? ""
        : "Study is not available on this server (admin: run install_reader_ai.sh).";
    }
    if (studySummarize) studySummarize.disabled = !readerAiReady;
    if (studyAskBtn) studyAskBtn.disabled = !readerAiReady;
  }

  function toggleDualPage() {
    if (epubScrolled || !activeRendition) return;
    epubSpread = epubSpread === "always" ? "none" : "always";
    localStorage.setItem("bookpupEpubSpread", epubSpread);
    try {
      activeRendition.spread(epubSpread);
    } catch (_e) {
      /* older epub.js */
    }
    try {
      activeRendition.resize("100%", epubLayoutH);
    } catch (_e) {}
    updateSpreadButton();
  }

  async function openReader(meta, authHeader) {
    cleanup();
    activeOffline = !!meta.offline;
    activeAuthHeader = authHeader;
    activeItemId = meta.id || null;
    activeSharedOwner = meta.owner || null;
    activeFormat = meta.format;
    if (activeItemId) {
      readingState = await fetchReading(activeItemId, authHeader);
    }
    const startLoc = readingState && readingState.location;
    if (bookmarkBtn) bookmarkBtn.onclick = () => void addBookmark(authHeader);
    renderBookmarks(authHeader);

    modal.classList.remove("hidden");
    document.body.classList.add("bp-reader-open");
    titleEl.textContent = meta.title || "Reader";
    const fmt = meta.format;
    if (studyToggle) {
      studyToggle.classList.toggle("hidden", fmt !== "epub" && fmt !== "txt");
    }

    try {
      if (fmt === "pdf") {
        msgEl.textContent = "Loading PDF…";
        const blob = await fetchReadBlob(meta.read_url, authHeader);
        activeBlobUrl = URL.createObjectURL(blob);
        const iframe = document.createElement("iframe");
        iframe.className = "bp-reader-pdf";
        iframe.title = "PDF viewer";
        const page = startLoc?.type === "pdf" && startLoc.page ? startLoc.page : 1;
        iframe.src = activeBlobUrl + "#page=" + page;
        bodyEl.appendChild(iframe);
        msgEl.textContent = "";
        return;
      }

      if (fmt === "txt") {
        msgEl.textContent = "Loading text…";
        const res = await fetch(meta.read_url, { headers: fetchHeaders(authHeader) });
        if (!res.ok) throw new Error(res.statusText || "Could not load text");
        const text = await res.text();
        activeTxtLength = text.length;
        const pre = document.createElement("pre");
        pre.className = "bp-reader-txt";
        pre.textContent = text;
        bodyEl.classList.add("bp-reader-body--scroll");
        bodyEl.appendChild(pre);
        pre.addEventListener("scroll", () => scheduleSaveReading(authHeader), { passive: true });
        if (startLoc?.type === "txt" && typeof startLoc.scroll === "number") {
          requestAnimationFrame(() => applyScrollRatio(pre, startLoc.scroll));
        }
        msgEl.textContent = "";
        await setupReaderAi(meta, authHeader);
        return;
      }

      if (fmt === "md") {
        msgEl.textContent = "Loading markdown…";
        const res = await fetch(meta.read_url, { headers: fetchHeaders(authHeader) });
        if (!res.ok) throw new Error(res.statusText || "Could not load markdown");
        const text = await res.text();
        activeTxtLength = text.length;
        const article = document.createElement("article");
        article.className = "bp-reader-md";
        article.innerHTML = markdownToHtml(text);
        bodyEl.classList.add("bp-reader-body--scroll");
        bodyEl.appendChild(article);
        article.addEventListener("scroll", () => scheduleSaveReading(authHeader), { passive: true });
        if (startLoc?.type === "md" && typeof startLoc.scroll === "number") {
          requestAnimationFrame(() => applyScrollRatio(article, startLoc.scroll));
        }
        msgEl.textContent = "";
        return;
      }

      if (fmt === "html") {
        msgEl.textContent = "Loading HTML…";
        const res = await fetch(meta.read_url, { headers: fetchHeaders(authHeader) });
        if (!res.ok) throw new Error(res.statusText || "Could not load HTML");
        let html = stripUnsafeHtml(await res.text());
        if (!/<\s*html[\s>]/i.test(html)) {
          html =
            '<!DOCTYPE html><html><head><meta charset="utf-8">' +
            '<meta name="viewport" content="width=device-width,initial-scale=1">' +
            '<style>body{font-family:system-ui,sans-serif;margin:1rem;line-height:1.5;}</style></head><body>' +
            html +
            "</body></html>";
        }
        const iframe = document.createElement("iframe");
        iframe.className = "bp-reader-html-frame";
        iframe.title = "HTML document";
        iframe.sandbox = "";
        iframe.srcdoc = html;
        bodyEl.classList.add("bp-reader-body--scroll");
        bodyEl.appendChild(iframe);
        const onHtmlScroll = () => scheduleSaveReading(authHeader);
        iframe.addEventListener("load", () => {
          const doc = iframe.contentDocument;
          if (doc) doc.addEventListener("scroll", onHtmlScroll, { passive: true });
          if (startLoc?.type === "html" && typeof startLoc.scroll === "number") {
            applyScrollRatio(iframe, startLoc.scroll);
          }
        });
        msgEl.textContent = "";
        return;
      }

      if (fmt === "epub") {
        const ePubFactory = typeof ePub !== "undefined" ? ePub : globalThis.ePub;
        if (!ePubFactory) {
          throw new Error("EPUB viewer failed to load (epub.js)");
        }
        if (typeof JSZip === "undefined") {
          throw new Error("EPUB viewer failed to load (JSZip)");
        }
        msgEl.textContent = meta.converted ? "Converting / loading EPUB…" : "Loading EPUB…";

        const blob = await fetchReadBlob(meta.read_url, authHeader);
        const buffer = await blob.arrayBuffer();
        activeBlobUrl = URL.createObjectURL(blob);

        const flow = epubFlow(meta);
        epubScrolled = flow === "scrolled";
        const host = document.createElement("div");
        host.id = "epub-host";
        host.className =
          "bp-reader-epub-host" + (flow === "scrolled" ? " bp-reader-epub-host--scroll" : "");
        bodyEl.classList.toggle("bp-reader-body--scroll", flow === "scrolled");
        bodyEl.appendChild(host);
        epubHost = host;

        const layoutH = { value: await readerBodyHeight() };
        epubLayoutH = layoutH.value;
        host.style.height = layoutH.value + "px";

        msgEl.textContent = "Opening book…";
        activeBook = ePubFactory(buffer);
        await withTimeout(activeBook.ready, 120000, "EPUB open");

        msgEl.textContent = "Rendering…";
        const spread = epubScrolled ? "none" : epubSpread;
        activeRendition = activeBook.renderTo(host, {
          width: "100%",
          height: layoutH.value,
          spread: spread,
          flow: flow,
        });
        activeRendition.themes.default({
          body: { color: "#1a1a1a", background: "#fff" },
          p: { color: "#1a1a1a" },
        });

        let cfi = undefined;
        if (startLoc?.type === "epub" && startLoc.cfi) {
          if (flow === "paginated" || meta.converted) {
            cfi = startLoc.cfi;
          }
        }
        await withTimeout(activeRendition.display(cfi), 60000, "EPUB render");
        if (startLoc?.type === "epub" && flow === "scrolled") {
          const ratio =
            typeof startLoc.scroll === "number"
              ? startLoc.scroll
              : typeof startLoc.percentage === "number"
                ? startLoc.percentage
                : null;
          if (ratio != null) {
            setTimeout(() => restoreScrollRatio(ratio), startLoc.cfi ? 850 : 500);
          }
        }

        epubNav.classList.remove("hidden");
        stopResize = bindReaderResize(host, layoutH);
        stopProgress = bindEpubProgress(flow);

        prevBtn.onclick = goEpubPrev;
        nextBtn.onclick = goEpubNext;
        if (spreadBtn) spreadBtn.onclick = toggleDualPage;
        updateSpreadButton();
        keyHandler = (ev) => {
          if (modal.classList.contains("hidden") || fmt !== "epub") return;
          if (ev.key === "ArrowLeft" || ev.key === "PageUp") {
            ev.preventDefault();
            goEpubPrev();
          } else if (ev.key === "ArrowRight" || ev.key === "PageDown") {
            ev.preventDefault();
            goEpubNext();
          }
        };
        modal.addEventListener("keydown", keyHandler);

        msgEl.textContent = "";
        await setupReaderAi(meta, authHeader);
        return;
      }

      if (COMIC_FMTS.has(fmt)) {
        msgEl.textContent = "Loading comic…";
        const metaUrl =
          meta.comic_meta_url || "/api/library/" + encodeURIComponent(meta.id) + "/comic/meta";
        const metaRes = await fetch(metaUrl, { headers: fetchHeaders(authHeader) });
        const comicMeta = await metaRes.json();
        if (!metaRes.ok) {
          const err = new Error(comicMeta.error || "Couldn't load comic");
          err.debugStderr = comicMeta.debug_stderr || "";
          throw err;
        }
        comicPageCount = comicMeta.pages || 0;
        if (!comicPageCount) throw new Error("No images in this comic");
        comicPage =
          startLoc?.type === fmt && typeof startLoc.page === "number" ? startLoc.page : 0;
        let comicDual = localStorage.getItem("bookpupComicDual") === "1";
        comicPage = Math.max(0, Math.min(comicPage, comicPageCount - 1));
        if (comicDual) comicPage -= comicPage % 2;
        const COMIC_ZOOM_MIN = 0.25;
        const COMIC_ZOOM_MAX = 5;
        const paneView = [
          { zoom: 1, panX: 0, panY: 0 },
          { zoom: 1, panX: 0, panY: 0 },
        ];
        const paneEls = [];
        const paneImgs = [];
        let activePane = 0;
        let pinchDist0 = 0;
        let pinchZoom0 = 1;
        let pinchPaneIx = 0;
        let comicDrag = null;

        function paneTransform(pv) {
          if (pv.zoom === 1 && pv.panX === 0 && pv.panY === 0) return "";
          return (
            "translate(" + pv.panX + "px," + pv.panY + "px) scale(" + pv.zoom + ")"
          );
        }
        function resetPaneView(ix) {
          paneView[ix].panX = 0;
          paneView[ix].panY = 0;
        }
        function resetAllPaneViews() {
          resetPaneView(0);
          resetPaneView(1);
        }
        function paneFromTarget(t) {
          const pane = t && t.closest && t.closest(".bp-reader-comic-pane");
          if (!pane) return activePane;
          const ix = Number(pane.dataset.pane);
          return Number.isFinite(ix) ? ix : activePane;
        }
        function applyPaneTransform(ix) {
          paneEls[ix].style.transform = paneTransform(paneView[ix]);
        }
        function endComicDrag() {
          comicDrag = null;
          viewport.classList.remove("bp-reader-comic-viewport--dragging");
          document.removeEventListener("mousemove", onComicDragMove);
          document.removeEventListener("mouseup", endComicDrag);
          document.removeEventListener("touchmove", onComicDragMove);
          document.removeEventListener("touchend", endComicDrag);
          document.removeEventListener("touchcancel", endComicDrag);
        }
        function onComicDragMove(ev) {
          if (!comicDrag) return;
          if (ev.type === "touchmove" && ev.touches.length !== 1) return;
          ev.preventDefault();
          const cx =
            ev.touches && ev.touches.length ? ev.touches[0].clientX : ev.clientX;
          const cy =
            ev.touches && ev.touches.length ? ev.touches[0].clientY : ev.clientY;
          const pv = paneView[comicDrag.paneIx];
          pv.panX = comicDrag.panX0 + (cx - comicDrag.x);
          pv.panY = comicDrag.panY0 + (cy - comicDrag.y);
          applyPaneTransform(comicDrag.paneIx);
        }
        function beginComicDrag(clientX, clientY, target) {
          const ix = paneFromTarget(target);
          activePane = ix;
          const pv = paneView[ix];
          comicDrag = {
            x: clientX,
            y: clientY,
            panX0: pv.panX,
            panY0: pv.panY,
            paneIx: ix,
          };
          viewport.classList.add("bp-reader-comic-viewport--dragging");
          document.addEventListener("mousemove", onComicDragMove);
          document.addEventListener("mouseup", endComicDrag);
          document.addEventListener("touchmove", onComicDragMove, { passive: false });
          document.addEventListener("touchend", endComicDrag);
          document.addEventListener("touchcancel", endComicDrag);
        }
        bodyEl.classList.add("bp-reader-body--comic");
        const wrap = document.createElement("div");
        wrap.className = "bp-reader-comic";
        const viewport = document.createElement("div");
        viewport.className = "bp-reader-comic-viewport";
        viewport.tabIndex = 0;
        const stage = document.createElement("div");
        stage.className = "bp-reader-comic-stage";
        function makeComicPane(ix) {
          const pane = document.createElement("div");
          pane.className = "bp-reader-comic-pane";
          pane.dataset.pane = String(ix);
          if (ix === 1) pane.classList.add("bp-reader-comic-pane--page2");
          const im = document.createElement("img");
          im.alt = "";
          pane.appendChild(im);
          paneEls[ix] = pane;
          paneImgs[ix] = im;
          stage.appendChild(pane);
        }
        makeComicPane(0);
        makeComicPane(1);
        const img = paneImgs[0];
        const img2 = paneImgs[1];
        viewport.appendChild(stage);

        const toolbar = document.createElement("div");
        toolbar.className = "bp-reader-comic-toolbar";
        const zoomOut = document.createElement("button");
        zoomOut.type = "button";
        zoomOut.className = "bp-btn";
        zoomOut.textContent = "−";
        zoomOut.setAttribute("aria-label", "Zoom out");
        const zoomPct = document.createElement("span");
        zoomPct.className = "bp-msg muted bp-reader-comic-zoom-pct";
        const zoomFit = document.createElement("button");
        zoomFit.type = "button";
        zoomFit.className = "bp-btn bp-btn--ghost";
        zoomFit.textContent = "Fit";
        zoomFit.setAttribute("aria-label", "Reset zoom");
        const zoomIn = document.createElement("button");
        zoomIn.type = "button";
        zoomIn.className = "bp-btn";
        zoomIn.textContent = "+";
        zoomIn.setAttribute("aria-label", "Zoom in");

        function applyComicZoom() {
          applyPaneTransform(0);
          applyPaneTransform(1);
          const zoomed = paneView[0].zoom > 1.001 || paneView[1].zoom > 1.001;
          viewport.classList.toggle("bp-reader-comic-viewport--zoomed", zoomed);
          stage.classList.toggle("bp-reader-comic-stage--zoomed", zoomed);
          const apv = paneView[activePane];
          zoomOut.disabled = apv.zoom <= COMIC_ZOOM_MIN + 0.001;
          zoomIn.disabled = apv.zoom >= COMIC_ZOOM_MAX - 0.001;
          zoomPct.textContent = Math.round(apv.zoom * 100) + "%";
        }
        function updateComicSpreadUi() {
          const dual = comicDual;
          const label = dual ? "Single page" : "Dual page";
          if (spreadBtn) {
            spreadBtn.classList.remove("hidden");
            spreadBtn.textContent = label;
            spreadBtn.setAttribute("aria-pressed", dual ? "true" : "false");
            spreadBtn.classList.toggle("bp-btn--active", dual);
            spreadBtn.disabled = false;
          }
        }
        function toggleComicDual() {
          comicDual = !comicDual;
          localStorage.setItem("bookpupComicDual", comicDual ? "1" : "0");
          if (comicDual) comicPage -= comicPage % 2;
          updateComicSpreadUi();
          void showPage();
        }
        function setPaneZoom(ix, next) {
          const pv = paneView[ix];
          pv.zoom = Math.min(COMIC_ZOOM_MAX, Math.max(COMIC_ZOOM_MIN, next));
          if (pv.zoom <= 1.001) resetPaneView(ix);
          activePane = ix;
          applyComicZoom();
        }
        function resetComicFit() {
          paneView[0].zoom = 1;
          paneView[1].zoom = 1;
          resetAllPaneViews();
          applyComicZoom();
        }
        zoomOut.addEventListener("click", () => setPaneZoom(activePane, paneView[activePane].zoom / 1.25));
        zoomIn.addEventListener("click", () => setPaneZoom(activePane, paneView[activePane].zoom * 1.25));
        zoomFit.addEventListener("click", () => resetComicFit());
        viewport.addEventListener("mousedown", (ev) => {
          if (ev.button !== 0) return;
          beginComicDrag(ev.clientX, ev.clientY, ev.target);
          ev.preventDefault();
        });
        viewport.addEventListener(
          "wheel",
          (ev) => {
            ev.preventDefault();
            const ix = paneFromTarget(ev.target);
            activePane = ix;
            const factor = ev.deltaY < 0 ? 1.1 : 1 / 1.1;
            setPaneZoom(ix, paneView[ix].zoom * factor);
          },
          { passive: false }
        );
        viewport.addEventListener(
          "touchstart",
          (ev) => {
            if (ev.touches.length === 2) {
              if (comicDrag) endComicDrag();
              const a = ev.touches[0];
              const b = ev.touches[1];
              pinchDist0 = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
              const cx = (a.clientX + b.clientX) / 2;
              const cy = (a.clientY + b.clientY) / 2;
              pinchPaneIx = paneFromTarget(document.elementFromPoint(cx, cy));
              activePane = pinchPaneIx;
              pinchZoom0 = paneView[pinchPaneIx].zoom;
            } else if (ev.touches.length === 1) {
              beginComicDrag(ev.touches[0].clientX, ev.touches[0].clientY, ev.target);
            }
          },
          { passive: true }
        );
        viewport.addEventListener(
          "touchmove",
          (ev) => {
            if (ev.touches.length !== 2 || !pinchDist0) return;
            ev.preventDefault();
            const a = ev.touches[0];
            const b = ev.touches[1];
            const dist = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
            setPaneZoom(pinchPaneIx, pinchZoom0 * (dist / pinchDist0));
          },
          { passive: false }
        );
        viewport.addEventListener(
          "touchend",
          (ev) => {
            if (ev.touches.length < 2) pinchDist0 = 0;
          },
          { passive: true }
        );
        toolbar.appendChild(zoomOut);
        toolbar.appendChild(zoomPct);
        toolbar.appendChild(zoomFit);
        toolbar.appendChild(zoomIn);

        const label = document.createElement("span");
        label.className = "bp-msg muted";
        const nav = document.createElement("div");
        nav.className = "bp-reader-comic-nav";
        const prev = document.createElement("button");
        prev.type = "button";
        prev.className = "bp-btn";
        prev.textContent = "Previous";
        const next = document.createElement("button");
        next.type = "button";
        next.className = "bp-btn";
        next.textContent = "Next";
        async function fetchComicPageBlob(ix) {
          const url =
            "/api/library/" +
            encodeURIComponent(meta.id) +
            "/comic/page/" +
            ix +
            catalogOwnerQuery();
          const res = await fetch(url, { headers: fetchHeaders(authHeader) });
          if (!res.ok) {
            let errMsg = "Could not load page";
            let dbg = "";
            try {
              const j = await res.json();
              errMsg = j.error || errMsg;
              dbg = j.debug_stderr || "";
            } catch (_e) {
              /* non-JSON body */
            }
            const err = new Error(errMsg);
            err.debugStderr = dbg;
            throw err;
          }
          return URL.createObjectURL(await res.blob());
        }
        function setComicImg(el, blobUrl) {
          if (el.dataset.blob) URL.revokeObjectURL(el.dataset.blob);
          el.dataset.blob = blobUrl;
          el.src = blobUrl;
        }
        function updateComicNav() {
          prev.disabled = comicPage <= 0;
          if (comicDual) {
            next.disabled = comicPage + 1 >= comicPageCount;
          } else {
            next.disabled = comicPage >= comicPageCount - 1;
          }
        }
        async function showPage() {
          const secondIx = comicDual && comicPage + 1 < comicPageCount ? comicPage + 1 : -1;
          const primaryUrl = await fetchComicPageBlob(comicPage);
          setComicImg(img, primaryUrl);
          if (secondIx >= 0) {
            const secondUrl = await fetchComicPageBlob(secondIx);
            setComicImg(img2, secondUrl);
            stage.classList.add("bp-reader-comic-stage--dual");
            label.textContent =
              "Pages " +
              (comicPage + 1) +
              "–" +
              (secondIx + 1) +
              " / " +
              comicPageCount;
          } else {
            if (img2.dataset.blob) {
              URL.revokeObjectURL(img2.dataset.blob);
              delete img2.dataset.blob;
            }
            img2.removeAttribute("src");
            stage.classList.remove("bp-reader-comic-stage--dual");
            label.textContent = "Page " + (comicPage + 1) + " / " + comicPageCount;
          }
          resetComicFit();
          updateComicNav();
          scheduleSaveReading(authHeader);
        }
        prev.addEventListener("click", () => {
          if (comicPage <= 0) return;
          comicPage -= comicDual ? 2 : 1;
          if (comicPage < 0) comicPage = 0;
          void showPage();
        });
        next.addEventListener("click", () => {
          if (comicDual) {
            if (comicPage + 2 < comicPageCount) comicPage += 2;
            else if (comicPage < comicPageCount - 1) comicPage = comicPageCount - 1;
            else return;
          } else if (comicPage < comicPageCount - 1) {
            comicPage++;
          } else {
            return;
          }
          void showPage();
        });
        nav.appendChild(prev);
        nav.appendChild(label);
        nav.appendChild(next);
        wrap.appendChild(viewport);
        wrap.appendChild(toolbar);
        wrap.appendChild(nav);
        applyComicZoom();
        bodyEl.appendChild(wrap);
        epubNav.classList.remove("hidden");
        epubNav.classList.add("bp-reader-epub-nav--comic");
        if (prevBtn) prevBtn.classList.add("hidden");
        if (nextBtn) nextBtn.classList.add("hidden");
        if (spreadBtn) spreadBtn.onclick = toggleComicDual;
        updateComicSpreadUi();
        await showPage();
        msgEl.textContent = "";
        return;
      }

      throw new Error("Unsupported format: " + fmt);
    } catch (err) {
      const dbg = err && err.debugStderr ? err.debugStderr : "";
      fail(err && err.message ? err.message : String(err), dbg);
    }
  }

  window.BookPupReader = { open: openReader, close: closeReader };
})();