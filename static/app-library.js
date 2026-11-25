(function (BP) {
  "use strict";
  const CSRF = BP.CSRF;
  const COVER_MAX_BYTES = BP.COVER_MAX_BYTES;
  const LIB_VIEW_KEY = "bookpupLibraryView";
  const LIB_LAYOUT_KEY = "bookpupLibraryLayout";
  const LIB_GROUP_KEY = "bookpupLibraryGroup";
  const LIB_SORT_KEY = "bookpupLibrarySort";
  const LIB_SHELF_KEY = "bookpupLibraryShelf";
  const LIB_PROGRESS_KEY = "bookpupLibraryInProgress";
  const coverBlobUrls = new Map();
  let libraryItemsCache = [];
  let libraryBrowseOwner = "";
  let libraryBrowseMode = null;
  let librarySharesData = { incoming: [], outgoing: [], browsing: [] };
  let ownLibraryQuota = { used_bytes: 0, quota_bytes: 1 };
  let offlineIdSet = new Set();
  let libOfflineOnly = false;
  let libInProgressOnly = localStorage.getItem(LIB_PROGRESS_KEY) === "1";
  let pendingLibraryFocus = null;
  let libraryShelvesCache = [];
  let activeShelfId = "";
  let shelfNameModalMode = "create";
  const LIBRARY_READABLE_FALLBACK = new Set([
    "epub",
    "pdf",
    "txt",
    "md",
    "html",
    "mobi",
    "azw3",
    "azw",
    "prc",
    "fb2",
    "lit",
    "chm",
    "rtf",
    "djvu",
    "cbz",
    "cbr",
    "cb7",
  ]);
  let libraryReadableFormats = new Set(LIBRARY_READABLE_FALLBACK);
  const libFilterInput = document.getElementById("lib-filter");

  function libOwnerQuery() {
    return libraryBrowseOwner ? "?owner=" + encodeURIComponent(libraryBrowseOwner) : "";
  }

  function isSharedBrowse() {
    return !!libraryBrowseOwner;
  }

  function migrateLibraryViewPrefs() {
    const legacy = localStorage.getItem(LIB_VIEW_KEY);
    if (!legacy) return;
    if (legacy === "series") {
      localStorage.setItem(LIB_GROUP_KEY, "series");
      if (!localStorage.getItem(LIB_LAYOUT_KEY)) localStorage.setItem(LIB_LAYOUT_KEY, "grid");
    } else if (legacy === "list" || legacy === "grid") {
      localStorage.setItem(LIB_LAYOUT_KEY, legacy);
    }
    localStorage.removeItem(LIB_VIEW_KEY);
  }

  migrateLibraryViewPrefs();

  function libraryLayoutMode() {
    const m = localStorage.getItem(LIB_LAYOUT_KEY);
    if (m === "list") return "list";
    if (m === "flow") return "flow";
    return "grid";
  }

  function flowAvailable() {
    return libraryGroupMode() === "none";
  }

  function catalogueEffectiveLayout() {
    const layout = libraryLayoutMode();
    if (layout === "flow" && !flowAvailable()) return "grid";
    return layout;
  }

  function downloadsLayoutMode() {
    const m = libraryLayoutMode();
    return m === "list" ? "list" : "grid";
  }

  function libraryGroupMode() {
    const g = localStorage.getItem(LIB_GROUP_KEY);
    return g === "series" || g === "author" ? g : "none";
  }

  function librarySortMode() {
    const allowed = new Set([
      "saved_desc",
      "reading_desc",
      "title_asc",
      "title_desc",
      "author_asc",
      "series_asc",
      "size_desc",
    ]);
    const s = localStorage.getItem(LIB_SORT_KEY);
    return allowed.has(s) ? s : "saved_desc";
  }

  function sortLibraryItems(items) {
    const mode = librarySortMode();
    const out = items.slice();
    const titleKey = (it) => String(it.title || it.filename || "").toLowerCase();
    const authorKey = (it) => String(it.authors || "").toLowerCase();
    const seriesKey = (it) => String(it.series || "").toLowerCase();
    const seriesIdx = (it) => {
      const n = parseFloat(it.series_index);
      return Number.isNaN(n) ? Number.POSITIVE_INFINITY : n;
    };
    out.sort((a, b) => {
      if (mode === "title_desc") return titleKey(b).localeCompare(titleKey(a));
      if (mode === "title_asc") return titleKey(a).localeCompare(titleKey(b));
      if (mode === "author_asc") return authorKey(a).localeCompare(authorKey(b)) || titleKey(a).localeCompare(titleKey(b));
      if (mode === "series_asc") {
        const s = seriesKey(a).localeCompare(seriesKey(b));
        if (s) return s;
        const d = seriesIdx(a) - seriesIdx(b);
        if (d) return d;
        return titleKey(a).localeCompare(titleKey(b));
      }
      if (mode === "size_desc") return (b.bytes || 0) - (a.bytes || 0) || titleKey(a).localeCompare(titleKey(b));
      if (mode === "reading_desc") {
        const ra = a.reading?.updated_at || 0;
        const rb = b.reading?.updated_at || 0;
        if (rb !== ra) return rb - ra;
        return titleKey(a).localeCompare(titleKey(b));
      }
      return (b.saved_at || 0) - (a.saved_at || 0) || titleKey(a).localeCompare(titleKey(b));
    });
    return out;
  }

  function updateLibraryToolbar() {
    const layout = libraryLayoutMode();
    const gridBtn = document.getElementById("lib-view-grid");
    const listBtn = document.getElementById("lib-view-list");
    const flowBtn = document.getElementById("lib-view-flow");
    const groupSel = document.getElementById("lib-group-by");
    const sortSel = document.getElementById("lib-sort-by");
    const flowOk = flowAvailable();
    if (gridBtn) {
      gridBtn.classList.toggle("bp-btn--active", layout === "grid");
      gridBtn.setAttribute("aria-pressed", layout === "grid" ? "true" : "false");
    }
    if (listBtn) {
      listBtn.classList.toggle("bp-btn--active", layout === "list");
      listBtn.setAttribute("aria-pressed", layout === "list" ? "true" : "false");
    }
    if (flowBtn) {
      flowBtn.disabled = !flowOk;
      flowBtn.setAttribute("aria-disabled", flowOk ? "false" : "true");
      flowBtn.classList.toggle("bp-btn--active", layout === "flow" && flowOk);
      flowBtn.setAttribute("aria-pressed", layout === "flow" && flowOk ? "true" : "false");
      flowBtn.title = flowOk ? "" : "Flow is only available when Group by is None";
    }
    if (groupSel) groupSel.value = libraryGroupMode();
    if (sortSel) sortSel.value = librarySortMode();
  }

  function setLibraryLayoutMode(mode) {
    const next = mode === "list" ? "list" : mode === "flow" ? "flow" : "grid";
    localStorage.setItem(LIB_LAYOUT_KEY, next);
    updateLibraryToolbar();
    renderLibrary();
  }

  function setLibraryGroupMode(mode) {
    const next = mode === "series" || mode === "author" ? mode : "none";
    localStorage.setItem(LIB_GROUP_KEY, next);
    updateLibraryToolbar();
    renderLibrary();
  }

  function setLibrarySortMode(mode) {
    localStorage.setItem(LIB_SORT_KEY, mode || "saved_desc");
    updateLibraryToolbar();
    renderLibrary();
  }

  function seriesGapHint(seriesName, items) {
    const nums = items
      .map((it) => parseFloat(it.series_index))
      .filter((n) => !Number.isNaN(n))
      .map((n) => Math.floor(n));
    if (nums.length < 2) return "";
    const set = new Set(nums);
    const min = Math.min(...nums);
    const max = Math.max(...nums);
    const missing = [];
    for (let i = min; i <= max && missing.length < 10; i++) {
      if (!set.has(i)) missing.push(i);
    }
    if (!missing.length) return "";
    return "Missing in “" + seriesName + "”: #" + missing.join(", #");
  }

  function renderLibraryGroupBlock(container, groupName, items, readable, options) {
    const showSeriesGaps = options && options.seriesGaps;
    const block = document.createElement("section");
    block.className = "bp-lib-series-block";
    const h = document.createElement("h4");
    h.textContent = groupName;
    block.appendChild(h);
    if (showSeriesGaps) {
      const gap = seriesGapHint(groupName, items);
      if (gap) {
        const p = document.createElement("p");
        p.className = "bp-lib-series-gap";
        p.textContent = gap;
        block.appendChild(p);
      }
    }
    const sorted = sortLibraryItems(items);
    const layout = downloadsLayoutMode();
    const inner = document.createElement("div");
    inner.className = "bp-lib-items bp-lib-items--" + layout;
    if (layout === "list") {
      inner.appendChild(renderLibraryList(sorted, readable));
    } else {
      sorted.forEach((item) => inner.appendChild(renderLibraryCard(item, readable)));
    }
    block.appendChild(inner);
    container.appendChild(block);
  }

  function isStagedItem(item) {
    return (item.source || "download") === "download";
  }

  function isRegisteredItem(item) {
    const s = item.source || "";
    return s === "calibre_import" || s === "registered";
  }

  function librarySearchText(item) {
    const parts = [
      item.title,
      item.filename,
      item.authors,
      item.series,
      item.tags,
      item.publisher,
      item.pubdate,
      item.isbn,
      item.format,
      item.source,
    ];
    if (item.series_index != null && item.series_index !== "") {
      parts.push(String(item.series_index));
    }
    return parts
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .replace(/["']/g, "");
  }

  function fuzzyTokenMatch(haystack, token) {
    if (!token) return true;
    if (haystack.includes(token)) return true;
    let i = 0;
    for (let c = 0; c < haystack.length; c++) {
      if (haystack[c] === token[i]) {
        i++;
        if (i === token.length) return true;
      }
    }
    return false;
  }

  function libraryItemMatchesFilter(item, query) {
    const q = (query || "").trim().toLowerCase();
    if (!q) return true;
    const hay = librarySearchText(item);
    const tokens = q.split(/\s+/).filter(Boolean);
    return tokens.every((tok) => fuzzyTokenMatch(hay, tok));
  }

  function activeShelfItemSet() {
    const shelf = libraryShelvesCache.find((s) => s.id === activeShelfId);
    return new Set((shelf && shelf.item_ids) || []);
  }

  function filterLibraryItems(items) {
    let out = items;
    if (libOfflineOnly) out = out.filter((item) => offlineIdSet.has(item.id));
    if (libInProgressOnly) {
      out = out.filter(
        (item) => isRegisteredItem(item) && !!(item.reading && item.reading.in_progress)
      );
    }
    if (activeShelfId) {
      const ids = activeShelfItemSet();
      out = out.filter((item) => isRegisteredItem(item) && ids.has(item.id));
    }
    const q = libFilterInput ? libFilterInput.value : "";
    return out.filter((item) => libraryItemMatchesFilter(item, q));
  }

  function normalizeCatalogTitle(text) {
    return String(text || "")
      .toLowerCase()
      .replace(/['’"]/g, "")
      .replace(/[^\w\s]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function authorTokens(authors) {
    return normalizeCatalogTitle(authors)
      .split(" ")
      .filter((t) => t.length > 1);
  }

  function findCatalogDuplicates({ title, authors, excludeId }) {
    const nt = normalizeCatalogTitle(title);
    if (!nt) return [];
    const toks = authorTokens(authors);
    const hits = [];
    for (const item of libraryItemsCache) {
      if (!isRegisteredItem(item) || item.id === excludeId) continue;
      const it = normalizeCatalogTitle(item.title || item.filename);
      if (!it) continue;
      const exact = it === nt;
      const titleNear = it.includes(nt) || nt.includes(it);
      if (!exact && !titleNear) continue;
      if (!exact && toks.length) {
        const at = authorTokens(item.authors);
        if (at.length && !toks.some((t) => at.some((a) => a.includes(t) || t.includes(a)))) continue;
      }
      hits.push(item);
      if (hits.length >= 3) break;
    }
    return hits;
  }

  function libraryBookDeepLink(item, owner) {
    const own = owner != null ? owner : libraryBrowseOwner;
    let hash = "#library/book/" + encodeURIComponent(item.id);
    if (own) hash += "?owner=" + encodeURIComponent(own);
    return window.location.origin + window.location.pathname + hash;
  }

  async function copyTextToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch {
        /* fall through */
      }
    }
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    return ok;
  }

  async function copyLibraryLink(item) {
    const url = libraryBookDeepLink(item);
    const ok = await copyTextToClipboard(url);
    BP.showAppToast(
      "Kennel",
      ok ? "Link copied — opens this book in Kennel." : "Could not copy link.",
      ok ? "ok" : "err"
    );
  }

  function parseLibraryDeepLinkHash() {
    const raw = (window.location.hash || "").trim();
    const m = raw.match(/^#library\/book\/([^?/#]+)(?:\?(.*))?$/);
    if (!m) return null;
    let owner = "";
    if (m[2]) {
      const qs = new URLSearchParams(m[2]);
      owner = (qs.get("owner") || "").trim();
    }
    return { id: decodeURIComponent(m[1]), owner };
  }

  function parseLibraryDeepLinkFromUrl() {
    const hit = parseLibraryDeepLinkHash();
    if (!hit) return false;
    pendingLibraryFocus = hit;
    const base = window.location.pathname + window.location.search;
    window.history.replaceState(null, "", base);
    if (hit.owner) libraryBrowseOwner = hit.owner;
    return true;
  }

  function focusLibraryItem(itemId) {
    if (!itemId) return;
    const esc = typeof CSS !== "undefined" && CSS.escape ? CSS.escape(itemId) : itemId;
    const node =
      document.querySelector('.bp-lib-card[data-lib-item-id="' + esc + '"]') ||
      document.querySelector('tr[data-lib-item-id="' + esc + '"]') ||
      document.querySelector('.bp-lib-flow__spine[data-lib-item-id="' + esc + '"]');
    if (!node) return;
    node.scrollIntoView({ behavior: "smooth", block: "nearest" });
    const host = node.classList?.contains("bp-lib-card") ? node : node.closest(".bp-lib-card") || node;
    host.classList.add("bp-lib-card--link-target");
    window.setTimeout(() => host.classList.remove("bp-lib-card--link-target"), 2200);
  }

  function tryFocusPendingLibraryItem() {
    if (!pendingLibraryFocus?.id) return;
    const id = pendingLibraryFocus.id;
    pendingLibraryFocus = null;
    window.requestAnimationFrame(() => focusLibraryItem(id));
  }

  function surpriseMeRead() {
    if (BP.state.offlineOnly) {
      BP.showAppToast("Kennel", "Surprise me needs the server catalog.", "info");
      return;
    }
    const pool = filterLibraryItems(libraryItemsCache).filter((item) => {
      if (!isRegisteredItem(item)) return false;
      const fmt = (item.format || "").toLowerCase().replace(/["']/g, "").replace(/^\./, "");
      return libraryReadableFormats.has(fmt);
    });
    if (!pool.length) {
      BP.showAppToast("Kennel", "No readable catalogued books match your filter.", "info");
      return;
    }
    const pick = pool[Math.floor(Math.random() * pool.length)];
    openLibraryReader(pick);
  }

  function readingPillHtml(item) {
    const label = item.reading?.progress_label;
    if (!label || BP.state.offlineOnly) return "";
    return (
      '<span class="bp-lib-reading-pill" title="Reading progress">' +
      BP.escapeHtml(label) +
      "</span>"
    );
  }

  function deviceSendButton(item, shared) {
    if (shared || !isRegisteredItem(item)) return "";
    return '<button type="button" class="bp-btn device-send">Send to e-reader…</button> ';
  }

  function offlineActionButton(item, shared) {
    if (shared || !BP.offlineBooks?.canKeepOffline(item)) return "";
    if (offlineIdSet.has(item.id)) {
      return '<button type="button" class="bp-btn remove-offline">Remove offline copy</button> ';
    }
    return '<button type="button" class="bp-btn keep-offline">Keep offline</button> ';
  }

  async function keepOfflineCopy(item) {
    if (!BP.offlineBooks) return;
    try {
      BP.showAppToast("Offline", "Downloading for this device…", "info");
      await BP.offlineBooks.downloadBook(item, BP.state.authHeader);
      await refreshOfflineIds();
      renderLibrary();
      BP.showAppToast("Offline", "Kept on this device — readable without the server.", "ok");
    } catch (err) {
      BP.showAppToast("Offline", err.message || "Could not keep offline", "err");
    }
  }

  async function removeOfflineCopy(item) {
    if (!BP.offlineBooks) return;
    const label = item.title || item.filename || "this book";
    if (!window.confirm('Remove the offline copy of "' + label + '" from this device?')) return;
    try {
      await BP.offlineBooks.removeBook(item.id);
      await refreshOfflineIds();
      renderLibrary();
      BP.showAppToast("Offline", "Offline copy removed.", "ok");
    } catch (err) {
      BP.showAppToast("Offline", err.message || "Could not remove offline copy", "err");
    }
  }

  function wireOfflineActions(root, item) {
    root.querySelector(".keep-offline")?.addEventListener("click", () => void keepOfflineCopy(item));
    root.querySelector(".remove-offline")?.addEventListener("click", () => void removeOfflineCopy(item));
    root.querySelector(".device-send")?.addEventListener("click", () => BP.openDeviceSendModal?.(item));
  }

  function clearCoverUrls() {
    for (const url of coverBlobUrls.values()) URL.revokeObjectURL(url);
    coverBlobUrls.clear();
  }

  function setUploadProgress(ratio, label) {
    const box = document.getElementById("lib-import-progress");
    const fill = document.getElementById("lib-import-progress-fill");
    const lab = document.getElementById("lib-import-progress-label");
    if (!box || !fill || !lab) return;
    box.classList.remove("hidden");
    const pct = Math.max(0, Math.min(100, Math.round(ratio * 100)));
    fill.style.width = pct + "%";
    lab.textContent = label || pct + "%";
  }

  function hideUploadProgress() {
    document.getElementById("lib-import-progress")?.classList.add("hidden");
  }

  async function uploadImportSession(sessionCreatePath, sessionIdPrefix, files) {
    const session = await BP.api(sessionCreatePath, {
      method: "POST",
      body: JSON.stringify({
        parts: files.map((f) => ({ name: f.name, size: f.size })),
      }),
    });
    const chunkSize = session.chunk_size || 4 * 1024 * 1024;
    let uploaded = 0;
    const total =
      session.total_bytes || files.reduce((sum, file) => sum + (file.size || 0), 0);
    setUploadProgress(0, "Uploading…");
    for (const file of files) {
      let offset = 0;
      while (offset < file.size) {
        const end = Math.min(offset + chunkSize, file.size);
        const slice = file.slice(offset, end);
        const res = await fetch(
          sessionIdPrefix + encodeURIComponent(session.session_id) + "/chunk",
          {
            method: "POST",
            headers: {
              ...CSRF,
              ...(BP.state.authHeader ? { Authorization: BP.state.authHeader } : {}),
              "X-Bookpup-Part": file.name,
              "X-Bookpup-Offset": String(offset),
              "Content-Type": "application/octet-stream",
            },
            body: slice,
          }
        );
        const text = await res.text();
        let chunk = {};
        try {
          chunk = text ? JSON.parse(text) : {};
        } catch {
          chunk = {};
        }
        if (!res.ok) throw new Error((chunk && chunk.error) || res.statusText || "Chunk failed");
        const n = slice.size;
        offset += n;
        uploaded += n;
        setUploadProgress(uploaded / total, `Uploading ${BP.bytes(uploaded)} / ${BP.bytes(total)}`);
      }
    }
    setUploadProgress(1, "Importing…");
    return BP.api(sessionIdPrefix + encodeURIComponent(session.session_id) + "/finish", {
      method: "POST",
      body: "{}",
    });
  }

  async function importCalibreParts(fileList) {
    const status = document.getElementById("calibre-import-status");
    const files = Array.from(fileList || []).filter((f) =>
      /\.calibre-data$/i.test(f.name || "")
    );
    if (!files.length) {
      if (status) status.textContent = "Choose part-*.calibre-data file(s) from a Calibre export folder.";
      return;
    }
    if (status) status.textContent = `Uploading ${files.length} part file(s)…`;
    let data;
    try {
      data = await uploadImportSession(
        "/api/library/import-calibre/session",
        "/api/library/import-calibre/session/",
        files
      );
    } finally {
      hideUploadProgress();
    }
    const errN = (data.errors || []).length;
    if (status) {
      status.textContent =
        `Imported ${data.imported || 0}, skipped ${data.skipped || 0}` +
        (errN ? `, ${errN} issue(s)` : "") +
        ".";
    }
    loadLibrary();
    return data;
  }

  async function importKoreaderSidecars(fileList) {
    const status = document.getElementById("koreader-import-status");
    const files = Array.from(fileList || []).filter((f) =>
      /\.(lua|zip)$/i.test(f.name || "")
    );
    if (!files.length) {
      if (status) status.textContent = "Choose .lua sidecars or a .zip of .sdr folders.";
      return;
    }
    if (status) status.textContent = `Uploading ${files.length} file(s)…`;
    try {
      const data = await uploadImportSession(
        "/api/library/koreader/import/session",
        "/api/library/koreader/import/session/",
        files
      );
      const n = data.imported || (data.results || []).length;
      const errN = (data.errors || []).length;
      if (status) {
        if (n) status.textContent = "Imported " + n + " KOReader sidecar(s)." + (errN ? " (" + errN + " failed.)" : "");
        else if (errN) status.textContent = errN + " file(s) could not be read.";
        else status.textContent = "";
      }
      loadLibrary();
      return data;
    } finally {
      hideUploadProgress();
    }
  }

  function libraryMetaLine(item) {
    const bits = [];
    if (item.authors) bits.push(item.authors);
    if (item.series) {
      let line = item.series;
      if (item.series_index != null && item.series_index !== "") {
        line += " #" + item.series_index;
      }
      bits.push(line);
    }
    if (item.publisher) bits.push(item.publisher);
    if (item.tags) bits.push(item.tags);
    if (item.koreader_percentage != null && item.koreader_percentage !== "") {
      const pct = Math.round(Number(item.koreader_percentage) * 1000) / 10;
      if (!Number.isNaN(pct)) bits.push("KOReader " + pct + "%");
    }
    return bits.join(" · ");
  }

  function downloadNameFromResponse(item, disposition) {
    if (disposition) {
      const star = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
      if (star) {
        try {
          return decodeURIComponent(star[1].trim());
        } catch (_e) {
          return star[1].trim();
        }
      }
      const plain = /filename="([^"]+)"/i.exec(disposition);
      if (plain) return plain[1];
    }
    const fmt = (item.format || "bin").toLowerCase().replace(/^\./, "");
    if (item.filename) return item.filename;
    const base = (item.title || item.id || "book").replace(/[^\w.\-()+ ]+/g, "_").trim() || "book";
    return base + (base.includes(".") ? "" : "." + fmt);
  }

  async function downloadLibraryItem(item) {
    const res = await fetch("/api/library/" + encodeURIComponent(item.id) + libOwnerQuery(), {
      headers: { ...(BP.state.authHeader ? { Authorization: BP.state.authHeader } : {}) },
    });
    if (res.status === 401) {
      BP.showLogin("Your session wandered off. Come inside again.");
      throw new Error("Authentication required");
    }
    if (!res.ok) {
      const text = await res.text();
      let msg = "Download failed";
      try {
        const data = JSON.parse(text);
        if (data && data.error) msg = data.error;
      } catch (_e) {
        /* body may be empty */
      }
      throw new Error(msg);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = downloadNameFromResponse(item, res.headers.get("Content-Disposition"));
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function refreshOfflineIds() {
    if (!BP.offlineBooks) {
      offlineIdSet = new Set();
      return;
    }
    try {
      const metas = await BP.offlineBooks.listMeta();
      offlineIdSet = new Set(metas.map((m) => m.item_id));
    } catch {
      offlineIdSet = new Set();
    }
  }

  async function coverUrlForItem(item) {
    if (item?.offline_only && item.id && BP.offlineBooks) {
      return BP.offlineBooks.coverBlobUrlFor(item.id);
    }
    if (!item.has_cover) return null;
    if (coverBlobUrls.has(item.id)) return coverBlobUrls.get(item.id);
    const res = await fetch("/api/library/" + encodeURIComponent(item.id) + "/cover" + libOwnerQuery(), {
      headers: { ...CSRF, ...(BP.state.authHeader ? { Authorization: BP.state.authHeader } : {}) },
    });
    if (!res.ok) return null;
    const url = URL.createObjectURL(await res.blob());
    coverBlobUrls.set(item.id, url);
    return url;
  }

  const sendModal = document.getElementById("send-modal");
  const sendForm = document.getElementById("send-form");
  const sendToSelect = document.getElementById("send-to-user");
  const sendItemLabel = document.getElementById("send-item-label");
  const sendMsg = document.getElementById("send-msg");

  function closeSendModal() {
    BP.state.sendTarget = null;
    if (sendModal) sendModal.classList.add("hidden");
    if (sendForm) sendForm.reset();
    if (sendMsg) {
      sendMsg.textContent = "";
      sendMsg.className = "bp-msg muted";
    }
  }

  async function openSendModal(target) {
    BP.state.sendTarget = target;
    const { users } = await BP.api("/api/users");
    const choices = (users || []).filter((u) => u && u !== BP.state.sessionUsername);
    if (!choices.length) {
      BP.showAppToast("Pass to pup", "No other pups in the pack to pass to.", "info");
      return;
    }
    if (sendToSelect) {
      sendToSelect.innerHTML = choices.map((u) => '<option value="' + BP.escapeHtml(u) + '">' + BP.escapeHtml(u) + "</option>").join("");
    }
    if (sendItemLabel) sendItemLabel.textContent = "Pass a copy to another kennel: " + (target.title || target.id);
    const titleEl = document.getElementById("send-modal-title");
    if (titleEl) titleEl.textContent = "Pass to a pup";
    if (sendModal) sendModal.classList.remove("hidden");
  }

  document.getElementById("send-modal-close")?.addEventListener("click", closeSendModal);
  document.getElementById("send-cancel")?.addEventListener("click", closeSendModal);
  if (sendForm) {
    sendForm.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      if (!BP.state.sendTarget) return;
      const to = sendToSelect && sendToSelect.value;
      if (!to) return;
      if (sendMsg) {
        sendMsg.textContent = "Sending…";
        sendMsg.className = "bp-msg muted";
      }
      try {
        if (BP.state.sendTarget.kind === "library") {
          await BP.api("/api/library/" + encodeURIComponent(BP.state.sendTarget.id) + "/send", {
            method: "POST",
            body: JSON.stringify({ to }),
          });
        } else {
          await BP.api("/api/staging/" + encodeURIComponent(BP.state.sendTarget.id) + "/send", {
            method: "POST",
            body: JSON.stringify({ to, title: BP.state.sendTarget.title }),
          });
        }
        BP.showAppToast(
          "Pass to pup",
          "Passed to " + to + " — you keep your copy.",
          "ok"
        );
        if (sendMsg) {
          sendMsg.textContent = "";
          sendMsg.className = "bp-msg muted";
        }
        closeSendModal();
      } catch (err) {
        if (sendMsg) {
          sendMsg.textContent = err.message;
          sendMsg.className = "bp-msg err";
        }
      }
    });
  }

  async function takeSharedItem(item) {
    if (!libraryBrowseOwner) return;
    try {
      await BP.api(
        "/api/library/shares/" +
          encodeURIComponent(libraryBrowseOwner) +
          "/items/" +
          encodeURIComponent(item.id) +
          "/take",
        { method: "POST", body: "{}" }
      );
      BP.showAppToast("Kennel", "Added to your kennel — " + (item.title || item.filename), "ok");
      const own = await BP.api("/api/library");
      ownLibraryQuota = { used_bytes: own.used_bytes, quota_bytes: own.quota_bytes };
      if (!isSharedBrowse()) updateLibraryQuota(own);
    } catch (err) {
      BP.showAppToast("Kennel", err.message || "Could not add book", "err");
    }
  }

  function buildLibraryActionsHtml(item, readable) {
    const fmt = (item.format || "").toLowerCase().replace(/["']/g, "").replace(/^\./, "");
    const canRead = readable.has(fmt);
    const staged = isStagedItem(item);
    const shared = isSharedBrowse();
    const ownerActions = shared
      ? ""
      : (staged ? '<button type="button" class="bp-btn register">Tag</button> ' : "") +
        (isRegisteredItem(item) ? '<button type="button" class="bp-btn edit-meta">Edit tags</button> ' : "") +
        '<button type="button" class="bp-btn cover">Cover</button> ' +
        '<button type="button" class="bp-btn send">Pass to pup…</button> ' +
        '<button type="button" class="bp-btn del">Toss</button> ';
    const takeBtn =
      shared && libraryBrowseMode === "give"
        ? '<button type="button" class="bp-btn take-shared">Add to my kennel</button> '
        : "";
    const copyLink = isRegisteredItem(item)
      ? '<button type="button" class="bp-btn copy-link">Copy link</button> '
      : "";
    return (
      deviceSendButton(item, shared) +
      offlineActionButton(item, shared) +
      (canRead ? '<button type="button" class="bp-btn read">Read</button> ' : "") +
      copyLink +
      ownerActions +
      takeBtn +
      '<a class="bp-btn dl" href="#">Grab file</a> '
    );
  }

  function attachLibraryItemActions(root, item, readable) {
    const fmt = (item.format || "").toLowerCase().replace(/["']/g, "").replace(/^\./, "");
    const shared = isSharedBrowse();
    const dl = root.querySelector("a.dl");
    if (dl) {
      dl.href = "#";
      dl.addEventListener("click", (ev) => {
        ev.preventDefault();
        downloadLibraryItem(item).catch((err) =>
          BP.showAppToast("Download", err.message || "Download failed", "err")
        );
      });
    }
    const read = root.querySelector(".read");
    if (read) read.addEventListener("click", () => openLibraryReader(item));
    root.querySelector(".copy-link")?.addEventListener("click", () => void copyLibraryLink(item));
    wireOfflineActions(root, item);
    if (!shared) {
      root.querySelector(".del")?.addEventListener("click", async () => {
        if (!(await BP.confirmToss(item.title || item.filename, { light: isStagedItem(item) }))) return;
        await BP.tossLibraryItem(item.id);
      });
      root.querySelector(".cover")?.addEventListener("click", () => openCoverModal(item));
      root.querySelector(".register")?.addEventListener("click", () => openRegisterModal(item));
      root.querySelector(".edit-meta")?.addEventListener("click", () => openEditMetadataModal(item));
      root.querySelector(".send")?.addEventListener("click", () =>
        openSendModal({ kind: "library", id: item.id, title: item.title || item.filename })
      );
    }
    root.querySelector(".take-shared")?.addEventListener("click", () => void takeSharedItem(item));
    const host = root.closest(".bp-lib-card") || root.closest(".bp-lib-flow");
    if (host && !readable.has(fmt)) host.classList.add("bp-lib-card--nodl-read");
    else if (host) host.classList.remove("bp-lib-card--nodl-read");
  }

  function attachLibraryCard(card, item, readable) {
    attachLibraryItemActions(card, item, readable);
    const img = card.querySelector(".bp-lib-cover");
    if (img) {
      if (item.has_cover) {
        coverUrlForItem(item).then((url) => {
          if (url) img.src = url;
        });
      } else {
        img.classList.add("bp-lib-cover--empty");
      }
    }
  }

  function renderLibraryCard(item, readable) {
    const fmt = (item.format || "").toLowerCase().replace(/["']/g, "").replace(/^\./, "");
    const card = document.createElement("article");
    card.className = "bp-lib-card";
    if (item.id) card.dataset.libItemId = item.id;
    const meta = libraryMetaLine(item);
    const pub = item.pubdate ? BP.escapeHtml(String(item.pubdate)) + " · " : "";
    card.innerHTML =
      '<div class="bp-lib-cover-wrap">' +
      '<img class="bp-lib-cover" alt="" width="120" height="160" loading="lazy" />' +
      '<span class="bp-lib-format">' +
      BP.escapeHtml((fmt || "?").toUpperCase()) +
      "</span>" +
      readingPillHtml(item) +
      "</div>" +
      '<div class="bp-lib-card-body">' +
      '<h4 class="bp-lib-title">' +
      BP.escapeHtml(item.title || item.filename) +
      "</h4>" +
      (meta ? '<p class="bp-lib-meta">' + BP.escapeHtml(meta) + "</p>" : "") +
      '<p class="bp-lib-extra muted">' +
      pub +
      BP.escapeHtml(BP.bytes(item.bytes || 0)) +
      "</p>" +
      '<div class="bp-lib-card-actions">' +
      buildLibraryActionsHtml(item, readable) +
      "</div></div>";
    attachLibraryCard(card, item, readable);
    return card;
  }

  function attachLibraryRow(tr, item, readable) {
    const fmt = (item.format || "").toLowerCase().replace(/["']/g, "").replace(/^\./, "");
    const shared = isSharedBrowse();
    const read = tr.querySelector(".read");
    if (read) read.addEventListener("click", () => openLibraryReader(item));
    tr.querySelector(".copy-link")?.addEventListener("click", () => void copyLibraryLink(item));
    wireOfflineActions(tr, item);
    const dl = tr.querySelector("a.dl");
    if (dl) {
      dl.href = "#";
      dl.addEventListener("click", (ev) => {
        ev.preventDefault();
        downloadLibraryItem(item).catch((err) =>
          BP.showAppToast("Download", err.message || "Download failed", "err")
        );
      });
    }
    if (!shared) {
      tr.querySelector(".del")?.addEventListener("click", async () => {
        if (!(await BP.confirmToss(item.title || item.filename, { light: isStagedItem(item) }))) return;
        await BP.tossLibraryItem(item.id);
      });
      tr.querySelector(".register")?.addEventListener("click", () => openRegisterModal(item));
      tr.querySelector(".edit-meta")?.addEventListener("click", () => openEditMetadataModal(item));
      tr.querySelector(".cover")?.addEventListener("click", () => openCoverModal(item));
      tr.querySelector(".send")?.addEventListener("click", () =>
        openSendModal({ kind: "library", id: item.id, title: item.title || item.filename })
      );
    }
    tr.querySelector(".take-shared")?.addEventListener("click", () => void takeSharedItem(item));
    const thumb = tr.querySelector(".bp-lib-list-cover");
    if (thumb && item.has_cover) {
      coverUrlForItem(item).then((url) => {
        if (url) thumb.src = url;
      });
    } else if (thumb) {
      thumb.classList.add("bp-lib-cover--empty");
    }
  }

  function renderLibraryList(items, readable) {
    const wrap = document.createElement("div");
    wrap.className = "bp-table-wrap";
    const table = document.createElement("table");
    table.className = "bp-lib-table";
    table.innerHTML =
      "<thead><tr>" +
      "<th class='bp-lib-th-cover'></th>" +
      "<th>Title</th><th>Author</th><th>Series</th><th>Format</th><th>Size</th><th></th>" +
      "</tr></thead><tbody></tbody>";
    const tbody = table.querySelector("tbody");
    items.forEach((item) => {
      const fmt = (item.format || "").toLowerCase().replace(/["']/g, "").replace(/^\./, "");
      const canRead = readable.has(fmt);
      let series = item.series || "";
      if (series && item.series_index != null && item.series_index !== "") {
        series += " #" + item.series_index;
      }
      const shared = isSharedBrowse();
      const ownerCells = shared
        ? ""
        : (isStagedItem(item) ? '<button type="button" class="bp-btn register">Tag</button> ' : "") +
          (isRegisteredItem(item) ? '<button type="button" class="bp-btn edit-meta">Edit tags</button> ' : "") +
          '<button type="button" class="bp-btn cover">Cover</button> ' +
          '<button type="button" class="bp-btn send">Pass to pup…</button> ' +
          '<button type="button" class="bp-btn del">Toss</button> ';
      const takeBtn =
        shared && libraryBrowseMode === "give"
          ? '<button type="button" class="bp-btn take-shared">Add to my kennel</button> '
          : "";
      const tr = document.createElement("tr");
      if (item.id) tr.dataset.libItemId = item.id;
      tr.innerHTML =
        "<td class='bp-lib-td-cover'><img class='bp-lib-list-cover' alt='' width='40' height='56' loading='lazy' /></td>" +
        "<td class='bp-lib-td-title'>" +
        '<span class="bp-lib-list-title-text">' +
        BP.escapeHtml(item.title || item.filename) +
        "</span> " +
        readingPillHtml(item) +
        '<span class="bp-lib-list-meta muted">' +
        BP.escapeHtml((fmt || "?").toUpperCase()) +
        " · " +
        BP.escapeHtml(BP.bytes(item.bytes || 0)) +
        "</span></td>" +
        "<td>" +
        BP.escapeHtml(item.authors || "—") +
        "</td>" +
        "<td>" +
        BP.escapeHtml(series || "—") +
        "</td>" +
        "<td>" +
        BP.escapeHtml((fmt || "?").toUpperCase()) +
        "</td>" +
        "<td>" +
        BP.escapeHtml(BP.bytes(item.bytes || 0)) +
        "</td>" +
        "<td class='bp-lib-td-actions'>" +
        deviceSendButton(item, shared) +
        offlineActionButton(item, shared) +
        (canRead ? '<button type="button" class="bp-btn read">Read</button> ' : "") +
        (isRegisteredItem(item)
          ? '<button type="button" class="bp-btn copy-link">Copy link</button> '
          : "") +
        ownerCells +
        takeBtn +
        '<a class="bp-btn dl" href="#">Grab file</a> ' +
        "</td>";
      attachLibraryRow(tr, item, readable);
      tbody.appendChild(tr);
    });
    wrap.appendChild(table);
    return wrap;
  }

  function fillLibrarySection(container, items, readable, emptyText, filterActive, seriesGapHints, allowFlow) {
    if (!container) return;
    if (BP.LibraryFlow) BP.LibraryFlow.destroy(container);
    const group = libraryGroupMode();
    const layout = allowFlow ? catalogueEffectiveLayout() : downloadsLayoutMode();
    container.innerHTML = "";
    if (!items.length) {
      container.className = "bp-lib-items bp-lib-items--grid";
      const empty = document.createElement("p");
      empty.className = "bp-msg muted";
      empty.textContent = filterActive ? "No books match your filter." : emptyText;
      container.appendChild(empty);
      return;
    }
    if (group === "series") {
      container.className = "bp-lib-series-wrap";
      const bySeries = new Map();
      const loose = [];
      items.forEach((item) => {
        const s = String(item.series || "").trim();
        if (!s) loose.push(item);
        else {
          if (!bySeries.has(s)) bySeries.set(s, []);
          bySeries.get(s).push(item);
        }
      });
      [...bySeries.keys()].sort((a, b) => a.localeCompare(b)).forEach((name) => {
        renderLibraryGroupBlock(container, name, bySeries.get(name) || [], readable, {
          seriesGaps: seriesGapHints,
        });
      });
      if (loose.length) {
        renderLibraryGroupBlock(container, "No series set", loose, readable, { seriesGaps: false });
      }
      return;
    }
    if (group === "author") {
      container.className = "bp-lib-series-wrap";
      const byAuthor = new Map();
      const loose = [];
      items.forEach((item) => {
        const a = String(item.authors || "").trim();
        if (!a) loose.push(item);
        else {
          if (!byAuthor.has(a)) byAuthor.set(a, []);
          byAuthor.get(a).push(item);
        }
      });
      [...byAuthor.keys()].sort((a, b) => a.localeCompare(b)).forEach((name) => {
        renderLibraryGroupBlock(container, name, byAuthor.get(name) || [], readable);
      });
      if (loose.length) {
        renderLibraryGroupBlock(container, "Unknown author", loose, readable);
      }
      return;
    }
    const sorted = sortLibraryItems(items);
    if (allowFlow && layout === "flow" && BP.LibraryFlow) {
      BP.LibraryFlow.mount(container, sorted, readable, {
        coverUrlForItem,
        buildLibraryActionsHtml,
        attachLibraryActions: attachLibraryItemActions,
        libraryMetaLine,
      });
      return;
    }
    container.className = "bp-lib-items bp-lib-items--" + layout;
    if (layout === "list") {
      container.appendChild(renderLibraryList(sorted, readable));
    } else {
      sorted.forEach((item) => container.appendChild(renderLibraryCard(item, readable)));
    }
  }

  function updateSharedBrowseChrome() {
    const shared = isSharedBrowse();
    const banner = document.getElementById("lib-browse-banner");
    const exportBtn = document.getElementById("lib-export-btn");
    const freshBtn = document.getElementById("fresh-upload-btn");
    const calImp = document.getElementById("calibre-import-btn");
    const koImp = document.getElementById("koreader-import-btn");
    const dlHead = document.querySelector("#lib-section-downloads .bp-lib-section-head p");
    const calHead = document.querySelector("#lib-section-calibre .bp-lib-section-head p");
    if (banner) {
      if (shared) {
        const mode =
          libraryBrowseMode === "give"
            ? "give — you may copy books into your kennel"
            : "lend — browse and read only";
        banner.textContent = "Browsing " + libraryBrowseOwner + "'s kennel (" + mode + ").";
        banner.classList.remove("hidden");
      } else {
        banner.classList.add("hidden");
        banner.textContent = "";
      }
    }
    const shelfRow = document.getElementById("lib-shelf-row");
    if (shelfRow) shelfRow.classList.toggle("hidden", shared || !!BP.state.offlineOnly);
    if (exportBtn) exportBtn.classList.toggle("hidden", shared);
    if (freshBtn) freshBtn.classList.toggle("hidden", shared);
    if (calImp) calImp.classList.toggle("hidden", shared);
    if (koImp) koImp.classList.toggle("hidden", shared);
    if (dlHead) dlHead.classList.toggle("hidden", shared);
    if (calHead && shared) calHead.textContent = "Their fresh catches and catalogued bones — read-only.";
    else if (calHead && !shared)
      calHead.textContent =
        "Catalogued bones — synced to OPDS and KOReader wireless progress.";
  }

  function renderLibrary() {
    const filterActive = !!(libFilterInput && libFilterInput.value.trim());
    const hideDownloads = !!BP.state.offlineOnly || !!activeShelfId;
    document.getElementById("lib-section-downloads")?.classList.toggle("hidden", hideDownloads);
    const progWrap = document.getElementById("lib-in-progress-wrap");
    const progInput = document.getElementById("lib-in-progress-only");
    if (progWrap) progWrap.classList.toggle("hidden", !!BP.state.offlineOnly);
    if (progInput) progInput.checked = libInProgressOnly && !BP.state.offlineOnly;
    updateSharedBrowseChrome();
    updateShelfToolbar();
    document.getElementById("lib-usage").textContent =
      libraryUsageText || "Library";
    clearCoverUrls();
    const readable = libraryReadableFormats;
    const calibreEl = document.getElementById("lib-items-calibre");
    const downloadEl = document.getElementById("lib-items-downloads");
    const calibre = [];
    const downloads = [];
    filterLibraryItems(libraryItemsCache).forEach((item) => {
      if (isRegisteredItem(item)) calibre.push(item);
      else downloads.push(item);
    });
    const freshEmpty = document.getElementById("fresh-empty");
    const showFreshEmpty = !filterActive && !downloads.length;
    if (freshEmpty) freshEmpty.classList.toggle("hidden", !showFreshEmpty);
    if (downloadEl) downloadEl.classList.toggle("hidden", showFreshEmpty);
    fillLibrarySection(
      downloadEl,
      downloads,
      readable,
      "No fresh catches yet — sniff something on IRC.",
      filterActive,
      false,
      false
    );
    const shelf =
      activeShelfId && libraryShelvesCache.find((s) => s.id === activeShelfId);
    const catalogueEmpty =
      shelf && !filterActive
        ? `No books on “${shelf.name}” yet — assign catalogued bones from the list or pick another shelf.`
        : "No catalogued bones yet — import Calibre or tag a fresh catch.";
    fillLibrarySection(calibreEl, calibre, readable, catalogueEmpty, filterActive, true, true);
    updateLibraryToolbar();
    updateLibFilterClearBtn();
  }

  let libraryUsageText = "";

  function updateLibraryBadge() {
    const badge = document.getElementById("library-tab-badge");
    if (!badge) return;
    const n = libraryItemsCache.filter((it) => isStagedItem(it)).length;
    if (n < 1) {
      badge.classList.add("hidden");
      badge.textContent = "";
      badge.removeAttribute("aria-label");
      return;
    }
    badge.textContent = n > 99 ? "99+" : String(n);
    badge.classList.remove("hidden");
    badge.setAttribute("aria-label", n + " fresh catch(es)");
  }

  function updateLibraryQuota(lib) {
    const used = lib.used_bytes || 0;
    const quota = lib.quota_bytes || 1;
    const pct = Math.min(100, Math.round((used / quota) * 100));
    const fill = document.getElementById("lib-usage-fill");
    const pctEl = document.getElementById("lib-usage-pct");
    if (fill) {
      fill.style.width = pct + "%";
      fill.classList.toggle("bp-progress-fill--warn", pct >= 85);
      fill.classList.toggle("bp-progress-fill--danger", pct >= 95);
    }
    if (pctEl) pctEl.textContent = pct + "%";
  }

  function focusLibraryItem(itemId) {
    if (!itemId) return;
    const btn = BP.tabButton("library");
    if (btn) BP.activateTab(btn);
    if (libFilterInput) {
      const item = libraryItemsCache.find((it) => it.id === itemId);
      libFilterInput.value = item?.title || itemId;
    }
    if (libraryLayoutMode() === "flow" && flowAvailable() && BP.LibraryFlow) {
      BP.LibraryFlow.setIndexByItemId(itemId);
    }
    renderLibrary();
    requestAnimationFrame(() => {
      const calibreEl = document.getElementById("lib-items-calibre");
      const inFlow = calibreEl?.classList.contains("bp-lib-items--flow");
      const sel = inFlow
        ? calibreEl?.querySelector('.bp-lib-flow__spine--center[data-lib-item-id="' + CSS.escape(itemId) + '"]')
        : document.querySelector('[data-lib-item-id="' + CSS.escape(itemId) + '"]');
      sel?.classList.add("bp-lib-highlight");
      sel?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      setTimeout(() => sel?.classList.remove("bp-lib-highlight"), 4000);
    });
  }

  async function refreshLibraryShares() {
    try {
      librarySharesData = await BP.api("/api/library/shares");
    } catch (_e) {
      librarySharesData = { incoming: [], outgoing: [], browsing: [] };
    }
    syncBrowseSelect();
    updateSharingBadge();
    renderShareModalLists();
  }

  function syncBrowseSelect() {
    const sel = document.getElementById("lib-browse-select");
    if (!sel) return;
    const prev = libraryBrowseOwner;
    const browsing = librarySharesData.browsing || [];
    sel.innerHTML =
      '<option value="">My kennel</option>' +
      browsing
        .map((g) => {
          const label = g.owner + " (" + (g.mode === "give" ? "give" : "lend") + ")";
          return (
            '<option value="' + BP.escapeHtml(g.owner) + '">' + BP.escapeHtml(label) + "</option>"
          );
        })
        .join("");
    if (prev && browsing.some((g) => g.owner === prev)) {
      sel.value = prev;
    } else if (prev && !browsing.some((g) => g.owner === prev)) {
      libraryBrowseOwner = "";
      libraryBrowseMode = null;
      sel.value = "";
    }
    const hit = browsing.find((g) => g.owner === sel.value);
    libraryBrowseMode = hit ? hit.mode : null;
  }

  function updateSharingBadge() {
    const badge = document.getElementById("lib-sharing-badge");
    if (!badge) return;
    const pending = (librarySharesData.incoming || []).filter((g) => g.status === "pending").length;
    badge.classList.toggle("hidden", pending < 1);
    badge.textContent = pending > 9 ? "9+" : String(pending);
  }

  async function loadLibrary() {
    if (BP.state.offlineOnly && BP.offlineBooks) {
      await refreshOfflineIds();
      libraryItemsCache = await BP.offlineBooks.pseudoLibraryItems();
      const used = await BP.offlineBooks.totalBytes();
      libraryUsageText = "Offline · " + BP.bytes(used) + " on this device";
      libraryReadableFormats = new Set(["epub", "pdf"]);
      updateLibraryBadge();
      renderLibrary();
      return;
    }
    try {
      await refreshLibraryShares();
    } catch (err) {
      if (!navigator.onLine && BP.offlineBooks) {
        const metas = await BP.offlineBooks.listMeta();
        if (metas.length) {
          BP.state.offlineOnly = true;
          return loadLibrary();
        }
      }
      throw err;
    }
    const path = libraryBrowseOwner
      ? "/api/library/shares/" + encodeURIComponent(libraryBrowseOwner) + "/catalog"
      : "/api/library";
    let lib;
    try {
      lib = await BP.api(path);
    } catch (err) {
      if (!navigator.onLine && BP.offlineBooks && !libraryBrowseOwner) {
        const metas = await BP.offlineBooks.listMeta();
        if (metas.length) {
          BP.state.offlineOnly = true;
          BP.showAppToast("Offline", "Server unreachable — showing books on this device.", "info");
          return loadLibrary();
        }
      }
      throw err;
    }
    await refreshOfflineIds();
    if (!libraryBrowseOwner && lib.pruned_ghosts > 0) {
      BP.showAppToast?.(
        "Kennel",
        `Removed ${lib.pruned_ghosts} ghost ${lib.pruned_ghosts === 1 ? "entry" : "entries"} (file was gone).`,
        "info"
      );
    }
    if (!libraryBrowseOwner) {
      ownLibraryQuota = { used_bytes: lib.used_bytes, quota_bytes: lib.quota_bytes };
      libraryUsageText = `Kennel ${BP.bytes(lib.used_bytes)} / ${BP.bytes(lib.quota_bytes)}`;
      updateLibraryQuota(lib);
    } else {
      libraryUsageText = libraryBrowseOwner + "'s kennel";
      updateLibraryQuota(ownLibraryQuota);
      libraryBrowseMode = lib.share_mode || libraryBrowseMode;
    }
    libraryItemsCache = lib.items || [];
    libraryShelvesCache = Array.isArray(lib.shelves) ? lib.shelves : [];
    if (!libraryBrowseOwner) {
      const saved = localStorage.getItem(LIB_SHELF_KEY) || "";
      if (saved && libraryShelvesCache.some((s) => s.id === saved)) activeShelfId = saved;
      else if (saved) {
        activeShelfId = "";
        localStorage.removeItem(LIB_SHELF_KEY);
      }
    } else {
      activeShelfId = "";
    }
    syncShelfSelect();
    if (Array.isArray(lib.readable_formats) && lib.readable_formats.length) {
      libraryReadableFormats = new Set(lib.readable_formats);
    } else {
      libraryReadableFormats = new Set(LIBRARY_READABLE_FALLBACK);
    }
    updateLibraryBadge();
    renderLibrary();
    tryFocusPendingLibraryItem();
  }

  async function openLibraryReader(item) {
    try {
      if (BP.offlineBooks && (BP.state.offlineOnly || !navigator.onLine)) {
        if (await BP.offlineBooks.has(item.id)) {
          const meta = await BP.offlineBooks.viewMeta(item.id);
          if (meta && window.BookPupReader) {
            await window.BookPupReader.open(meta, BP.state.authHeader);
            return;
          }
        }
        throw new Error("No offline copy — use Keep offline while connected");
      }
      const body = libraryBrowseOwner
        ? JSON.stringify({ owner: libraryBrowseOwner })
        : "{}";
      const meta = await BP.api("/api/library/" + encodeURIComponent(item.id) + "/view", {
        method: "POST",
        body,
      });
      if (window.BookPupReader) {
        await window.BookPupReader.open(meta, BP.state.authHeader);
      }
    } catch (err) {
      BP.showAppToast("Reader", err.message || "Could not open reader", "err");
    }
  }

  const registerModal = document.getElementById("register-modal");
  const registerForm = document.getElementById("register-form");
  const registerResults = document.getElementById("register-results");
  const registerMsg = document.getElementById("register-msg");
  const registerCoverImages = document.getElementById("register-cover-images");
  const registerCoverFileHint = document.getElementById("register-cover-file-hint");
  const registerCoverFile = document.getElementById("reg-cover-file");
  const coverModal = document.getElementById("cover-modal");
  const coverModalMsg = document.getElementById("cover-modal-msg");
  const coverModalImages = document.getElementById("cover-modal-images");
  const coverModalFile = document.getElementById("cover-modal-file");
  let registerItemId = null;
  let registerMode = "register";
  const registerModalTitle = document.getElementById("register-modal-title");
  const registerSubmitBtn = document.getElementById("register-submit");
  let coverModalItemId = null;
  let coverModalItem = null;

  function registerField(id) {
    return document.getElementById(id);
  }

  function validateCoverFile(file) {
    if (!file) return "No file chosen";
    if (file.size > COVER_MAX_BYTES) return "Image must be 2 MB or smaller";
    const ok = ["image/jpeg", "image/png", "image/webp"];
    if (!ok.includes(file.type)) return "Use JPEG, PNG, or WebP";
    return null;
  }

  async function uploadCoverFile(itemId, file) {
    const v = validateCoverFile(file);
    if (v) throw new Error(v);
    const fd = new FormData();
    fd.append("cover", file, file.name || "cover.jpg");
    const res = await fetch("/api/library/" + encodeURIComponent(itemId) + "/cover", {
      method: "POST",
      headers: { ...CSRF, ...(BP.state.authHeader ? { Authorization: BP.state.authHeader } : {}) },
      body: fd,
    });
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { raw: text };
    }
    if (!res.ok) {
      throw new Error((data && data.error) || res.statusText || "Upload failed");
    }
    return data;
  }

  async function applyCoverFromUrl(itemId, url) {
    return BP.api("/api/library/" + encodeURIComponent(itemId) + "/cover/url", {
      method: "POST",
      body: JSON.stringify({ url }),
    });
  }

  function setSearchBtnLoading(btn, loading) {
    if (!btn) return;
    btn.classList.remove("bp-btn--loading");
    btn.removeAttribute("aria-busy");
    if (loading) {
      if (!btn.dataset.bpLabel) btn.dataset.bpLabel = btn.textContent;
      btn.disabled = true;
      btn.classList.add("bp-btn--loading");
      btn.setAttribute("aria-busy", "true");
      btn.textContent = "";
    } else {
      btn.disabled = false;
      btn.textContent = btn.dataset.bpLabel || btn.textContent;
    }
  }

  function renderCoverImageResults(container, rows, onPick) {
    if (!container) return;
    container.innerHTML = "";
    if (!rows.length) {
      container.classList.remove("hidden");
      container.innerHTML = '<p class="bp-msg muted">No images found.</p>';
      return;
    }
    container.classList.remove("hidden");
    let selectedBtn = null;
    rows.forEach((row) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "bp-cover-pick";
      btn.title = row.title || "Cover";
      const img = document.createElement("img");
      img.src = row.thumbnail_url || row.url;
      img.alt = row.title || "";
      img.loading = "lazy";
      btn.appendChild(img);
      btn.addEventListener("click", () => {
        if (selectedBtn) selectedBtn.classList.remove("bp-cover-pick--selected");
        selectedBtn = btn;
        btn.classList.add("bp-cover-pick--selected");
        onPick(row);
      });
      container.appendChild(btn);
    });
  }

  async function searchCoverImages(itemId, fields, container, msgEl, onPick, searchBtn) {
    setSearchBtnLoading(searchBtn, true);
    if (msgEl) {
      msgEl.textContent = "Searching for cover images…";
      msgEl.className = "bp-msg muted";
    }
    try {
      const data = await BP.api(
        "/api/library/" + encodeURIComponent(itemId) + "/cover/images/search",
        { method: "POST", body: JSON.stringify(fields) }
      );
      renderCoverImageResults(container, data.results || [], onPick);
      if (msgEl && (data.results || []).length) {
        msgEl.textContent = (data.results || []).length + " image(s). Click one to use it.";
        msgEl.className = "bp-msg muted";
      }
    } catch (err) {
      if (msgEl) {
        msgEl.textContent = err.message || "Image search failed";
        msgEl.className = "bp-msg err";
      }
      if (container) {
        container.classList.add("hidden");
        container.innerHTML = "";
      }
    } finally {
      setSearchBtnLoading(searchBtn, false);
    }
  }

  function closeRegisterModal() {
    if (registerModal) registerModal.classList.add("hidden");
    registerItemId = null;
    registerMode = "register";
    if (registerModalTitle) registerModalTitle.textContent = "Tag this book";
    if (registerSubmitBtn) registerSubmitBtn.textContent = "Tag it";
    if (registerResults) {
      registerResults.classList.add("hidden");
      registerResults.innerHTML = "";
    }
    if (registerCoverImages) {
      registerCoverImages.classList.add("hidden");
      registerCoverImages.innerHTML = "";
    }
    if (registerCoverFile) registerCoverFile.value = "";
    if (registerCoverFileHint) {
      registerCoverFileHint.classList.add("hidden");
      registerCoverFileHint.textContent = "";
    }
    if (registerMsg) registerMsg.textContent = "";
  }

  function closeCoverModal() {
    if (coverModal) coverModal.classList.add("hidden");
    coverModalItemId = null;
    coverModalItem = null;
    if (coverModalImages) {
      coverModalImages.classList.add("hidden");
      coverModalImages.innerHTML = "";
    }
    if (coverModalFile) coverModalFile.value = "";
    if (coverModalMsg) coverModalMsg.textContent = "";
    document.body.classList.remove("bp-reader-open");
  }

  function openCoverModal(item) {
    coverModalItem = item;
    coverModalItemId = item.id;
    const titleEl = document.getElementById("cover-modal-title");
    if (titleEl) titleEl.textContent = "Cover — " + (item.title || item.filename || item.id);
    if (coverModalMsg) coverModalMsg.textContent = "";
    if (coverModalImages) {
      coverModalImages.classList.add("hidden");
      coverModalImages.innerHTML = "";
    }
    if (coverModal) coverModal.classList.remove("hidden");
    document.body.classList.add("bp-reader-open");
  }

  function fillRegisterForm(item) {
    registerField("reg-title").value = item.title || "";
    registerField("reg-authors").value = item.authors || "";
    registerField("reg-isbn").value = item.isbn || "";
    registerField("reg-series").value = item.series || "";
    registerField("reg-series-index").value =
      item.series_index != null && item.series_index !== "" ? item.series_index : "";
    registerField("reg-publisher").value = item.publisher || "";
    registerField("reg-pubdate").value = item.pubdate || "";
    registerField("reg-tags").value = item.tags || "";
    registerField("reg-comments").value = item.comments || "";
    registerField("reg-cover-url").value = "";
    const useCover = document.getElementById("register-use-cover");
    if (useCover) useCover.checked = false;
    if (registerCoverFile) registerCoverFile.value = "";
    if (registerCoverImages) {
      registerCoverImages.classList.add("hidden");
      registerCoverImages.innerHTML = "";
    }
    if (registerCoverFileHint) {
      registerCoverFileHint.classList.add("hidden");
      registerCoverFileHint.textContent = "";
    }
  }

  function applyMetadataCandidate(row) {
    registerField("reg-title").value = row.title || "";
    registerField("reg-authors").value = row.authors || "";
    registerField("reg-isbn").value = row.isbn || "";
    registerField("reg-publisher").value = row.publisher || "";
    registerField("reg-pubdate").value = row.pubdate || "";
    registerField("reg-tags").value = row.tags || "";
    registerField("reg-comments").value = row.comments || "";
    registerField("reg-cover-url").value = row.cover_url || "";
    const useCover = document.getElementById("register-use-cover");
    if (useCover) useCover.checked = !!row.cover_url;
    if (registerMsg) {
      registerMsg.textContent = `Selected match (${row.source || "online"}).`;
      registerMsg.className = "bp-msg muted";
    }
  }

  function openRegisterModal(item) {
    if (!isStagedItem(item)) return;
    registerMode = "register";
    registerItemId = item.id;
    if (registerModalTitle) registerModalTitle.textContent = "Tag this book";
    if (registerSubmitBtn) registerSubmitBtn.textContent = "Tag it";
    fillRegisterForm(item);
    if (registerModal) registerModal.classList.remove("hidden");
    document.body.classList.add("bp-reader-open");
    BP.walkTrailOnRegisterOpen?.(item);
  }

  function openEditMetadataModal(item) {
    if (!isRegisteredItem(item)) return;
    registerMode = "edit";
    registerItemId = item.id;
    if (registerModalTitle) registerModalTitle.textContent = "Edit tags";
    if (registerSubmitBtn) registerSubmitBtn.textContent = "Save";
    fillRegisterForm(item);
    if (registerMsg) registerMsg.textContent = "";
    if (registerModal) registerModal.classList.remove("hidden");
    document.body.classList.add("bp-reader-open");
  }

  async function searchRegisterMetadata() {
    if (!registerItemId) return;
    const searchBtn = document.getElementById("register-search-btn");
    setSearchBtnLoading(searchBtn, true);
    if (registerMsg) {
      registerMsg.textContent = "Searching Google Books and Open Library…";
      registerMsg.className = "bp-msg muted";
    }
    const payload = {
      title: registerField("reg-title").value,
      authors: registerField("reg-authors").value,
      isbn: registerField("reg-isbn").value,
    };
    try {
      const data = await BP.api(
        "/api/library/" + encodeURIComponent(registerItemId) + "/metadata/search",
        { method: "POST", body: JSON.stringify(payload) }
      );
      const rows = data.results || [];
      if (!registerResults) return;
      registerResults.innerHTML = "";
      if (!rows.length) {
        registerResults.classList.remove("hidden");
        registerResults.innerHTML = '<p class="bp-msg muted">No matches. Try a shorter title or last name only.</p>';
        if (registerMsg) registerMsg.textContent = "No matches.";
        return;
      }
      registerResults.classList.remove("hidden");
      rows.forEach((row) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "bp-register-hit";
        btn.innerHTML =
          BP.escapeHtml(row.title || "Untitled") +
          "<small>" +
          BP.escapeHtml(
            [row.authors, row.publisher, row.pubdate, row.isbn].filter(Boolean).join(" · ")
          ) +
          "</small>";
        btn.addEventListener("click", () => applyMetadataCandidate(row));
        registerResults.appendChild(btn);
      });
      if (registerMsg) registerMsg.textContent = rows.length + " match(es). Pick one to fill the form.";
    } catch (err) {
      if (registerMsg) {
        registerMsg.textContent = err.message || "Search failed";
        registerMsg.className = "bp-msg err";
      }
    } finally {
      setSearchBtnLoading(searchBtn, false);
    }
  }

  if (registerForm) {
    registerForm.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      if (!registerItemId) return;
      const itemId = registerItemId;
      if (registerMode === "register") {
        const dupes = findCatalogDuplicates({
          title: registerField("reg-title").value,
          authors: registerField("reg-authors").value,
          excludeId: itemId,
        });
        if (dupes.length) {
          const lines = dupes
            .map((d) => "• " + (d.title || d.filename) + (d.authors ? " — " + d.authors : ""))
            .join("\n");
          const ok = window.confirm(
            "This title may already be in your kennel:\n\n" +
              lines +
              "\n\nTag this fresh catch anyway?"
          );
          if (!ok) return;
        }
      }
      const pendingFile = registerCoverFile?.files?.[0] || null;
      if (pendingFile) {
        const v = validateCoverFile(pendingFile);
        if (v) {
          if (registerMsg) {
            registerMsg.textContent = v;
            registerMsg.className = "bp-msg err";
          }
          return;
        }
      }
      const useCover = document.getElementById("register-use-cover");
      const body = {
        title: registerField("reg-title").value,
        authors: registerField("reg-authors").value,
        isbn: registerField("reg-isbn").value,
        series: registerField("reg-series").value,
        series_index: registerField("reg-series-index").value,
        publisher: registerField("reg-publisher").value,
        pubdate: registerField("reg-pubdate").value,
        tags: registerField("reg-tags").value,
        comments: registerField("reg-comments").value,
        cover_url: registerField("reg-cover-url").value,
        use_cover: !pendingFile && !!(useCover && useCover.checked),
      };
      try {
        const path =
          registerMode === "edit"
            ? "/api/library/" + encodeURIComponent(itemId) + "/metadata"
            : "/api/library/" + encodeURIComponent(itemId) + "/register";
        await BP.api(path, {
          method: "POST",
          body: JSON.stringify(body),
        });
        if (pendingFile) await uploadCoverFile(itemId, pendingFile);
        closeRegisterModal();
        document.body.classList.remove("bp-reader-open");
        BP.walkTrailOnRegisterSaved?.(itemId);
        loadLibrary();
      } catch (err) {
        if (registerMsg) {
          registerMsg.textContent = err.message || "Tag failed";
          registerMsg.className = "bp-msg err";
        }
      }
    });
  }
  document.getElementById("register-search-btn")?.addEventListener("click", () => searchRegisterMetadata());
  document.getElementById("register-cover-images-btn")?.addEventListener("click", () => {
    if (!registerItemId) return;
    const coverSearchBtn = document.getElementById("register-cover-images-btn");
    void searchCoverImages(
      registerItemId,
      {
        title: registerField("reg-title").value,
        authors: registerField("reg-authors").value,
        isbn: registerField("reg-isbn").value,
      },
      registerCoverImages,
      registerMsg,
      (row) => {
        registerField("reg-cover-url").value = row.url;
        const useCover = document.getElementById("register-use-cover");
        if (useCover) useCover.checked = true;
        if (registerMsg) {
          registerMsg.textContent = "Selected cover image (will download when you Tag it).";
          registerMsg.className = "bp-msg muted";
        }
      },
      coverSearchBtn
    );
  });
  registerCoverFile?.addEventListener("change", () => {
    const file = registerCoverFile.files?.[0];
    if (!file) {
      if (registerCoverFileHint) registerCoverFileHint.classList.add("hidden");
      return;
    }
    const v = validateCoverFile(file);
    if (registerCoverFileHint) {
      registerCoverFileHint.classList.remove("hidden");
      registerCoverFileHint.textContent = v || "Ready to upload when you Tag it: " + file.name;
      registerCoverFileHint.className = v ? "bp-msg err" : "bp-msg muted";
    }
    if (!v) {
      const useCover = document.getElementById("register-use-cover");
      if (useCover) useCover.checked = false;
    }
  });
  document.getElementById("cover-modal-close")?.addEventListener("click", () => closeCoverModal());
  document.getElementById("cover-modal-images-btn")?.addEventListener("click", () => {
    if (!coverModalItemId) return;
    const src = coverModalItem || {};
    const coverModalSearchBtn = document.getElementById("cover-modal-images-btn");
    void searchCoverImages(
      coverModalItemId,
      {
        title: src.title || src.filename || "",
        authors: src.authors || "",
        isbn: src.isbn || "",
      },
      coverModalImages,
      coverModalMsg,
      async (row) => {
        try {
          if (coverModalMsg) {
            coverModalMsg.textContent = "Saving cover…";
            coverModalMsg.className = "bp-msg muted";
          }
          await applyCoverFromUrl(coverModalItemId, row.url);
          closeCoverModal();
          loadLibrary();
        } catch (err) {
          if (coverModalMsg) {
            coverModalMsg.textContent = err.message || "Could not save cover";
            coverModalMsg.className = "bp-msg err";
          }
        }
      },
      coverModalSearchBtn
    );
  });
  coverModalFile?.addEventListener("change", async () => {
    const file = coverModalFile.files?.[0];
    if (!file || !coverModalItemId) return;
    const v = validateCoverFile(file);
    if (v) {
      if (coverModalMsg) {
        coverModalMsg.textContent = v;
        coverModalMsg.className = "bp-msg err";
      }
      coverModalFile.value = "";
      return;
    }
    try {
      if (coverModalMsg) {
        coverModalMsg.textContent = "Uploading…";
        coverModalMsg.className = "bp-msg muted";
      }
      await uploadCoverFile(coverModalItemId, file);
      closeCoverModal();
      loadLibrary();
    } catch (err) {
      if (coverModalMsg) {
        coverModalMsg.textContent = err.message || "Upload failed";
        coverModalMsg.className = "bp-msg err";
      }
    } finally {
      coverModalFile.value = "";
    }
  });
  document.getElementById("register-close")?.addEventListener("click", () => {
    closeRegisterModal();
    document.body.classList.remove("bp-reader-open");
  });
  document.getElementById("register-cancel")?.addEventListener("click", () => {
    closeRegisterModal();
    document.body.classList.remove("bp-reader-open");
  });

  document.getElementById("lib-export-btn")?.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/library/export", {
        headers: { ...CSRF, ...(BP.state.authHeader ? { Authorization: BP.state.authHeader } : {}) },
      });
      if (!res.ok) throw new Error(res.statusText || "Export failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download =
        res.headers.get("Content-Disposition")?.match(/filename="([^"]+)"/)?.[1] ||
        "bookpup-catalog.json";
      a.click();
      URL.revokeObjectURL(url);
      BP.showAppToast("Kennel", "Catalog metadata exported", "ok");
    } catch (err) {
      BP.showAppToast("Export", err.message || "Export failed", "err");
    }
  });

  function applyShelvesFromResponse(data) {
    if (data && Array.isArray(data.shelves)) {
      libraryShelvesCache = data.shelves;
      if (activeShelfId && !libraryShelvesCache.some((s) => s.id === activeShelfId)) {
        activeShelfId = "";
        localStorage.removeItem(LIB_SHELF_KEY);
      }
      syncShelfSelect();
    }
  }

  function syncShelfSelect() {
    const sel = document.getElementById("lib-shelf-select");
    if (!sel) return;
    const prev = activeShelfId;
    sel.innerHTML = '<option value="">All catalogued</option>';
    libraryShelvesCache.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = s.name + (s.count ? " (" + s.count + ")" : "");
      sel.appendChild(opt);
    });
    sel.value = prev && libraryShelvesCache.some((s) => s.id === prev) ? prev : "";
    activeShelfId = sel.value || "";
  }

  function updateShelfToolbar() {
    const manage = document.getElementById("lib-shelf-manage-btn");
    if (manage) manage.disabled = !activeShelfId || isSharedBrowse() || !!BP.state.offlineOnly;
  }

  function setActiveShelf(id) {
    activeShelfId = id || "";
    if (activeShelfId && !isSharedBrowse()) localStorage.setItem(LIB_SHELF_KEY, activeShelfId);
    else localStorage.removeItem(LIB_SHELF_KEY);
    updateShelfToolbar();
    renderLibrary();
  }

  const shelfNameModal = document.getElementById("shelf-name-modal");
  const shelfNameInput = document.getElementById("shelf-name-input");
  const shelfNameTitle = document.getElementById("shelf-name-modal-title");
  const shelfNameMsg = document.getElementById("shelf-name-msg");

  function closeShelfNameModal() {
    shelfNameModal?.classList.add("hidden");
    if (shelfNameMsg) shelfNameMsg.textContent = "";
  }

  function openShelfNameModal(mode) {
    shelfNameModalMode = mode;
    if (shelfNameTitle) shelfNameTitle.textContent = mode === "rename" ? "Rename shelf" : "New shelf";
    if (shelfNameInput) {
      if (mode === "rename") {
        const shelf = libraryShelvesCache.find((s) => s.id === activeShelfId);
        shelfNameInput.value = shelf ? shelf.name : "";
      } else shelfNameInput.value = "";
    }
    shelfNameModal?.classList.remove("hidden");
    shelfNameInput?.focus();
  }

  const shelfManageModal = document.getElementById("shelf-manage-modal");
  const shelfManageList = document.getElementById("shelf-manage-list");
  const shelfManageTitle = document.getElementById("shelf-manage-modal-title");
  const shelfManageMsg = document.getElementById("shelf-manage-msg");

  function closeShelfManageModal() {
    shelfManageModal?.classList.add("hidden");
    if (shelfManageMsg) shelfManageMsg.textContent = "";
    if (shelfManageList) shelfManageList.innerHTML = "";
  }

  function openShelfManageModal() {
    const shelf = libraryShelvesCache.find((s) => s.id === activeShelfId);
    if (!shelf || !shelfManageList) return;
    if (shelfManageTitle) shelfManageTitle.textContent = "Manage shelf — " + shelf.name;
    const onShelf = new Set(shelf.item_ids || []);
    shelfManageList.innerHTML = "";
    const q = (libFilterInput?.value || "").trim().toLowerCase();
    const registered = libraryItemsCache.filter((it) => isRegisteredItem(it));
    const list = q
      ? registered.filter((it) => libraryItemMatchesFilter(it, q))
      : registered.slice().sort((a, b) => String(a.title || "").localeCompare(String(b.title || "")));
    list.forEach((item) => {
      const lab = document.createElement("label");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = item.id;
      cb.checked = onShelf.has(item.id);
      lab.appendChild(cb);
      const span = document.createElement("span");
      span.textContent = (item.title || "Untitled") + (item.authors ? " · " + item.authors : "");
      lab.appendChild(span);
      shelfManageList.appendChild(lab);
    });
    if (!list.length) {
      const p = document.createElement("p");
      p.className = "muted";
      p.textContent = "No catalogued bones yet.";
      shelfManageList.appendChild(p);
    }
    shelfManageModal?.classList.remove("hidden");
  }

  document.getElementById("lib-shelf-select")?.addEventListener("change", (ev) => {
    setActiveShelf(ev.target.value);
  });
  document.getElementById("lib-shelf-new-btn")?.addEventListener("click", () => openShelfNameModal("create"));
  document.getElementById("lib-shelf-manage-btn")?.addEventListener("click", () => openShelfManageModal());
  document.getElementById("shelf-name-modal-close")?.addEventListener("click", closeShelfNameModal);
  document.getElementById("shelf-name-cancel")?.addEventListener("click", closeShelfNameModal);
  document.getElementById("shelf-manage-modal-close")?.addEventListener("click", closeShelfManageModal);
  document.getElementById("shelf-rename-btn")?.addEventListener("click", () => {
    closeShelfManageModal();
    openShelfNameModal("rename");
  });
  document.getElementById("shelf-delete-btn")?.addEventListener("click", async () => {
    if (!activeShelfId) return;
    const shelf = libraryShelvesCache.find((s) => s.id === activeShelfId);
    if (!shelf) return;
    if (!window.confirm('Delete shelf "' + shelf.name + '"? Books stay in your kennel.')) return;
    try {
      const data = await BP.api("/api/library/shelves/" + encodeURIComponent(activeShelfId), {
        method: "DELETE",
        body: "{}",
      });
      activeShelfId = "";
      localStorage.removeItem(LIB_SHELF_KEY);
      applyShelvesFromResponse(data);
      closeShelfManageModal();
      renderLibrary();
      BP.showAppToast("Kennel", "Shelf deleted", "ok");
    } catch (err) {
      BP.showAppToast("Shelf", err.message || "Delete failed", "err");
    }
  });
  document.getElementById("shelf-name-form")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const name = (shelfNameInput?.value || "").trim();
    if (!name) return;
    try {
      let data;
      if (shelfNameModalMode === "rename" && activeShelfId) {
        data = await BP.api("/api/library/shelves/" + encodeURIComponent(activeShelfId), {
          method: "PATCH",
          body: JSON.stringify({ name }),
        });
      } else {
        data = await BP.api("/api/library/shelves", {
          method: "POST",
          body: JSON.stringify({ name }),
        });
        if (data.shelf?.id) {
          activeShelfId = data.shelf.id;
          localStorage.setItem(LIB_SHELF_KEY, activeShelfId);
        }
      }
      applyShelvesFromResponse(data);
      closeShelfNameModal();
      renderLibrary();
      BP.showAppToast("Kennel", shelfNameModalMode === "rename" ? "Shelf renamed" : "Shelf created", "ok");
    } catch (err) {
      if (shelfNameMsg) {
        shelfNameMsg.textContent = err.message || "Save failed";
        shelfNameMsg.className = "bp-msg err";
      }
    }
  });
  document.getElementById("shelf-manage-form")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (!activeShelfId || !shelfManageList) return;
    const itemIds = [...shelfManageList.querySelectorAll('input[type="checkbox"]:checked')].map((el) => el.value);
    try {
      const data = await BP.api(
        "/api/library/shelves/" + encodeURIComponent(activeShelfId) + "/items",
        {
          method: "PUT",
          body: JSON.stringify({ item_ids: itemIds }),
        }
      );
      applyShelvesFromResponse(data);
      closeShelfManageModal();
      renderLibrary();
      BP.showAppToast("Kennel", "Shelf updated", "ok");
    } catch (err) {
      if (shelfManageMsg) {
        shelfManageMsg.textContent = err.message || "Save failed";
        shelfManageMsg.className = "bp-msg err";
      }
    }
  });

  const libViewGrid = document.getElementById("lib-view-grid");
  const libViewList = document.getElementById("lib-view-list");
  const libViewFlow = document.getElementById("lib-view-flow");
  const libGroupBy = document.getElementById("lib-group-by");
  const libSortBy = document.getElementById("lib-sort-by");
  if (libViewGrid) libViewGrid.addEventListener("click", () => setLibraryLayoutMode("grid"));
  if (libViewList) libViewList.addEventListener("click", () => setLibraryLayoutMode("list"));
  if (libViewFlow) libViewFlow.addEventListener("click", () => { if (flowAvailable()) setLibraryLayoutMode("flow"); });
  libGroupBy?.addEventListener("change", () => setLibraryGroupMode(libGroupBy.value));
  libSortBy?.addEventListener("change", () => setLibrarySortMode(libSortBy.value));
  function updateLibFilterClearBtn() {
    const btn = document.getElementById("lib-filter-clear");
    if (btn) btn.disabled = !(libFilterInput?.value || "").trim();
  }

  const libOfflineOnlyInput = document.getElementById("lib-offline-only");
  if (libOfflineOnlyInput) {
    libOfflineOnlyInput.addEventListener("change", () => {
      libOfflineOnly = !!libOfflineOnlyInput.checked;
      renderLibrary();
    });
  }
  const libInProgressInput = document.getElementById("lib-in-progress-only");
  if (libInProgressInput) {
    libInProgressInput.checked = libInProgressOnly;
    libInProgressInput.addEventListener("change", () => {
      libInProgressOnly = !!libInProgressInput.checked;
      localStorage.setItem(LIB_PROGRESS_KEY, libInProgressOnly ? "1" : "0");
      renderLibrary();
    });
  }
  document.getElementById("lib-surprise-btn")?.addEventListener("click", () => surpriseMeRead());

  if (libFilterInput) {
    libFilterInput.addEventListener("input", () => {
      updateLibFilterClearBtn();
      renderLibrary();
    });
  }
  document.getElementById("lib-filter-clear")?.addEventListener("click", () => {
    if (!libFilterInput || !libFilterInput.value.trim()) return;
    libFilterInput.value = "";
    updateLibFilterClearBtn();
    renderLibrary();
  });
  updateLibraryToolbar();

  const freshUploadBtn = document.getElementById("fresh-upload-btn");
  const freshUploadInput = document.getElementById("fresh-upload-input");
  const freshUploadStatus = document.getElementById("fresh-upload-status");
  if (freshUploadBtn && freshUploadInput) {
    freshUploadBtn.addEventListener("click", () => freshUploadInput.click());
    freshUploadInput.addEventListener("change", async () => {
      const file = freshUploadInput.files && freshUploadInput.files[0];
      freshUploadInput.value = "";
      if (!file) return;
      if (freshUploadStatus) {
        freshUploadStatus.textContent = "Uploading " + file.name + "…";
        freshUploadStatus.className = "bp-msg muted";
      }
      try {
        const CHUNKED_UPLOAD_MIN = 3 * 1024 * 1024;
        let data;
        if (file.size > CHUNKED_UPLOAD_MIN) {
          setUploadProgress(0, "Uploading (chunked)…");
          data = await uploadImportSession(
            "/api/library/upload/session",
            "/api/library/upload/session/",
            [file]
          );
          hideUploadProgress();
        } else {
          const fd = new FormData();
          fd.append("file", file, file.name);
          const res = await fetch("/api/library/upload", {
            method: "POST",
            headers: { ...CSRF, ...(BP.state.authHeader ? { Authorization: BP.state.authHeader } : {}) },
            body: fd,
          });
          const text = await res.text();
          data = {};
          try {
            data = text ? JSON.parse(text) : {};
          } catch {
            data = {};
          }
          if (!res.ok) {
            throw new Error((data && data.error) || res.statusText || "Upload failed");
          }
        }
        if (freshUploadStatus) {
          freshUploadStatus.textContent = "Added to Fresh catches.";
          freshUploadStatus.className = "bp-msg muted";
        }
        BP.showAppToast("Kennel", (data.item && data.item.title) || file.name + " uploaded", "ok");
        loadLibrary();
      } catch (err) {
        hideUploadProgress();
        if (freshUploadStatus) {
          freshUploadStatus.textContent = err.message || "Upload failed";
          freshUploadStatus.className = "bp-msg err";
        }
        BP.showAppToast("Upload", err.message || "Could not upload file", "err");
      }
    });
  }

  const calibreImportBtn = document.getElementById("calibre-import-btn");
  const calibreImportInput = document.getElementById("calibre-import-input");
  if (calibreImportBtn && calibreImportInput) {
    calibreImportBtn.addEventListener("click", () => calibreImportInput.click());
    calibreImportInput.addEventListener("change", async () => {
      if (!calibreImportInput.files || !calibreImportInput.files.length) return;
      try {
        await importCalibreParts(calibreImportInput.files);
      } catch (err) {
        const status = document.getElementById("calibre-import-status");
        if (status) status.textContent = err.message || "Import failed";
      } finally {
        calibreImportInput.value = "";
      }
    });
  }

  const koreaderImportBtn = document.getElementById("koreader-import-btn");
  const koreaderImportInput = document.getElementById("koreader-import-input");
  if (koreaderImportBtn && koreaderImportInput) {
    koreaderImportBtn.addEventListener("click", () => koreaderImportInput.click());
    koreaderImportInput.addEventListener("change", async () => {
      if (!koreaderImportInput.files || !koreaderImportInput.files.length) return;
      const status = document.getElementById("koreader-import-status");
      if (status) status.textContent = "Uploading…";
      try {
        await importKoreaderSidecars(koreaderImportInput.files);
      } catch (err) {
        hideUploadProgress();
        if (status) status.textContent = err.message || "Import failed";
      } finally {
        koreaderImportInput.value = "";
      }
    });
  }

  const shareModal = document.getElementById("lib-share-modal");
  const shareIncomingEl = document.getElementById("lib-share-incoming");
  const shareOutgoingEl = document.getElementById("lib-share-outgoing");
  const shareGrantedEl = document.getElementById("lib-share-granted");
  const shareRequestForm = document.getElementById("lib-share-request-form");
  const shareRequestUser = document.getElementById("lib-share-request-user");
  const shareRequestMsg = document.getElementById("lib-share-request-msg");

  function shareRow(label, actions) {
    const row = document.createElement("div");
    row.className = "bp-share-row";
    const meta = document.createElement("span");
    meta.className = "bp-share-meta";
    meta.textContent = label;
    row.appendChild(meta);
    actions.forEach((btn) => row.appendChild(btn));
    return row;
  }

  function renderShareModalLists() {
    if (!shareIncomingEl) return;
    shareIncomingEl.innerHTML = "";
    const pendingIn = (librarySharesData.incoming || []).filter((g) => g.status === "pending");
    if (!pendingIn.length) {
      shareIncomingEl.innerHTML = '<p class="bp-msg muted">No pending requests.</p>';
    } else {
      pendingIn.forEach((g) => {
        const lend = document.createElement("button");
        lend.type = "button";
        lend.className = "bp-btn";
        lend.textContent = "Lend";
        lend.addEventListener("click", () => void respondShare(g.id, "accept", "lend"));
        const give = document.createElement("button");
        give.type = "button";
        give.className = "bp-btn";
        give.textContent = "Give";
        give.addEventListener("click", () => void respondShare(g.id, "accept", "give"));
        const decline = document.createElement("button");
        decline.type = "button";
        decline.className = "bp-btn";
        decline.textContent = "Decline";
        decline.addEventListener("click", () => void respondShare(g.id, "decline"));
        shareIncomingEl.appendChild(
          shareRow(g.requester + " wants to browse your kennel", [lend, give, decline])
        );
      });
    }
    shareOutgoingEl.innerHTML = "";
    const pendingOut = (librarySharesData.outgoing || []).filter((g) => g.status === "pending");
    if (!pendingOut.length) {
      shareOutgoingEl.innerHTML = '<p class="bp-msg muted">No outgoing requests.</p>';
    } else {
      pendingOut.forEach((g) => {
        const cancel = document.createElement("button");
        cancel.type = "button";
        cancel.className = "bp-btn";
        cancel.textContent = "Cancel";
        cancel.addEventListener("click", () => void cancelShareRequest(g.id));
        shareOutgoingEl.appendChild(shareRow("Waiting on " + g.owner, [cancel]));
      });
    }
    shareGrantedEl.innerHTML = "";
    const granted = librarySharesData.granted || [];
    if (!granted.length) {
      shareGrantedEl.innerHTML = '<p class="bp-msg muted">You are not sharing your kennel.</p>';
    } else {
      granted.forEach((g) => {
        const revoke = document.createElement("button");
        revoke.type = "button";
        revoke.className = "bp-btn";
        revoke.textContent = "Revoke";
        revoke.addEventListener("click", () => void respondShare(g.id, "revoke"));
        const mode = g.mode === "give" ? "give" : "lend";
        shareGrantedEl.appendChild(
          shareRow(g.requester + " (" + mode + ")", [revoke])
        );
      });
    }
  }

  async function respondShare(id, action, mode) {
    try {
      if (action === "accept") {
        await BP.api("/api/library/shares/" + id + "/accept", {
          method: "POST",
          body: JSON.stringify({ mode }),
        });
      } else if (action === "decline") {
        await BP.api("/api/library/shares/" + id + "/decline", { method: "POST", body: "{}" });
      } else if (action === "revoke") {
        await BP.api("/api/library/shares/" + id + "/revoke", { method: "POST", body: "{}" });
      }
      await loadLibrary();
    } catch (err) {
      BP.showAppToast("Sharing", err.message || "Request failed", "err");
    }
  }

  async function cancelShareRequest(id) {
    try {
      await BP.api("/api/library/shares/" + id, { method: "DELETE" });
      await loadLibrary();
    } catch (err) {
      BP.showAppToast("Sharing", err.message || "Could not cancel", "err");
    }
  }

  async function openShareModal() {
    const { users } = await BP.api("/api/users");
    const me = BP.state.sessionUsername;
    const choices = (users || []).filter((u) => u && u !== me);
    if (shareRequestUser) {
      shareRequestUser.innerHTML = choices
        .map((u) => '<option value="' + BP.escapeHtml(u) + '">' + BP.escapeHtml(u) + "</option>")
        .join("");
    }
    renderShareModalLists();
    if (shareRequestMsg) shareRequestMsg.textContent = "";
    shareModal?.classList.remove("hidden");
  }

  function closeShareModal() {
    shareModal?.classList.add("hidden");
  }

  document.getElementById("lib-sharing-btn")?.addEventListener("click", () => void openShareModal());
  document.getElementById("lib-share-modal-close")?.addEventListener("click", closeShareModal);
  document.getElementById("lib-browse-select")?.addEventListener("change", (ev) => {
    libraryBrowseOwner = ev.target.value || "";
    const hit = (librarySharesData.browsing || []).find((g) => g.owner === libraryBrowseOwner);
    libraryBrowseMode = hit ? hit.mode : null;
    loadLibrary().catch((err) => BP.showAppToast("Kennel", err.message, "err"));
  });
  if (shareRequestForm) {
    shareRequestForm.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const owner = shareRequestUser && shareRequestUser.value;
      if (!owner) return;
      if (shareRequestMsg) {
        shareRequestMsg.textContent = "Sending…";
        shareRequestMsg.className = "bp-msg muted";
      }
      try {
        await BP.api("/api/library/shares/request", {
          method: "POST",
          body: JSON.stringify({ owner }),
        });
        if (shareRequestMsg) shareRequestMsg.textContent = "Request sent.";
        await loadLibrary();
      } catch (err) {
        if (shareRequestMsg) {
          shareRequestMsg.textContent = err.message;
          shareRequestMsg.className = "bp-msg err";
        }
      }
    });
  }

  BP.bindSearchHistoryUx();
  BP.renderSearchHistoryUi();
  // exports
  BP.applyCoverFromUrl = applyCoverFromUrl;
  BP.applyMetadataCandidate = applyMetadataCandidate;
  BP.attachLibraryCard = attachLibraryCard;
  BP.attachLibraryItemActions = attachLibraryItemActions;
  BP.buildLibraryActionsHtml = buildLibraryActionsHtml;
  BP.catalogueEffectiveLayout = catalogueEffectiveLayout;
  BP.attachLibraryRow = attachLibraryRow;
  BP.clearCoverUrls = clearCoverUrls;
  BP.closeCoverModal = closeCoverModal;
  BP.closeRegisterModal = closeRegisterModal;
  BP.closeSendModal = closeSendModal;
  BP.coverUrlForItem = coverUrlForItem;
  BP.downloadLibraryItem = downloadLibraryItem;
  BP.focusLibraryItem = focusLibraryItem;
  BP.getLibraryItems = () => libraryItemsCache;
  BP.openRegisterModal = openRegisterModal;
  BP.downloadNameFromResponse = downloadNameFromResponse;
  BP.fillLibrarySection = fillLibrarySection;
  BP.fillRegisterForm = fillRegisterForm;
  BP.filterLibraryItems = filterLibraryItems;
  BP.fuzzyTokenMatch = fuzzyTokenMatch;
  BP.hideUploadProgress = hideUploadProgress;
  BP.importCalibreParts = importCalibreParts;
  BP.importKoreaderSidecars = importKoreaderSidecars;
  BP.isRegisteredItem = isRegisteredItem;
  BP.isStagedItem = isStagedItem;
  BP.libraryGroupMode = libraryGroupMode;
  BP.libraryItemMatchesFilter = libraryItemMatchesFilter;
  BP.libraryLayoutMode = libraryLayoutMode;
  BP.libraryMetaLine = libraryMetaLine;
  BP.librarySearchText = librarySearchText;
  BP.librarySortMode = librarySortMode;
  BP.loadLibrary = loadLibrary;
  BP.migrateLibraryViewPrefs = migrateLibraryViewPrefs;
  BP.openCoverModal = openCoverModal;
  BP.openEditMetadataModal = openEditMetadataModal;
  BP.openLibraryReader = openLibraryReader;
  BP.openRegisterModal = openRegisterModal;
  BP.openSendModal = openSendModal;
  BP.registerField = registerField;
  BP.renderCoverImageResults = renderCoverImageResults;
  BP.renderLibrary = renderLibrary;
  BP.renderLibraryCard = renderLibraryCard;
  BP.renderLibraryGroupBlock = renderLibraryGroupBlock;
  BP.renderLibraryList = renderLibraryList;
  BP.searchCoverImages = searchCoverImages;
  BP.searchRegisterMetadata = searchRegisterMetadata;
  BP.seriesGapHint = seriesGapHint;
  BP.setLibraryGroupMode = setLibraryGroupMode;
  BP.setLibraryLayoutMode = setLibraryLayoutMode;
  BP.setLibrarySortMode = setLibrarySortMode;
  BP.setUploadProgress = setUploadProgress;
  BP.sortLibraryItems = sortLibraryItems;
  BP.updateLibraryToolbar = updateLibraryToolbar;
  BP.uploadCoverFile = uploadCoverFile;
  BP.uploadImportSession = uploadImportSession;
  BP.validateCoverFile = validateCoverFile;
  BP.parseLibraryDeepLinkFromUrl = parseLibraryDeepLinkFromUrl;
  BP.tryFocusPendingLibraryItem = tryFocusPendingLibraryItem;
  BP.focusLibraryItem = focusLibraryItem;
})(window.BookPup);
