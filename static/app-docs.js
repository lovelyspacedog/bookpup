(function (BP) {
  "use strict";
  const CSRF = BP.CSRF;
  const COVER_MAX_BYTES = BP.COVER_MAX_BYTES;
  async function openAboutModal() {
    const modal = document.getElementById("about-modal");
    const body = document.getElementById("about-body");
    if (!modal || !body) return;
    modal.classList.remove("hidden");
    body.innerHTML = '<p class="muted">Loading…</p>';
    try {
      const res = await fetch("/static/about.md");
      if (!res.ok) throw new Error(res.statusText || "Could not load about");
      let html = formatChangelog(await res.text());
      try {
        const health = await BP.fetchPublic("/api/health");
        if (health && health.version) {
          html +=
            '<p class="muted bp-about-run">Running <strong>BookPup ' +
            BP.escapeHtml(health.version) +
            "</strong> on this server.</p>";
        }
      } catch {
        const ver = document.getElementById("bp-header-ver");
        const verText = ver?.textContent?.trim();
        if (verText) {
          html += '<p class="muted bp-about-run">' + BP.escapeHtml(verText) + "</p>";
        }
      }
      body.innerHTML = html;
      body.dataset.loaded = "1";
    } catch (err) {
      body.innerHTML =
        '<p class="bp-msg err">' + BP.escapeHtml(err.message || "Could not load about") + "</p>";
    }
    document.getElementById("about-modal-close")?.focus();
  }

  function closeAboutModal() {
    document.getElementById("about-modal")?.classList.add("hidden");
  }

  document.getElementById("about-open-login")?.addEventListener("click", () => void openAboutModal());
  document.getElementById("about-open-app")?.addEventListener("click", () => void openAboutModal());
  document.getElementById("about-modal-close")?.addEventListener("click", closeAboutModal);
  document.getElementById("about-modal")?.addEventListener("click", (ev) => {
    if (ev.target === ev.currentTarget) closeAboutModal();
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key !== "Escape") return;
    const modal = document.getElementById("about-modal");
    if (modal && !modal.classList.contains("hidden")) closeAboutModal();
  });

  function formatInlineMd(text) {
    return String(text)
      .split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
      .map((part) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return "<strong>" + BP.escapeHtml(part.slice(2, -2)) + "</strong>";
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return "<code>" + BP.escapeHtml(part.slice(1, -1)) + "</code>";
        }
        return BP.escapeHtml(part);
      })
      .join("");
  }

  function formatChangelog(text) {
    const parts = [];
    let inList = false;
    const closeList = () => {
      if (inList) {
        parts.push("</ul>");
        inList = false;
      }
    };
    text.split("\n").forEach((line) => {
      const t = line.trimEnd();
      if (!t) {
        closeList();
        return;
      }
      if (t.startsWith("# ")) {
        closeList();
        parts.push("<h2>" + BP.escapeHtml(t.slice(2)) + "</h2>");
        return;
      }
      if (t.startsWith("## ")) {
        closeList();
        parts.push("<h3>" + BP.escapeHtml(t.slice(3)) + "</h3>");
        return;
      }
      if (t.startsWith("- ")) {
        if (!inList) {
          parts.push('<ul class="bp-changelog-list">');
          inList = true;
        }
        parts.push("<li>" + formatInlineMd(t.slice(2)) + "</li>");
        return;
      }
      closeList();
      parts.push("<p>" + formatInlineMd(t) + "</p>");
    });
    closeList();
    return parts.join("");
  }

  function parseGuidePages(text) {
    const intro = [];
    const pages = [];
    let current = null;
    const flush = () => {
      if (current) {
        pages.push(current);
        current = null;
      }
    };
    text.split("\n").forEach((line) => {
      const t = line.trimEnd();
      if (t.startsWith("## ")) {
        flush();
        current = { title: t.slice(3).trim(), lines: [] };
        return;
      }
      if (!t) {
        if (current) current.lines.push("");
        else if (intro.length && intro[intro.length - 1] !== "") intro.push("");
        return;
      }
      if (t.startsWith("# ")) return;
      if (current) current.lines.push(t);
      else intro.push(t);
    });
    flush();
    return { intro, pages };
  }

  function renderGuidePageBody(lines) {
    const parts = [];
    let inList = false;
    const closeList = () => {
      if (inList) {
        parts.push("</ul>");
        inList = false;
      }
    };
    lines.forEach((line) => {
      const t = line.trimEnd();
      if (!t) {
        closeList();
        return;
      }
      if (t.startsWith("- ")) {
        if (!inList) {
          parts.push('<ul class="bp-changelog-list">');
          inList = true;
        }
        parts.push("<li>" + formatInlineMd(t.slice(2)) + "</li>");
        return;
      }
      closeList();
      parts.push("<p>" + formatInlineMd(t) + "</p>");
    });
    closeList();
    return parts.join("");
  }

  const GUIDE_PAGE_KEY = "bookpupGuidePage";
  let guidePages = [];
  let guideIntroHtml = "";
  let guidePageIndex = 0;
  let guideShowAll = false;

  function setGuidePagerChrome() {
    const label = document.getElementById("guide-page-label");
    const prev = document.getElementById("guide-prev");
    const next = document.getElementById("guide-next");
    const showAllBtn = document.getElementById("guide-show-all");
    if (showAllBtn) {
      showAllBtn.textContent = guideShowAll ? "By page" : "Show all";
    }
    if (guideShowAll) {
      if (label) label.textContent = "All " + guidePages.length + " pages";
      if (prev) prev.disabled = true;
      if (next) next.disabled = true;
      return;
    }
    if (label && guidePages.length) {
      label.textContent = pageIndexLabel(guidePageIndex + 1, guidePages.length);
    }
    if (prev) prev.disabled = guidePageIndex <= 0;
    if (next) next.disabled = guidePageIndex >= guidePages.length - 1;
  }

  function renderGuideAllView() {
    const el = document.getElementById("guide-body");
    if (!el || !guidePages.length) return;
    guideShowAll = true;
    el.classList.remove("bp-guide-page-view");
    el.classList.add("bp-guide-all-view");
    const parts = [];
    if (guideIntroHtml) parts.push(guideIntroHtml);
    guidePages.forEach((page) => {
      parts.push('<section class="bp-guide-all-section">');
      parts.push('<h2 class="bp-guide-page-title">' + BP.escapeHtml(page.title) + "</h2>");
      parts.push('<div class="bp-guide-section-body">' + renderGuidePageBody(page.lines) + "</div>");
      parts.push("</section>");
    });
    el.innerHTML = parts.join("");
    setGuidePagerChrome();
  }

  function renderGuidePageView() {
    const el = document.getElementById("guide-body");
    if (!el || !guidePages.length) return;
    guideShowAll = false;
    const page = guidePages[guidePageIndex];
    el.classList.remove("bp-guide-all-view");
    el.classList.add("bp-guide-page-view");
    el.innerHTML =
      (guidePageIndex === 0 && guideIntroHtml ? guideIntroHtml : "") +
      '<h2 class="bp-guide-page-title">' +
      BP.escapeHtml(page.title) +
      "</h2>" +
      '<div class="bp-guide-section-body">' +
      renderGuidePageBody(page.lines) +
      "</div>";
    setGuidePagerChrome();
    try {
      sessionStorage.setItem(GUIDE_PAGE_KEY, String(guidePageIndex));
    } catch {
      /* ignore */
    }
  }

  function pageIndexLabel(n, total) {
    return "Page " + n + " of " + total;
  }

  function bindGuidePager() {
    const prev = document.getElementById("guide-prev");
    const next = document.getElementById("guide-next");
    const showAllBtn = document.getElementById("guide-show-all");
    if (prev && !prev.dataset.bound) {
      prev.dataset.bound = "1";
      prev.addEventListener("click", () => {
        if (guideShowAll || guidePageIndex <= 0) return;
        guidePageIndex -= 1;
        renderGuidePageView();
      });
    }
    if (next && !next.dataset.bound) {
      next.dataset.bound = "1";
      next.addEventListener("click", () => {
        if (guideShowAll || guidePageIndex >= guidePages.length - 1) return;
        guidePageIndex += 1;
        renderGuidePageView();
      });
    }
    if (showAllBtn && !showAllBtn.dataset.bound) {
      showAllBtn.dataset.bound = "1";
      showAllBtn.addEventListener("click", () => {
        if (guideShowAll) renderGuidePageView();
        else renderGuideAllView();
      });
    }
  }

  async function loadMarkdownDoc(el, url, label) {
    if (!el || el.dataset.loaded === "1") return;
    el.innerHTML = '<p class="muted">Loading ' + label + "…</p>";
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(res.statusText);
      el.innerHTML = formatChangelog(await res.text());
      el.dataset.loaded = "1";
    } catch (err) {
      el.innerHTML =
        '<p class="bp-msg err">' + BP.escapeHtml(err.message || "Could not load " + label) + "</p>";
    }
  }

  async function loadGuide() {
    const el = document.getElementById("guide-body");
    if (!el || el.dataset.loaded === "1") return;
    el.innerHTML = '<p class="muted">Loading pup guide…</p>';
    try {
      const res = await fetch("/static/guide.md");
      if (!res.ok) throw new Error(res.statusText);
      const parsed = parseGuidePages(await res.text());
      guidePages = parsed.pages;
      guideIntroHtml = parsed.intro.length
        ? "<p class='muted'>" + formatInlineMd(parsed.intro.join(" ")) + "</p>"
        : "";
      let start = 0;
      try {
        const saved = parseInt(sessionStorage.getItem(GUIDE_PAGE_KEY) || "0", 10);
        if (!Number.isNaN(saved) && saved >= 0 && saved < guidePages.length) start = saved;
      } catch {
        /* ignore */
      }
      guidePageIndex = start;
      el.dataset.loaded = "1";
      bindGuidePager();
      renderGuidePageView();
    } catch (err) {
      el.innerHTML =
        '<p class="bp-msg err">' + BP.escapeHtml(err.message || "Could not load pup guide") + "</p>";
    }
  }

  async function loadChangelog() {
    return loadMarkdownDoc(
      document.getElementById("changelog-body"),
      "/static/changelog.md",
      "changelog"
    );
  }
  // exports
  BP.bindGuidePager = bindGuidePager;
  BP.closeAboutModal = closeAboutModal;
  BP.formatChangelog = formatChangelog;
  BP.formatInlineMd = formatInlineMd;
  BP.loadChangelog = loadChangelog;
  BP.loadGuide = loadGuide;
  BP.loadMarkdownDoc = loadMarkdownDoc;
  BP.openAboutModal = openAboutModal;
  BP.pageIndexLabel = pageIndexLabel;
  BP.parseGuidePages = parseGuidePages;
  BP.renderGuideAllView = renderGuideAllView;
  BP.renderGuidePageBody = renderGuidePageBody;
  BP.renderGuidePageView = renderGuidePageView;
  BP.setGuidePagerChrome = setGuidePagerChrome;
})(window.BookPup);
