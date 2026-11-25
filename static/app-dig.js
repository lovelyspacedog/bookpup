(function (BP) {
  "use strict";

  const root = document.getElementById("dig-sections");
  const msgEl = document.getElementById("dig-msg");
  let loaded = false;

  function setMsg(text, kind) {
    if (!msgEl) return;
    if (!text) {
      msgEl.textContent = "";
      msgEl.className = "bp-msg muted hidden";
      return;
    }
    msgEl.textContent = text;
    msgEl.className = "bp-msg " + (kind || "muted");
    msgEl.classList.remove("hidden");
  }

  function warningCopy(code) {
    if (code === "catalog_empty") {
      return "Tag a few books in Kennel — Dig picks taste from your catalogued bones.";
    }
    if (code === "openlibrary_unavailable") {
      return "Open Library did not respond — along-the-trail picks may be empty.";
    }
    return "";
  }

  function renderRow(item) {
    const card = document.createElement("article");
    card.className = "bp-card bp-dig-card";
    const title = BP.escapeHtml(item.title || "");
    const authors = item.authors ? "<p class=\"muted bp-dig-card__authors\">" + BP.escapeHtml(item.authors) + "</p>" : "";
    const reason = item.reason
      ? "<p class=\"bp-dig-card__reason muted\">" + BP.escapeHtml(item.reason) + "</p>"
      : "";
    const badge = item.in_kennel
      ? '<span class="bp-dig-badge">In kennel</span>'
      : "";
    const cover = item.cover_url
      ? '<img class="bp-dig-card__cover" src="' +
        BP.escapeHtml(item.cover_url) +
        '" alt="" loading="lazy" decoding="async" />'
      : "";
    const q = item.sniff_query || item.title || "";
    card.innerHTML =
      '<div class="bp-dig-card__row">' +
      cover +
      '<div class="bp-dig-card__main">' +
      "<h3 class=\"bp-dig-card__title\">" +
      title +
      "</h3>" +
      authors +
      reason +
      badge +
      "</div></div>" +
      '<button type="button" class="bp-btn bp-dig-sniff">Sniff this</button>';
    card.querySelector(".bp-dig-sniff")?.addEventListener("click", () => {
      BP.sniffWithQuery?.(q);
    });
    return card;
  }

  function renderSection(section) {
    const wrap = document.createElement("section");
    wrap.className = "bp-dig-section";
    const h = document.createElement("h2");
    h.className = "bp-dig-section__title";
    h.textContent = section.title || "";
    wrap.appendChild(h);
    const items = section.items || [];
    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Nothing here yet.";
      wrap.appendChild(empty);
    } else {
      const list = document.createElement("div");
      list.className = "bp-dig-list";
      items.forEach((item) => list.appendChild(renderRow(item)));
      wrap.appendChild(list);
    }
    if (section.id === "bestsellers" && section.meta) {
      const foot = document.createElement("p");
      foot.className = "muted bp-dig-foot";
      const parts = [];
      if (section.meta.updated) parts.push("List updated " + section.meta.updated);
      if (section.meta.attribution) parts.push(section.meta.attribution);
      foot.textContent = parts.join(" — ");
      wrap.appendChild(foot);
    }
    return wrap;
  }

  async function loadDigPicks() {
    if (!root) return;
    if (!loaded) {
      root.innerHTML = '<p class="muted">Digging up ideas…</p>';
    }
    setMsg("", "");
    try {
      const data = await BP.api("/api/dig-picks");
      loaded = true;
      const sections = data.sections || [];
      root.innerHTML = "";
      sections.forEach((sec) => root.appendChild(renderSection(sec)));
      const warnLines = (data.warnings || []).map(warningCopy).filter(Boolean);
      if (warnLines.length) setMsg(warnLines.join(" "), "info");
    } catch (err) {
      root.innerHTML = "";
      setMsg(err.message || "Could not load Dig picks", "err");
    }
  }

  BP.loadDigPicks = loadDigPicks;
})(window.BookPup);