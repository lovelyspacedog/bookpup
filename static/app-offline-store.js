(function (BP) {
  "use strict";

  const DB_NAME = "bookpup-offline-v1";
  const DB_VER = 1;
  const STORE_BOOKS = "books";
  const STORE_SYNC = "reading_sync";
  const DEVICE_QUOTA_BYTES = 2 * 1024 * 1024 * 1024;
  const OFFLINE_FORMATS = new Set(["epub", "pdf"]);
  const blobUrlCache = new Map();

  let dbPromise = null;

  function canKeepOffline(item) {
    if (!item || !item.id) return false;
    const src = (item.source || "").toLowerCase();
    if (src !== "registered" && src !== "calibre_import") return false;
    const fmt = (item.format || "").toLowerCase().replace(/^\./, "");
    return OFFLINE_FORMATS.has(fmt);
  }

  function openDb() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise((resolve, reject) => {
      if (!("indexedDB" in self)) {
        reject(new Error("IndexedDB unavailable"));
        return;
      }
      const req = indexedDB.open(DB_NAME, DB_VER);
      req.onerror = () => reject(req.error || new Error("Could not open offline storage"));
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(STORE_BOOKS)) {
          db.createObjectStore(STORE_BOOKS, { keyPath: "item_id" });
        }
        if (!db.objectStoreNames.contains(STORE_SYNC)) {
          const st = db.createObjectStore(STORE_SYNC, { keyPath: "id", autoIncrement: true });
          st.createIndex("item_id", "item_id", { unique: false });
        }
      };
      req.onsuccess = () => resolve(req.result);
    });
    return dbPromise;
  }

  async function withStore(mode, name, fn) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(name, mode);
      const st = tx.objectStore(name);
      Promise.resolve(fn(st, tx))
        .then(resolve)
        .catch(reject);
      tx.onerror = () => reject(tx.error || new Error("Offline storage error"));
      tx.onabort = () => reject(tx.error || new Error("Offline storage aborted"));
    });
  }

  async function listMeta() {
    return withStore("readonly", STORE_BOOKS, (st) => {
      return new Promise((resolve, reject) => {
        const req = st.getAll();
        req.onsuccess = () => {
          const rows = (req.result || []).map((r) => ({
            item_id: r.item_id,
            title: r.title,
            format: r.format,
            bytes: r.bytes,
            savedAt: r.savedAt,
            has_cover: !!r.has_cover,
            owner: r.owner || "",
          }));
          resolve(rows);
        };
        req.onerror = () => reject(req.error);
      });
    });
  }

  async function has(itemId) {
    const row = await withStore("readonly", STORE_BOOKS, (st) => {
      return new Promise((resolve, reject) => {
        const req = st.get(itemId);
        req.onsuccess = () => resolve(req.result || null);
        req.onerror = () => reject(req.error);
      });
    });
    return !!row;
  }

  async function totalBytes() {
    const rows = await listMeta();
    return rows.reduce((n, r) => n + (r.bytes || 0), 0);
  }

  async function getRecord(itemId) {
    return withStore("readonly", STORE_BOOKS, (st) => {
      return new Promise((resolve, reject) => {
        const req = st.get(itemId);
        req.onsuccess = () => resolve(req.result || null);
        req.onerror = () => reject(req.error);
      });
    });
  }

  function revokeBlobUrl(itemId) {
    const old = blobUrlCache.get(itemId);
    if (old) {
      URL.revokeObjectURL(old);
      blobUrlCache.delete(itemId);
    }
  }

  async function blobUrlFor(itemId) {
    const cached = blobUrlCache.get(itemId);
    if (cached) return cached;
    const row = await getRecord(itemId);
    if (!row || !row.file) throw new Error("No offline copy for this book");
    const url = URL.createObjectURL(row.file);
    blobUrlCache.set(itemId, url);
    return url;
  }

  async function coverBlobUrlFor(itemId) {
    const row = await getRecord(itemId);
    if (!row?.cover) return null;
    return URL.createObjectURL(row.cover);
  }

  async function getReadingState(itemId) {
    const row = await getRecord(itemId);
    if (!row) return { bookmarks: [], location: null };
    return {
      bookmarks: Array.isArray(row.bookmarks) ? row.bookmarks : [],
      location: row.location || null,
    };
  }

  async function setReadingState(itemId, partial) {
    const row = await getRecord(itemId);
    if (!row) return;
    if (partial.location !== undefined) row.location = partial.location;
    if (partial.bookmarks !== undefined) row.bookmarks = partial.bookmarks;
    await withStore("readwrite", STORE_BOOKS, (st) => st.put(row));
  }

  async function enqueueReadingSync(itemId, location) {
    await withStore("readwrite", STORE_SYNC, (st) =>
      st.add({ item_id: itemId, location, createdAt: Date.now() })
    );
  }

  async function flushReadingSync(authHeader) {
    if (!authHeader || !navigator.onLine) return 0;
    const db = await openDb();
    const rows = await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_SYNC, "readonly");
      const req = tx.objectStore(STORE_SYNC).getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    });
  let flushed = 0;
    for (const row of rows) {
      try {
        const res = await fetch("/api/library/" + encodeURIComponent(row.item_id) + "/reading", {
          method: "POST",
          headers: {
            ...BP.CSRF,
            Authorization: authHeader,
            "Content-Type": "application/json",
            "X-Bookpup": "1",
          },
          body: JSON.stringify({ location: row.location }),
        });
        if (!res.ok) continue;
        await withStore("readwrite", STORE_SYNC, (st) => {
          return new Promise((resolve, reject) => {
            const del = st.delete(row.id);
            del.onsuccess = () => resolve();
            del.onerror = () => reject(del.error);
          });
        });
        flushed += 1;
      } catch {
        /* keep queue */
      }
    }
    return flushed;
  }

  async function removeBook(itemId) {
    revokeBlobUrl(itemId);
    await withStore("readwrite", STORE_BOOKS, (st) => st.delete(itemId));
  }

  async function downloadBook(item, authHeader) {
    if (!canKeepOffline(item)) throw new Error("Only catalogued EPUB or PDF can be kept offline");
    const view = await BP.api("/api/library/" + encodeURIComponent(item.id) + "/view", {
      method: "POST",
      body: "{}",
    });
    const readRes = await fetch(view.read_url, {
      headers: {
        ...(authHeader ? { Authorization: authHeader } : {}),
        Accept: "application/epub+zip,application/pdf,*/*",
      },
    });
    if (!readRes.ok) throw new Error(readRes.statusText || "Could not download book");
    const file = await readRes.blob();
    if (file.size < 16) throw new Error("Downloaded file is empty");
    const existing = await totalBytes();
    const prev = await getRecord(item.id);
    const prevBytes = prev?.bytes || 0;
    if (existing - prevBytes + file.size > DEVICE_QUOTA_BYTES) {
      throw new Error("This device offline quota is full — remove another offline copy first");
    }
    let cover = null;
    if (item.has_cover) {
      try {
        const cRes = await fetch("/api/library/" + encodeURIComponent(item.id) + "/cover", {
          headers: authHeader ? { Authorization: authHeader } : {},
        });
        if (cRes.ok) cover = await cRes.blob();
      } catch {
        /* optional */
      }
    }
    let reading = { bookmarks: [], location: null };
    try {
      const rRes = await fetch("/api/library/" + encodeURIComponent(item.id) + "/reading", {
        headers: authHeader ? { Authorization: authHeader } : {},
      });
      if (rRes.ok) reading = await rRes.json();
    } catch {
      /* optional */
    }
    revokeBlobUrl(item.id);
    const owner = BP.state?.sessionUser || "";
    const record = {
      item_id: item.id,
      title: view.title || item.title || item.filename,
      format: view.format,
      bytes: file.size,
      savedAt: Date.now(),
      has_cover: !!cover,
      owner,
      file,
      cover,
      location: reading.location || null,
      bookmarks: reading.bookmarks || [],
    };
    await withStore("readwrite", STORE_BOOKS, (st) => st.put(record));
    return record;
  }

  async function pseudoLibraryItems() {
    const metas = await listMeta();
    return metas.map((m) => ({
      id: m.item_id,
      title: m.title,
      filename: m.title,
      format: m.format,
      bytes: m.bytes,
      source: "registered",
      has_cover: m.has_cover,
      offline_only: true,
    }));
  }

  async function viewMeta(itemId) {
    const row = await getRecord(itemId);
    if (!row) return null;
    return {
      ok: true,
      id: row.item_id,
      format: row.format,
      title: row.title,
      read_url: await blobUrlFor(itemId),
      offline: true,
    };
  }

  BP.offlineBooks = {
    canKeepOffline,
    listMeta,
    has,
    totalBytes,
    deviceQuotaBytes: DEVICE_QUOTA_BYTES,
    downloadBook,
    removeBook,
    blobUrlFor,
    coverBlobUrlFor,
    getReadingState,
    setReadingState,
    enqueueReadingSync,
    flushReadingSync,
    pseudoLibraryItems,
    viewMeta,
    offlineFormats: OFFLINE_FORMATS,
  };

  window.addEventListener("online", () => {
    const auth = BP.state?.authHeader;
    if (auth) void BP.offlineBooks.flushReadingSync(auth);
  });
})(window.BookPup);