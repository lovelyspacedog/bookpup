(function (BP) {
  "use strict";

  const SLOT_RADIUS = 5;
  const SLOT_COUNT = SLOT_RADIUS * 2 + 1;
  const DRAG_PX = 48;

  /** @type {WeakMap<HTMLElement, { abort: AbortController, index: number, items: object[] }>} */
  const instances = new WeakMap();

  let pendingFocusItemId = "";

  function clamp(n, lo, hi) {
    return Math.max(lo, Math.min(hi, n));
  }

  function spineTransform(offset) {
    const abs = Math.abs(offset);
    const rotate = offset * -42;
    const scale = Math.max(0.55, 1 - abs * 0.12);
    const tx = offset * 4.25;
    const z = 30 - abs * 8;
    const opacity = Math.max(0.35, 1 - abs * 0.14);
    return { rotate, scale, tx, z, opacity };
  }

  function destroy(container) {
    const inst = instances.get(container);
    if (inst) {
      inst.abort.abort();
      instances.delete(container);
    }
  }

  function setIndexByItemId(id) {
    pendingFocusItemId = id || "";
  }

  function attachCoverImg(img, item, coverUrlForItem, showReflection) {
    if (!img) return;
    img.alt = "";
    img.removeAttribute("src");
    img.classList.remove("bp-lib-cover--empty");
    const refl = img.closest(".bp-lib-flow__spine")?.querySelector(".bp-lib-flow__reflect img");
    if (refl) {
      refl.removeAttribute("src");
      refl.classList.remove("bp-lib-cover--empty");
    }
    if (!item) {
      img.classList.add("bp-lib-cover--empty");
      if (refl) refl.classList.add("bp-lib-cover--empty");
      return;
    }
    img.alt = String(item.title || item.filename || "Book cover");
    if (!item.has_cover) {
      img.classList.add("bp-lib-cover--empty");
      if (showReflection && refl) refl.classList.add("bp-lib-cover--empty");
      return;
    }
    coverUrlForItem(item).then((url) => {
      if (!url) return;
      img.src = url;
      if (showReflection && refl) refl.src = url;
    });
  }

  function mount(container, sortedItems, readable, hooks) {
    destroy(container);
    const items = sortedItems || [];
    const coverUrlForItem = hooks.coverUrlForItem;
    const buildActionsHtml = hooks.buildLibraryActionsHtml;
    const attachLibraryActions = hooks.attachLibraryActions;
    const onIndexChange = hooks.onIndexChange;

    let index = 0;
    if (pendingFocusItemId) {
      const ix = items.findIndex((it) => it.id === pendingFocusItemId);
      if (ix >= 0) index = ix;
      pendingFocusItemId = "";
    } else if (container.dataset.flowIndexItemId) {
      const ix = items.findIndex((it) => it.id === container.dataset.flowIndexItemId);
      if (ix >= 0) index = ix;
    }

    const root = document.createElement("div");
    root.className = "bp-lib-flow";
    root.innerHTML =
      '<div class="bp-lib-flow__chrome">' +
      '<button type="button" class="bp-btn bp-lib-flow__nav bp-lib-flow__nav--prev" aria-label="Previous book">‹</button>' +
      '<div class="bp-lib-flow__stage" tabindex="0" role="listbox" aria-label="Catalogued bones, cover flow">' +
      '<div class="bp-lib-flow__track"></div>' +
      "</div>" +
      '<button type="button" class="bp-btn bp-lib-flow__nav bp-lib-flow__nav--next" aria-label="Next book">›</button>' +
      "</div>" +
      '<div class="bp-lib-flow__detail">' +
      '<p class="bp-lib-flow__title" aria-live="polite"></p>' +
      '<p class="bp-lib-flow__meta muted"></p>' +
      '<div class="bp-lib-flow__actions bp-lib-card-actions"></div>' +
      "</div>";

    const stage = root.querySelector(".bp-lib-flow__stage");
    const track = root.querySelector(".bp-lib-flow__track");
    const titleEl = root.querySelector(".bp-lib-flow__title");
    const metaEl = root.querySelector(".bp-lib-flow__meta");
    const actionsEl = root.querySelector(".bp-lib-flow__actions");
    const prevBtn = root.querySelector(".bp-lib-flow__nav--prev");
    const nextBtn = root.querySelector(".bp-lib-flow__nav--next");

    const spines = [];
    for (let i = 0; i < SLOT_COUNT; i++) {
      const offset = i - SLOT_RADIUS;
      const spine = document.createElement("button");
      spine.type = "button";
      spine.className = "bp-lib-flow__spine";
      spine.dataset.offset = String(offset);
      spine.setAttribute("role", "option");
      spine.innerHTML =
        '<span class="bp-lib-flow__spine-inner">' +
        '<img class="bp-lib-cover bp-lib-flow__cover" width="120" height="160" decoding="async" alt="" />' +
        '<span class="bp-lib-flow__reflect" aria-hidden="true">' +
        '<img class="bp-lib-cover bp-lib-flow__cover" width="120" height="160" decoding="async" alt="" />' +
        "</span>" +
        '<span class="bp-lib-flow__format"></span>' +
        "</span>";
      track.appendChild(spine);
      spines.push(spine);
    }

    container.className = "bp-lib-items bp-lib-items--flow";
    container.innerHTML = "";
    container.appendChild(root);

    const abort = new AbortController();
    const sig = abort.signal;
    instances.set(container, { abort, index, items });

    function currentItem() {
      return items[index] || null;
    }

    function persistIndex() {
      const it = currentItem();
      if (it?.id) container.dataset.flowIndexItemId = it.id;
    }

    function updateDetail() {
      const item = currentItem();
      if (!item) {
        titleEl.textContent = "";
        metaEl.textContent = "";
        actionsEl.innerHTML = "";
        return;
      }
      titleEl.textContent = item.title || item.filename || "";
      const meta = hooks.libraryMetaLine ? hooks.libraryMetaLine(item) : "";
      const fmt = (item.format || "").toLowerCase().replace(/["']/g, "").replace(/^\./, "");
      metaEl.textContent =
        [meta, (fmt || "?").toUpperCase(), BP.bytes(item.bytes || 0)].filter(Boolean).join(" · ");
      actionsEl.innerHTML = buildActionsHtml(item, readable);
      attachLibraryActions(actionsEl, item, readable);
      if (item.id) actionsEl.dataset.libItemId = item.id;
    }

    function renderSpines() {
      spines.forEach((spine) => {
        const offset = parseInt(spine.dataset.offset, 10);
        const ix = index + offset;
        const item = ix >= 0 && ix < items.length ? items[ix] : null;
        const t = spineTransform(offset);
        spine.style.setProperty("--bp-flow-rotate", t.rotate + "deg");
        spine.style.setProperty("--bp-flow-scale", String(t.scale));
        spine.style.setProperty("--bp-flow-tx", t.tx + "rem");
        spine.style.setProperty("--bp-flow-z", String(t.z));
        spine.style.opacity = String(t.opacity);
        spine.classList.toggle("bp-lib-flow__spine--center", offset === 0);
        spine.classList.toggle("bp-lib-flow__spine--empty", !item);
        spine.disabled = !item;
        spine.setAttribute("aria-selected", offset === 0 && item ? "true" : "false");
        if (item?.id) spine.dataset.libItemId = item.id;
        else delete spine.dataset.libItemId;
        const fmtEl = spine.querySelector(".bp-lib-flow__format");
        if (fmtEl) {
          const fmt = item
            ? (item.format || "").toLowerCase().replace(/["']/g, "").replace(/^\./, "")
            : "";
          fmtEl.textContent = fmt ? fmt.toUpperCase() : "";
        }
        const img = spine.querySelector(".bp-lib-flow__spine-inner > .bp-lib-flow__cover");
        const showRefl = offset === 0;
        spine.querySelector(".bp-lib-flow__reflect")?.classList.toggle("hidden", !showRefl);
        attachCoverImg(img, item, coverUrlForItem, showRefl);
      });
      prevBtn.disabled = index <= 0;
      nextBtn.disabled = index >= items.length - 1;
      stage.setAttribute("aria-activedescendant", currentItem()?.id ? "bp-flow-opt-" + index : "");
      updateDetail();
      persistIndex();
      if (onIndexChange) onIndexChange(index, currentItem());
    }

    function step(delta) {
      if (!items.length) return;
      const next = clamp(index + delta, 0, items.length - 1);
      if (next === index) return;
      index = next;
      const inst = instances.get(container);
      if (inst) inst.index = index;
      renderSpines();
    }

    prevBtn.addEventListener("click", () => step(-1), { signal: sig });
    nextBtn.addEventListener("click", () => step(1), { signal: sig });

    spines.forEach((spine) => {
      const offset = parseInt(spine.dataset.offset, 10);
      spine.addEventListener(
        "click",
        () => {
          if (offset === 0) return;
          step(offset);
        },
        { signal: sig }
      );
    });

    stage.addEventListener(
      "keydown",
      (ev) => {
        if (ev.key === "ArrowLeft") {
          ev.preventDefault();
          step(-1);
        } else if (ev.key === "ArrowRight") {
          ev.preventDefault();
          step(1);
        } else if (ev.key === "Home") {
          ev.preventDefault();
          index = 0;
          renderSpines();
        } else if (ev.key === "End") {
          ev.preventDefault();
          index = items.length - 1;
          renderSpines();
        }
      },
      { signal: sig }
    );

    let dragStartX = null;
    stage.addEventListener(
      "pointerdown",
      (ev) => {
        if (ev.button !== 0) return;
        dragStartX = ev.clientX;
        stage.setPointerCapture(ev.pointerId);
      },
      { signal: sig }
    );
    stage.addEventListener(
      "pointerup",
      (ev) => {
        if (dragStartX == null) return;
        const dx = ev.clientX - dragStartX;
        dragStartX = null;
        if (Math.abs(dx) >= DRAG_PX) step(dx > 0 ? -1 : 1);
      },
      { signal: sig }
    );
    stage.addEventListener(
      "pointercancel",
      () => {
        dragStartX = null;
      },
      { signal: sig }
    );

    stage.addEventListener(
      "wheel",
      (ev) => {
        if (Math.abs(ev.deltaX) < Math.abs(ev.deltaY)) return;
        if (Math.abs(ev.deltaX) < 8) return;
        ev.preventDefault();
        step(ev.deltaX > 0 ? 1 : -1);
      },
      { signal: sig, passive: false }
    );

    renderSpines();
    return { getIndex: () => index, setIndex: (i) => { index = clamp(i, 0, Math.max(0, items.length - 1)); renderSpines(); } };
  }

  BP.LibraryFlow = { mount, destroy, setIndexByItemId };
})(window.BookPup);