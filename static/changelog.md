# BookPup changelog

## 1.4.12

- **Kennel:** **Email to my Kindle** — household Gmail SMTP (`smtp_*` in server `config.json`); sends the chosen format to each pup’s Send-to-Kindle address on **Your tag** (24 MB cap; use the link for bigger files).
- **Fix:** `GET /api/health` reports `kindle_smtp` when relay is configured.

## 1.4.11

- **Kennel:** **Send to e-reader…** on catalogued bones — pick format (original or EPUB), get a one-time HTTPS download link for Kindle, KOReader, or sideload.
- **UX:** **Your tag** — save Send-to-Kindle email; OPDS / KOReader / Kindle help in one **E-readers** panel.

## 1.4.10

- **UX:** **What's new** — all **1.3.x** patch notes (**1.3.0**–**1.3.110**) rolled into one abridged **1.3** history block (same style as **Through 1.2.x**).

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

## 1.3

Patch lines **1.3.0**–**1.3.110** (history only — live patch is current `VERSION` on **What's new** and `GET /api/health`).

- **Walk the Trail:** **New here?** onboard + step-by-step coach (practice sniff, Den chatter, tutorial MOBI **Fetch**, tag, queue, **Pack chat** with **BugBot** / **FeatureCat**); shipped tutorial fixture; mobile coach dock/scroll/spotlight/tap fixes; optional cleanup; confetti on complete; restart from **Pup guide** page 1 (**Walk the Trail again** lives there, not **Sniff**).
- **Pack:** household **Pack chat** (everyone + PMs, online presence, unread sidebar badges, compact **Remove**); **BugBot** bug DMs + **Feature inbox**; **FeatureCat** requests + **Feature inbox**; instant bot intros and **clear** to reset a bot thread.
- **Kennel & sniff:** whole-kennel **Sharing** (**lend** read/download or **give** copies) + **Browsing** picker; **Scheduled sniff** on the sniff card and bookmarks (collapsed summary, owner **BookPup** PM on new rows); **Fetch queue** opens on **All**; mobile kennel toolbar rows; **Fresh catch** done alert no longer replays after tag/toss or sign-out.
- **UX & copy:** lay-friendly **Pup guide**; labels aligned (**Fresh catches**, **Catalogued bones**, **Study**, **Scheduled sniff**); mobile **Sniff source** short labels; **Head out** under **More** on small screens; header weather (later removed in **1.3.66**).
- **Reader:** CBZ/CBR one-finger pan on mobile, including at 100% zoom.
- **Sniff — schedules & bookmarks (early 1.3):** bookmark **Schedule sniff** + server tick; compact **Open results & bookmarks** row; optional `sniff_schedule_*` config.
- **Security:** staging downloads scoped to job owner; `..` blocked in staging ids; library quota includes covers; SSRF guards on cover-from-URL and optional `ntfy_server`; atomic JSON for accounts, catalog, and reading state; safer zip extract; login field no longer prefilled from server.
- **UI:** readable native select menus; **About BookPup** from the header/logo; sniff toolbar sticks above the table, compact fetch buttons, bookmarks below results; **Den chatter** hidden until IRC activity; empty sniff card shows **Open results & bookmarks** only; cover/tag lookups show spinners; **What to sniff for** superbar (recent queries, **Clear** outside the field).
- **Sniff:** **Sniff source** labels and hints; default **Main trail · IRCHighway #ebooks**; **IRCHighway #bookz** removed; paginated filtered results with type badges; **Wipe matches** respects active filters; live queue/connect status; reliable sniff/fetch polling and queue backfill; **EPUB only** auto-off when it would hide every row; Undernet catalogue titles (no bare IDs).
- **Sniff — XDCC index:** [xdccsearch.com](https://xdccsearch.com) metasearch channel (warez yard, separate from IRC **All networks**); inline `POST /api/search` results; Den logs for index searches.
- **Sniff — Soulseek:** **Peer trail · Soulseek (slskd)** on Expedition; inline sniff; auto-reconnect when slskd is disconnected; per-user and household caps (`soulseek_limits` on accounts); health reports `soulseek.server_logged_in` / `server_state`.
- **Fetch:** XDCC index DCC to pack bots; **bot preflight** and two-phase DCC wait (`download_offer_timeout`, `bot_status_stale_seconds`); fast fail on **!get** refusals, **0 matches**, and stale bots; **Project Gutenberg** HTTPS fallback (EPUB first) with Den **Project Gutenberg fallback:** lines; Soulseek transfer completion and on-disk path fixes.
- **Kennel:** finished downloads land in **Fresh catches** (no **Got a bone!**); **Stash in kennel** confirms before **Tag this book**; ghost row cleanup after account wipe; list filter **Clear**; uploads/stash/import match expanded **Read** formats.
- **Reader (early 1.3):** MOBI/AZW paginated dual-page; CBZ/CBR pan/zoom/dual-page (per-page on CBZ); **FB2, DJVU, LIT, CHM, RTF, CB7**, sandboxed **Markdown/HTML** via Calibre; comic **Debug…** on archive errors.
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