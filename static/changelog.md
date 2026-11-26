# BookPup changelog

## 1.8.1

- **Fix — Den chatter:** **Enable Bark** no longer deadlocks the IRC worker (sniffs could stick on **Waking IRC link…** after a bark).

## 1.8.0

- **UX:** **What's new** — **1.7.x** patch notes rolled into an abridged history block (same style as **1.6** / **1.7.0**).

## 1.7 — dig & kennel polish

Patch lines **1.7.0**–**1.7.32** (history only — live patch is current `VERSION` on **What's new** and `GET /api/health`).

- **Dig:** New **Dig** tab — catalog picks, Open Library suggestions, **Popular on the trail** (bundled + optional live `dig_bestsellers_url`); **Sniff this** on each row; jacket art from your kennel or Open Library cache.
- **Kennel:** **Flow** cover carousel for **Catalogued bones**; two-row catalog toolbar; centered tag/cover/account dialogs with live cover preview; **In progress** filter, **Last read** sort, **Surprise me**, deep links, duplicate-title warning; grid covers use full jackets.
- **Sniff / Fetch:** **Every ebook net** and **Undernet** reliability fixes; cross-network fetch fallback before fail; **Fetch fail inbox** for admins; longer Soulseek poll and honest **in progress** status; **Sniff again** for last query.
- **Fix — Trust:** Chunked upload quota sessions; proxy-aware login throttle; generic 500 bodies; Walk the Trail tag focus and practice-toss cleanup.
- **UX:** Hound-head tab favicon; sign-in brand stack; **Pup guide** and **What's new** in one overflow tab.

## 1.6

Patch lines **1.6.0**–**1.6.8** (history only — live patch is current `VERSION` on **What's new** and `GET /api/health`).

- **Pack:** **Pack chat v2** — attach **catalogued books** (recommend or offer copy) and **kennel invites**; reply quotes; **paw / heart / laugh** reactions; owner invites accept lend/give from the chat card; tighter compose row, pending attachment chip, compact reaction pills and footer **Reply** / **Remove**.
- **Kennel:** Chunked **Upload file** over ~3 MB (proxy-safe); quota usage includes `derived/` cache; empty **shelf** filter copy; toss modal hooks for automation and no longer toggles reader layout.
- **Reader:** MOBI→EPUB derived cache **v2**/**v3** — strip justify/letter-spacing, collapse spaced NCX titles; Study **Copy study notes** tries `execCommand` when the Clipboard API is blocked.
- **Fix — Sniff/Fetch:** Zero-match searches clear open results; DCC rejects offers above 512 MB (or remaining kennel space) with 32 MB zip cap on search; re-fetch avoids `File exists`; cancelled downloads drop partial **Fresh catches** and staged files.
- **Fix — Pack/KOReader/Security:** Claim-copy reserves attachment under lock; `POST /users/create` accepts household `accounts.json` pups; disabled accounts revoke bearer sessions; sideload `HEAD` no longer leaks metadata; login rate-limit persists in `login_throttle.json` across restart; README API table matches auth.
- **Ops/Docs:** `HEAD` **200** on manifest, service worker, and sideload links; `GET /api/search/saved`; `GET /api/ready` ensures IRC worker thread; README **Manual QA & browser automation**.

## 1.5 — community operator

Patch lines **1.5.0**–**1.5.4** (history only — live patch is current `VERSION` on **What's new** and `GET /api/health`).

- **Operator:** **docs/DEPLOY.md** for any VPS; SSH-key deploy via `scripts/deploy-remote.sh`; Whatbox keeps `./deploy.sh`; no default `public_url` on new installs; `GET /api/health` reports `public_url_configured`; example `packaging/config.example.json`, production smoke `scripts/smoke_production.py`, hosting-neutral About/Pup guide copy.
- **UX:** **About** dialog and **Pup guide** readable Inter typography; guide markdown tables (e.g. Page 2 loop) render instead of raw pipe text.
- **Kennel:** **Shelves** — create named shelves, filter **Catalogued bones**, **Manage shelf…** to assign catalogued books.

## 1.4 — take your kennel beyond the browser

Patch lines **1.4.0**–**1.4.18** (history only — live patch is current `VERSION` on **What's new** and `GET /api/health`).

- **UX:** Install BookPup on your phone (**Add to Home Screen**, **Neon Kennel** icon); offline **Pup guide** / **What's new**; **Keep offline** for catalogued **EPUB**/**PDF**; sign-in/header logos; header **version** opens **About**, **logo** refreshes to **Sniff**; pre-**1.3** release notes abridged in **What's new**.
- **Kennel:** **Send to e-reader…** — one-time HTTPS link; **Email to my Kindle** when household SMTP is set (`kindle_smtp` on health); fresh `smtp_*` without restart.
- **Pack:** **Walk the Trail** onboard tour (practice sniff → fetch → tag → **Pack chat**); **Pack digest** lists pups who have not finished; completion syncs across devices.
- **Reader:** Mobile polish; keyboard shortcuts and comic dual-page zoom/pan; **Copy study notes** with reading position; Study resume per section.
- **Ops:** **Health** vs **readiness** (`GET /api/ready`); sample **systemd**, **nginx**, **PKGBUILD** under `packaging/`; CI/E2E smoke docs.

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