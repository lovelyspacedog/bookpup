# BookPup changelog

## 1.4.9

- **UX:** **What's new** — pre-**1.3** release notes (**0.x**, **1.0.x**, **1.1.x**, **1.2.x**) rolled into one abridged history block (same style as **1.3.0**–**1.3.59**).

## 1.4.8

- **Reader:** **Keep offline** on catalogued **EPUB** and **PDF** — device storage, **On this device** filter, and read when the server is down (position syncs when you are back online).
- **UX:** PWA shell precaches reader assets; offline reopen shows your downloaded titles in **Kennel**.

## 1.4.7

- **UX:** **Add to home screen** install box — thicker cyan border so it stands out on sign-in and **Your tag**.

## 1.4.6

- **UX:** **Install BookPup** on the sign-in page when your browser supports add-to-home-screen (still under **Your tag** too).

## 1.4.5

- **Fix:** **Pup guide** page 1 — **Walk the Trail** link at the bottom for new pups (not only after finishing the tour).

## 1.4.4

- **UX:** Tighter trimmed logos on sign-in and header so the mark isn’t swallowed by empty padding in the icon files.

## 1.4.3

- **UX:** Larger sign-in and header logos (crisp flat mark in the header, icon beside the title on login).

## 1.4.2

- **UX:** BookPup logo on the sign-in card and a small mark beside the header title.

## 1.4.1

- **UX:** New **Neon Kennel** home-screen icon (hound + book), maskable Android variant, and sharper tab favicon.

## 1.4.0

- **UX:** Install BookPup on your phone — PWA with home-screen icon; **Your tag** shows install help and what works offline vs online.
- **UX:** Offline **Pup guide** and **What's new** when you have no connection (shell only — sniff, kennel, and reader still need the server).

## 1.3.110

- **Fix:** **Reader** — comic one-finger pan on mobile at 100% zoom too (not only when magnified).

## 1.3.109

- **Fix:** **Reader** — comic CBZ/CBR pan with one finger on mobile after zoom (pinch or +/- still work).

## 1.3.108

- **UX:** **Walk the Trail again** only on **Pup guide** page 1 — removed from **Sniff** (including mobile dock).
- **Fix:** **Fresh catch** toast/desktop alert no longer replays after tag/toss, sign-out, or reload; remembered per account with a short backfill window for mid-fetch refresh.

## 1.3.107

- **Fix:** **Walk the Trail** **BugBot & FeatureCat** — mobile coach docks above the tab bar so bot rows stay tappable.

## 1.3.106

- **Fix:** **Walk the Trail** — **Pack channel** (and bot sidebar) coach scrolls back to the channel button on mobile after the Pack chat showcase; top-dock “loose” offset only on mobile.

## 1.3.105

- **UX:** After you dismiss **New here?**, **Walk the Trail again** sits at the bottom of **Sniff** (above the tab bar on mobile).

## 1.3.104

- **Fix:** **Walk the Trail** Pack chat mobile scroll — no coach scroll fighting the one slow showcase (flicker at step entry).

## 1.3.103

- **UI:** **Kennel** toolbar on mobile — one logical row each for browse/sharing, export, grid/list, group, and sort; filter stays on its own line.

## 1.3.102

- **UX:** **Walk the Trail** — on mobile, **Pack chat** gently scrolls through the tab; **Trail complete** drops pup/paw/celebration confetti (respects reduced motion).

## 1.3.101

- **Fix:** **Walk the Trail** mobile coach placement (Den scroll, Fetch/Queue/Tag/Pack channel layout, Catalogued scroll); cleanup targets your practice book in **Catalogued bones** or Fresh catches; finish opens Pup guide page 1.

## 1.3.100

- **Fix:** **Walk the Trail** Fresh catches no longer snaps back to the top while you scroll; cleanup coach docks at the bottom; **Remove fresh catch** sits above the tour overlay.

## 1.3.99

- **Fix:** **Walk the Trail** Fresh catches starts at the top of Kennel (you scroll to the practice file); **Remove practice book?** returns to Kennel and highlights **Toss**.

## 1.3.98

- **Fix:** **Walk the Trail** Pack chat steps — coach pins to the top; **BugBot & FeatureCat** highlights the bot rows, not the sidebar blurb over the message feed.

## 1.3.97

- **UX:** **Walk the Trail** — Fetch queue stays on Queue; Fresh catches scrolls to your practice file; new **Pack chat** steps (household channel, DMs, BugBot/FeatureCat); finish opens Pup guide page 12.

## 1.3.96

- **Fix:** **Walk the Trail** Tag step — form sits above the coach overlay, uses a short tutorial field set, and you can scroll to **Tag it**.

## 1.3.95

- **Fix:** **Walk the Trail** Kennel → Tag — no auto-open Tag modal; coach spotlights the practice **Tag** button (then the form after you open it).

## 1.3.94

- **Fix:** **Walk the Trail** practice **Fetch** reuses your existing tutorial MOBI when the fixture bytes are already in the kennel (repeat tours or a new practice title).

## 1.3.93

- **Fix:** **Walk the Trail** — entering **Den chatter** no longer scrolls down to the results table and back; the coach card sits above the panel so chat lines stay visible.

## 1.3.92

- **UX:** **Walk the Trail again** on Sniff (after first completion), onboard banner, and Pup guide pages 1–2.
- **UX:** Open results draft line matches practice sniff during the tour; Tag coach aligns when the register modal opens.

## 1.3.91

- **Fix:** **Walk the Trail** tutorial MOBI ships with the app (`lib/fixtures/`) so practice **Fetch** works on production.
- **UX:** **Walk the Trail** shows fetch errors in the coach card with **Retry**; stale sniff messages clear when you restart the tour.

## 1.3.90

- **Fix:** **Walk the Trail** explain steps (Den chatter, filter, queue) use a top coach card on mobile so the highlighted control stays visible below.

## 1.3.89

- **Fix:** **Walk the Trail** coach card stays readable on **Den chatter** (highlight no longer stacks over the tip on mobile).

## 1.3.88

- **Fix:** **Walk the Trail** advances after practice **Fetch** (explicit step transition, touch handler, reuse existing Fresh catch on repeat).

## 1.3.87

- **Fix:** **Walk the Trail** spotlight tracks the active control after scroll (query, Sniff source, fetch row) instead of sticking on the Sniff tab.

## 1.3.86

- **UX:** **New here?** banner explains **Walk the Trail** as step-by-step tutorial mode vs **Pup guide** reading.

## 1.3.85

- **Fix:** **Walk the Trail** — practice **Fetch** works on mobile (results above overlay; capture handler; spotlight no longer eats taps).

## 1.3.84

- **Fix:** **Walk the Trail** coach card stays on screen on mobile (docked above tab bar); spotlight/tip use viewport positioning so Next and targets respond to taps.

## 1.3.83

- **UX:** **Walk the Trail** — bold onboard link; step-by-step coach marks with practice sniff, mock Den chatter, tutorial MOBI fetch, tag step, optional cleanup, then Pup guide page 2. Restart from Pup guide page 1.

## 1.3.82

- **UX:** **Pup guide** rewritten for lay readers — defines sniff, fetch, catalog, and read up front; less jargon; Calibre, KOReader, and library sharing moved to later pages.

## 1.3.81

- **UX:** Align labels and help with the UI — **Fresh catches** → **Tag** → **Catalogued bones**, **Scheduled sniff**, lend (read and download), **Study** (not Reader AI), **Pup guide** + **README** / **About** refreshed.

## 1.3.80

- **Pack:** **BugBot** / **FeatureCat** intros are instant; only confirmations wait 2–5 s. Type **clear** in either bot thread to wipe the chat and show the intro again (tip on each confirmation).

## 1.3.79

- **Pack:** **BugBot** and **FeatureCat** wait 2–5 seconds before intro or confirmation replies (inbox still saves immediately).

## 1.3.78

- **Pack:** **FeatureCat** — feature requests in Pack chat (intro on first open, always online); admins triage on **Pack roster** → **Feature inbox**.

## 1.3.77

- **Pack:** **BugBot** always shows an online dot in Pack chat.

## 1.3.76

- **Pack:** **BugBot** in Pack chat — first open sends a how-to intro; pups DM bug reports; admins read them on **Pack roster** → **Bug inbox**.

## 1.3.75

- **UX:** **Fetch queue** tab opens on **All** (not **Active** only).

## 1.3.74

- **Fix:** **Kennel** toolbar wraps inside the page column instead of spilling past the quota card on the right.

## 1.3.73

- **Fix:** Scheduled sniff **?** tooltip describes BookPup DMs, not household ntfy.

## 1.3

Patch line **1.3.0**–**1.3.59** (live patch on **What’s new** and `GET /api/health`).

## 1.3.72

- **Fix:** **Pack chat** unread badges render beside pup names (grid layout); opening the **Pack chat** tab always returns to **everyone**.
- **Fix:** tab unread only bumps for DMs you receive (not your own sends).

## 1.3.71

- **UX:** **Pack chat** sidebar — unread count badge beside each pup (and **BookPup**) with new private messages; clears when you open that thread.

## 1.3.70

- **Kennel:** whole-kennel sharing — request browse access; owner accepts **lend** (read/download) or **give** (add copies on demand); **Sharing** panel and **Browsing** picker; Pack chat ping on requests.

## 1.3.69

- **UX:** on mobile, **Head out** moved from the tab bar into **More** (desktop header **Head out** unchanged).

## 1.3.68

- **UX:** mobile **Sniff source** short labels still show network/channel (e.g. **Main trail · IRCHighway #ebooks**); desktop keeps full text including “recommended” and xdccsearch notes.

## 1.3.67

- **UX:** **Sniff source** dropdown uses short names on mobile; full labels on wider screens; hints unchanged.

## 1.3.66

- **UX:** removed header ZIP / weather widget and `GET /api/weather` (wttr.in).

## 1.3.65

- **Fix:** **Pack chat** **Remove** no longer stretches full width (overrides card button styling).

## 1.3.64

- **UX:** **Pack chat** sidebar — **Pack chat · everyone** for the main channel; pup rows show **Open PM →** (active thread highlighted).
- **UX:** pack chat **Remove** sits on the far right of each line (compact, one-line height).

## 1.3.63

- **UX:** **Pack chat** private messages — click a pup (or **BookPup**) in the sidebar; **Pack** pill returns to the group channel.
- **Sniff:** **Scheduled sniff** new-row alerts go to the bookmark owner’s **BookPup** PM instead of household ntfy (download ntfy unchanged).

## 1.3.62

- **UX:** **Pack chat** tab — household group chat with who’s online; delete your own messages; admins can remove any message or clear the thread (not IRC **Den chatter**).

## 1.3.61

- **Sniff:** **Scheduled sniff** on the sniff card collapses by default (compact summary; **On · …** when active).

## 1.3.60

- **Sniff:** **Scheduled sniff** on the main sniff card (Enable + interval, **?** tooltip); ties to a matching bookmark or creates one when you turn it on.

## 1.3.59

- **UI:** **Open results & bookmarks** — compact Load/Remove/↑↓ row (no full-width button stack); clearer bookmark cards and form separator.

## 1.3.58

- **Sniff:** **Schedule sniff** on bookmarks — household server re-runs the bookmark query on an interval, ntfy when new rows appear (respects IRC idle queue; Soulseek caps).
- **Sniff:** optional config `sniff_schedule_tick_seconds`, `sniff_schedule_min_interval_hours`, `sniff_schedule_max_per_user`.

- **UX:** signed-in header shows **vX.Y.Z · Enter ZIP:** with a borderless field; **Enter** fetches a one-line [wttr.in](https://wttr.in) forecast for a US ZIP (`GET /api/weather`).
- **UX:** header version sits smaller and lower beside **ZIP:** (spaced entry); forecast keeps the version visible.
- **UX:** header weather centers after lookup; forecast uses wttr city name instead of ZIP.
- **UX:** click header forecast to toggle °F/°C; double-click clears it and brings back **ZIP:** entry.
- **UX:** version badge sits beside **BookPup**; weather stays centered on its own.

- **Security:** staging downloads scoped to job owner; `..` blocked in staging ids; library quota includes covers; SSRF guards on cover-from-URL and optional `ntfy_server`; atomic JSON for accounts, catalog, and reading state; safer zip extract; login field no longer prefilled from server.
- **UI:** readable native select menus; **About BookPup** from the header/logo; sniff toolbar sticks above the table, compact fetch buttons, bookmarks below results; **New here?** banner; **Den chatter** hidden until IRC activity; empty sniff card shows **Open results & bookmarks** only; cover/tag lookups show spinners; **What to sniff for** superbar (recent queries, **Clear** outside the field).
- **Sniff:** **Sniff source** labels and hints; default **Main trail · IRCHighway #ebooks**; **IRCHighway #bookz** removed; paginated filtered results with type badges; **Wipe matches** respects active filters; live queue/connect status; reliable sniff/fetch polling and queue backfill; **EPUB only** auto-off when it would hide every row; Undernet catalogue titles (no bare IDs).
- **Sniff — XDCC index:** [xdccsearch.com](https://xdccsearch.com) metasearch channel (warez yard, separate from IRC **All networks**); inline `POST /api/search` results; Den logs for index searches.
- **Sniff — Soulseek:** **Peer trail · Soulseek (slskd)** on Expedition; inline sniff; auto-reconnect when slskd is disconnected; per-user and household caps (`soulseek_limits` on accounts); health reports `soulseek.server_logged_in` / `server_state`.
- **Fetch:** XDCC index DCC to pack bots; **bot preflight** and two-phase DCC wait (`download_offer_timeout`, `bot_status_stale_seconds`); fast fail on **!get** refusals, **0 matches**, and stale bots; **Project Gutenberg** HTTPS fallback (EPUB first) with Den **Project Gutenberg fallback:** lines; Soulseek transfer completion and on-disk path fixes.
- **Kennel:** finished downloads land in **Fresh catches** (no **Got a bone!**); **Stash in kennel** confirms before **Tag this book**; ghost row cleanup after account wipe; list filter **Clear**; uploads/stash/import match expanded **Read** formats.
- **Reader:** MOBI/AZW paginated dual-page; CBZ/CBR pan/zoom/dual-page (per-page on CBZ); **FB2, DJVU, LIT, CHM, RTF, CB7**, sandboxed **Markdown/HTML** via Calibre; comic **Debug…** on archive errors.
- **Den / queue:** feed owner fix so IRC lines show; sniff/download backfill when the browser misses polls; clearer notes when filters hide all rows.
- **Config / health:** `xdcc_search_enabled`, `xdcc_search_url`, `BOOKPUP_XDCC_MOCK`; optional fetch timeouts in `~/.config/bookpup/config.json`.

## Through 1.2.x

Patch lines **0.x**–**1.2.9** (history only — live patch is current `VERSION` on **What's new** and `GET /api/health`).

- **1.2 — Mobile, sniff, and kennel polish:** fixed bottom tab bar + **More** menu; **Fetch selected** and finish toasts; **Recent** query UX; stricter **In kennel** matching; **IRCHighway #ebooks** recommended default; admin **Pack digest** + household backup zip; catalog **Export** JSON; **Queue best picks** batch fetch; **Copy study notes**; tab **a11y**; **Group by** / **Sort by** replaces old **Series**-only view.
- **1.1 — Household catalog extras:** row **In kennel** hints, EPUB-only / hide foreign bots / best-pick highlight; **Series** view with gap hints; duplicate stash fingerprint; **Upload file** on Fresh catches; **OPDS** `/opds/catalog`; desktop notifications + optional download **ntfy**; CBZ in **Reader**; friendlier queue copy.
- **1.0 — Stable household GA:** multi-user IRC search/fetch, library, KOReader sync, Calibre import, and in-browser reader ship as production-ready (Reader Study and IRC reliability stay optional). Sessions survive restart; `GET /api/health` + deploy checks; `public_url`; per-account **Den chatter**; MOBI/EPUB position saved on close; CI smoke tests and v1.0 ops docs.
- **0.9 — Networks, workspace, and pup voice:** **IRCHighway**, **Undernet**, **Rizon** channels and **All networks** merged search; Undernet bot rewrite and connect fixes; named **Open results** drafts/bookmarks with **Save** / **Load** / reorder; **Den chatter** **Bark** (opt-in) and **Post**; **Send to pup**; pup-play UI phrasing; 12-page **Pup guide** + **What's new** tab; login backdrop and mobile layout polish.
- **0.8 — Multi-user household:** per-account libraries, quotas, and covers; admin **Accounts** (create, quota, remove); **Pass to pup** / **Send to…** between accounts; account password changes; IRC live feed filters.
- **0.7 — Queue visibility and Reader Study:** per-job IRC **Status** column, faster queue poll, toasts; search history + autocomplete; optional on-VPS **Study** via `llama-server` + `install_reader_ai.sh` (summarize + Q&A on EPUB/TXT).
- **0.6 — KOReader:** wireless **Progress sync** at your BookPup URL; **Import KOReader** sidecar zip / `.lua` on registered books (partial MD5 match, chunked import). Full Kindle/USB steps live in the **Pup guide**.
- **0.5 — Register and covers:** **Staged** vs **Registered** library; metadata editor + **Search Online**; DuckDuckGo (and optional Google) cover search; manual cover upload; authenticated library **Download**.
- **0.4 — Reader and library foundations:** chunked **Import Calibre**; grid/list library; fuzzy filter; mobile-friendly layout; EPUB dual-page; server-side last position and bookmarks; idle IRC disconnect; this **What's new** page in the nav.
- **0.3 — Auth and queue:** bearer login; **Fetch queue** tab; job **Dismiss**; Calibre `part-*.calibre-data` import; safer IRC reconnect timing.
- **Earlier prototypes:** IRC `@search` + DCC download, staging, 10 GB library cap, MOBI/AZW reader via kindleunpack.