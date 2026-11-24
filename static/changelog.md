# BookPup changelog

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

## 1.2.9

- **Kennel:** **Series** view replaced with **Group by** (none / series / author) and **Sort by** (recent, title, author, series, size). Grid and List stay separate.

## 1.2.8

- **Mobile:** bottom bar fits the viewport — primary tabs only, **More** menu for Pack roster / Pup guide / What&apos;s new, short labels (**Queue**, **Out**).

## 1.2.7

- **Sniff:** **What to sniff for** clears when you open the Sniff tab (and after sign-in); last query stays in **Open results** metadata. Use **Recent** to rerun a past query.

## 1.2.6

- **Mobile:** fixed bottom tab bar with **Head out** on the right; header stays title + version only.
- **Sniff:** row checkboxes + **Fetch selected** (up to 5); filter checkboxes aligned; friendlier SearchBot notices in Den chatter and queue toasts.
- **Fetch:** in-app toast when a download finishes (plus existing desktop notification toggle).
- **Bookmarks:** smaller action buttons on narrow screens.

## 1.2.5

- **Sniff:** **IRCHighway #ebooks** first in channel list, labeled recommended; default selection + hint.

## 1.2.3

- **Sniff:** **Recent** is a compact dropdown (+ Clear); mobile stack layout, 44px touch targets.

## 1.2.2

- **Sniff:** recent queries as pill chips; focus dropdown with filter, remove one, clear all (replaces browser datalist).

## 1.2.1

- **Sniff:** stricter **In kennel** matching (stop words, distinctive token overlap, best catalog hit).

## 1.2.0

- **Admin:** Pack digest on Pack roster; household backup zip (`GET /api/admin/backup`).
- **Kennel:** Export catalog JSON (`GET /api/library/export`).
- **Sniff:** **Queue best picks** batch fetch (up to 3, `POST …/select-batch`).
- **Reader Study:** **Copy study notes** (summary + Q&A markdown to clipboard).
- **A11y:** Tab roving focus, `aria-selected`, live queue status region.

## 1.1.0

- **Sniff:** “In kennel” hints, EPUB-only / hide foreign bots / best-pick row highlight.
- **Kennel:** Series view with missing-volume hints; duplicate stash blocked by file fingerprint; **Upload file** on Fresh catches (`POST /api/library/upload`).
- **OPDS:** `/opds/catalog` for registered books (Your tag shows URL).
- **Alerts:** Desktop notification toggle; optional `ntfy_topic` on download done.
- **Reader:** CBZ comic pages.
- **UI:** Friendlier queue toasts and Fetch queue labels.

## 1.0.0

Stable household release: multi-user IRC search/fetch, library, KOReader sync, Calibre import, and in-browser reader are GA. Reader Study and IRC network reliability remain optional / best-effort.

- **Release:** `RELEASE-1.0.0.md`, `UPGRADING.md`, `LICENSE`, CI unit tests (`scripts/smoke_mock.sh`, `scripts/smoke_expedition.py`).
- **Config / ops:** `public_url` + `BOOKPUP_PUBLIC_URL`; `GET /api/health`; deploy health check.
- **Sessions:** `sessions.json` survives restart (7-day TTL); login rate limit per IP.
- **UI:** toasts for library errors and **Pass to pup**; Den chatter **Clear chat**; per-account IRC feed.
- **Reader:** MOBI/converted EPUB position (CFI + scroll) saved on close.
- **Docs:** v1.0 scope in README; mobile layout structural tests.

## 0.9.8.1

- **Pup guide:** **Show all** / **By page** toggle.

## 0.9.8

- **UI:** bookmarks live under **Filter results** (collapsed). Sleeker **Den chatter** toolbar. **Pup guide** is a 12-page tutorial with Previous/Next.

## 0.9.7.9

- **Login:** tagline typewriter no longer restarts on repeated session kicks (e.g. after server restart).

## 0.9.7.8

- **UI:** login backdrop fixed for real — `bookpup.css` paints full viewport; deploy no longer overwrites kennel `theme.css` from hyperwoofer.

## 0.9.7.7

- **UI:** backdrop no longer has a solid band at the top (removed centre vignette over paw tile).

## 0.9.7.6

- **UI:** page backdrop (paw tile + glows) fills the full viewport on login and wide screens.

## 0.9.7.5

- **Den chatter:** **Disconnect IRC** when idle; **Bark** input hidden until **Enable Bark** is checked.

## 0.9.7.4

- **Fetch:** **Stash in kennel** closes the “Got a bone!” panel on success.

## 0.9.7.3

- **Fetch:** Undernet rows with foreign bots (`!Horla`, `!Bsk`, …) redirect to the same title on that book’s home network instead of blind `!Oatmeal`. Better `!get` title matching.

## 0.9.7.2

- **Saved searches:** clearer labels (open results, bookmarked lists, **Bookmark**), structured Query / Sniffed from / Rows status.

## 0.9.7.1

- **Den chatter:** **Bark** disabled by default; **Enable Bark** checkbox (preference saved in browser).

## 0.9.7

- **Search workspace:** per-account **draft** (current results + filter + query/channel), **Save draft** into named snapshots, **Load** / **Remove** / **↑↓** reorder (max 25 saves, 2500 rows each). Fetch uses a backing job per draft/save.

## 0.9.6.3

- **All networks:** new IRC connection per channel on the same server (fixes IRCHighway `#bookz` disconnect after `#ebooks`).

## 0.9.6.1

- **All networks:** reuse one IRC connection when switching channels on the same server; continue after a failed target; keep partial merged results instead of full job retry.

## 0.9.6

- **IRC channel:** **All networks** runs the same query on each target, merges results (Network column), and **Fetch** uses the row’s network for download.

## 0.9.5.8

- **Fix:** IRC connect on Python 3.14 when `getaddrinfo` returns IPv6 4-tuples (Rizon / dual-stack hosts).

## 0.9.5.7

- **Undernet:** match foreign `!Bsk` rows to a `!get ID` from the same search when possible; fail fast when Oatmeal says file not in catalogue (no endless reconnect loop).
- **Den chatter:** **Copy log** button.

## 0.9.5.6

- **Undernet #bookz:** rewrite highway-style `!Bsk …` (and other foreign tags) to `!Oatmeal …` for Oatmeal DCC; `!get` unchanged.

## 0.9.5.4

- **Undernet search:** ignore interim “0 matches in the … catalogue” notices so SearchBot can still deliver results via DCC.

## 0.9.5.3

- **Fetch:** loading button uses a pseudo-element spinner (fixes clipped “(” in tight table cells).
- **DCC:** ignore late `SearchBot_results_*.txt.zip` offers when waiting for a book; clearer PING/PONG and IRC ERROR logging.

## 0.9.5.2

- **Undernet:** connect via `us.undernet.org` (reachable from Expedition); try each resolved IRC host instead of hanging on a dead round-robin address.

## 0.9.5

- **IRC channels:** Search picker lists **IRCHighway** (#ebooks, #bookz), **Undernet** (#bookz), and **Rizon** (#ebookz), each labeled with its network. Jobs reconnect to the right server per selection.

## 0.9.4

- **Fetch:** spinner on the row while queuing a download.
- **Kennel:** **Read** / **Cover** (was Curl up / Jacket); **Toss** needs a random phrase typed in the prompt.

## 0.9.2

- **Login:** keep **Come inside** visible; restore **Sign in** for 1Password/autofill (hidden label + `aria-label`, standard form fields).

## 0.9.1

- **Fix:** search/job polling no longer surfaces transient `Expecting value` errors (atomic job file writes + brief load retry).

## 0.9.0

- **Pup-play phrasing** across tabs, buttons, and messages (Sniff, Kennel, Fetch queue, etc.).
- **Pup guide:** collapsible sections (closed by default) + **Expand all** / **Collapse all**.

## 0.8.8

- **Guide** tab: getting-started help for Search, Library, KOReader, accounts, and more.

## 0.8.7

- **Sign-in:** random pup-themed tagline with typewriter effect.

## 0.8.6

- **IRC live:** **Post** sends a chat line to the channel selected in Search (#ebooks / #bookz). Max 400 chars; cannot start with `!`.

## 0.8.5

- **IRC live:** **Hide other users** (default on) filters feed to your jobs; **Hide raw** now re-filters existing lines when toggled.

## 0.8.4

- **Admins:** one **Accounts** tab (your login + household management). Regular users keep **Account** only.

## 0.8.3

- **Account** tab: users change username/password (current password required). Admins: **Set login** on any account (set only; passwords never displayed).

## 0.8.2

- **Fix:** multi-user migration no longer leaves an empty per-user `library.json` when the legacy index still has books (SleepyBadger / first admin).

## 0.8.1

- **Send to user:** copy a library book (staged or registered) or a finished IRC download into another account's library (sender keeps their copy). Recipient quota enforced. **Send to…** on library items and download panel.

## 0.8.0

- **Multi-user:** per-account library + covers under `~/.config/bookpup/users/<name>/`; **per-user storage quota**; admin **Accounts** tab (create, set quota GB, remove). `SleepyBadger` migrates as admin from existing config. KOReader/login works for any account.

## 0.7.8

- Changelog: correct KOReader path to **Progress sync** (in-book menu, not Settings).

## 0.7.7

- **Search:** local **history** + **autocomplete** (last 40 queries in browser); remembers last IRC channel.

## 0.7.6

- **Queue:** per-job **IRC status** from live session (connect, @search, DCC, notices); **Status** column; header line shows active job status; **toasts** on state/IRC updates (faster queue poll while jobs run).

## 0.7.5

- **Reader AI:** `llama-server` context **4096** (was 2048); shorter default excerpts so prompts fit. Restart: `pkill -f llama-server` or redeploy BookPup so a new server picks up `-c`.

## 0.7.4

- **Reader AI:** wait up to 3 minutes for `llama-server` to finish loading the GGUF; retry on HTTP 503 `Loading model` instead of failing immediately.

## 0.7.3

- Reload `config.json` when the file changes on disk (fixes Reader AI staying disabled after `install_reader_ai.sh` without restarting BookPup).

## 0.7.2

- **Reader AI:** install full `llama-runtime/` from release tarball (bundled `.so` libs); set `LD_LIBRARY_PATH` when starting `llama-server`.

## 0.7.1

- **install_reader_ai.sh:** fetch `llama-*-bin-ubuntu-x64.tar.gz` from **ggml-org/llama.cpp** (default `b7569`); auto-scan recent tags if that release 404s.

## 0.7.0

- **Reader Study (EPUB + TXT):** on-VPS **Qwen2.5-0.5B** via `llama-server` — summarize current section and ask grounded comprehension questions. Install on Expedition with `scripts/install_reader_ai.sh -y` (~500 MB disk); lazy server start from BookPup.

## 0.6.5

- **Import KOReader:** match registered books by KOReader **partial MD5** (folder hash in zip paths + indexed digests of library files) before title/filename heuristics.

## 0.6.4

- **Import KOReader:** sidecars for books not in Registered books are skipped silently (e.g. comics / `metadata.cbz.lua`).

## 0.6.3

- **Import KOReader:** ignore `custom_metadata.lua` and other non-sidecar `.lua` files; partial import + errors no longer leave the progress bar stuck.

## 0.6.2

- **Registered books:** **Edit** opens the metadata form (search online, covers, all fields); saves via `POST /api/library/{id}/metadata`.
- **Import Calibre** and **Import KOReader** share chunked uploads with a progress bar.

## 0.6.1

- Changelog: where to find `.sdr` folders on Kindle USB for **Import KOReader**.

## 0.6.0

- **KOReader sync** (Calibre-plugin style): wireless **Progress sync** server at your BookPup URL; **Import KOReader** for `metadata.*.lua` / `.sdr` zip on **Registered books**. Stores percent, position, status, highlights; matches books by title/filename like Calibre’s KOReader Sync plugin.

### Kindle KOReader Progress sync

1. On the Kindle (KOReader): **open a book**, then **Tools → Cloud storage &amp; sync → Progress sync** (some builds: gear menu → **Progress sync**). Not under Dropbox/FTP/WebDAV. Set **Custom sync server** to `https://bookpup.tonypup.box.ca`, then **Register / Login** with BookPup credentials.
2. Username = BookPup login user (`config.json`); password = BookPup login password (KOReader sends an MD5 hash; BookPup verifies it).
3. Open each book once on the device after it is in **Registered books** so the document hash matches the copy in BookPup.
4. **Sidecar zip (USB)** — KOReader stores one `.sdr` folder per book. On a Kindle over USB the volume is usually **`Kindle` / `documents`** (Linux: `/mnt/us/`).

   | KOReader setting **Document metadata folder** | Where the `.sdr` folders are |
   | --- | --- |
   | **Next to document** (default) | Beside each book, e.g. `documents/My Book.epub.sdr/` containing `metadata.epub.lua` |
   | **Docsettings** | Under `koreader/docsettings/` on the USB volume, mirroring the book path, e.g. `koreader/docsettings/documents/My Book.epub.sdr/metadata.epub.lua` |
   | **Hash** | Under `koreader/history/` (hashed subfolders; each still ends in `…/metadata.*.lua`) |

   Zip the `.sdr` folder(s) — or many in one archive — and use **Import KOReader** in Registered books. You can also upload a single `metadata.*.lua` if you only need one title.

   Tip: in KOReader, **File browser** → long-press the book → path shown at the top; the sidecar is that path + `.sdr/`.

## 0.5.3

- Library **Download** sends your auth token (fixes JSON `Authentication required` on direct link clicks).

## 0.5.2

- **Search cover images** uses DuckDuckGo (no API key or billing). Optional Google CSE still available via `BOOKPUP_COVER_IMAGE_PROVIDER=google`.

## 0.5.1

- **Manual cover upload** (JPEG, PNG, WebP; 2 MB max) from Register or **Cover** on library cards.
- **Google image search** for covers (Custom Search API; optional `google_cse_api_key` + `google_cse_cx` in config).

## 0.5.0

- Library sections: **Staged files** / **Registered books**; **Register** with metadata editor and **Search Online** (Google Books + Open Library, Calibre-style ISBN-first).

## 0.4.6

- Library **filter** (grid and list): multi-word fuzzy match on title, author, series, tags, etc.

## 0.4.5

- Mobile library **list** layout (roomier rows, actions on own row); **grid** fixed at two columns.

## 0.4.4

- **Mobile layout**: scrollable tabs, touch-friendly controls, responsive tables/library grid, reader safe areas.

## 0.4.3

- Changelog tab on the main nav (this page).

## 0.4.2

- Disconnect from IRC after **4 minutes** with no queued or running jobs; reconnect on the next search/download.

## 0.4.1

- EPUB **dual-page** reading toggle (paginated mode).
- Library **Grid / List** view toggle.
- Library sections: **Downloaded files** first, then **Calibre import**.

## 0.4.0

- **Chunked Calibre import** with upload progress bar.
- Library split into Calibre vs download sections; cover **grid** with metadata.
- Reader **last position** and **bookmarks** (server-side).

## 0.3.2

- **Import Calibre** from `part-*.calibre-data` export files.

## 0.3.1

- IRC post-join cooldown before search commands; randomized reconnect nicks.

## 0.3.0

- Login with bearer tokens; failed/cancelled jobs stay in queue with **Dismiss**.
- Queue tab and job lifecycle improvements.

## Earlier

- IRC search + DCC download, 10GB library, staging, MOBI/AZW reader via kindleunpack.