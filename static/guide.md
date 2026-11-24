# Pup guide

Step through with **Previous** / **Next**. Each `##` heading is one page.

## Page 1 — Come inside

- BookPup is your household IRC ebook portal — not your Whatbox panel login.
- Sign in with your **pack username** and **password**. An admin creates accounts under **Pack roster**.
- Your session stays in this browser until you **Head out** or the server restarts.
- Change your password under **Your tag** (everyone) or manage pups under **Pack roster** (admins).

## Page 2 — Sniff for books

- Open the **Sniff** tab. Under **Sniff source**, pick where the query runs:
  - **Main trail · IRCHighway #ebooks** — usual first pick for novels and mainstream EPUB/MOBI.
  - **Every ebook net** — same query on all three IRC `@search` channels at once (slower; no Soulseek or XDCC).
  - **Warez yard · XDCC index** — HTTP metasearch across warez IRC (not limited to ebooks).
  - **Peer trail · Soulseek (slskd)** — live Soulseek search on the household seedbox; shared Soulseek login for everyone.
- Type author, title, or keywords. The submit button says **Sniff on IRC**, **Sniff XDCC Index**, or **Sniff Soulseek** depending on the source.
- Soulseek takes longer than IRC (often 10–20 seconds). The status line updates while slskd gathers peer replies. A hint under the source shows **sniffs left this hour** and **fetches left today** when caps apply (admins are exempt from personal caps).
- Past queries autocomplete in the search box (stored in your browser).
- Watch **Fetch queue** at the bottom of Sniff or on the **Fetch queue** tab.

## Page 3 — All networks & the results table

- **All IRC networks** runs the same query on IRCHighway `#ebooks`, Undernet `#bookz`, and Rizon `#ebookz`.
- With no rows loaded yet, the card shows only **Open results & bookmarks**; after a sniff finishes, **Filter results** and the table appear.
- The **Network** column is the source: IRC net name, **XDCC**, or **Soulseek**. **Server** is the IRC bot tag, the XDCC bot name, or the Soulseek peer username.
- If one IRC network fails in an **all** sniff, you still keep the others — check **Den chatter** for errors.
- **Filter results** narrows what you see in the table; it does not shrink what gets saved.
- Filter checkboxes: **EPUB only**, **Hide risky foreign bots** (IRC), **Hide in-kennel matches**, **Highlight best pick** per title cluster.
- **Fetch selected** and **Queue highlighted picks** batch-fetch (small caps per batch).

## Page 4 — Fetch & stash

- **Fetch** on a row starts a download for that row’s backend:
  - **IRC** — DCC from the bot named in the command (`!Bot …` or Undernet `!get ####`).
  - **XDCC** — `xdcc send` to the bot on the row’s network.
  - **Soulseek** — slskd queues a peer transfer into the seedbox download folder, then BookPup copies it into your staging area.
- On Undernet, prefer **`!get ####`** rows when shown; BookPup can match foreign `!Bsk` / `!Horla` lines to a home-network row when possible.
- If **!get** refuses (for example “no EPUB available”), BookPup tries **Project Gutenberg** next — EPUB first, otherwise the best format PG offers (often plain text).
- When the file lands, BookPup adds it to **Fresh catches** automatically and shows a short toast. Open **Kennel** → **Tag** when you want metadata and cover.
- Soulseek fetches count toward **per-user daily caps** and share a **household concurrent** limit (only a few at once for the whole pack).

## Page 5 — Open results & bookmarks

- **Open results** is your working copy: the full last sniff (query, channel, filter). It syncs to your account.
- **Bookmark** saves that full list (25 max, 2500 rows each). **Load** / **Remove** / **↑↓** on each bookmark.
- **Scheduled sniff** on the main sniff card (collapsed **▸** row; or on a bookmark) re-runs the saved query and channel on an interval while BookPup is running. Enabling on the card matches an existing bookmark or bookmarks open results for you. New rows (not seen on that watch before) appear as a **BookPup** private message to whoever owns that bookmark (open **Pack chat** → click **BookPup** under Pack). Download-finished alerts still use optional household **ntfy** when `ntfy_topic` is set. The server defers scheduled sniffs when the fetch queue is busy; IRC still idles out between jobs.
- A new sniff replaces open results when it finishes — bookmark first if you need the old list.
- Recent sniff queries autocomplete in the superbar (focus, typing, or **↓**); picking one fills the box — submit **Sniff** yourself when ready.

## Page 6 — Den chatter

- **Den chatter** stays hidden until a sniff or fetch needs IRC activity, Soulseek status lines, or the den log already has content — then it opens.
- **Hide other pups** (default) filters to your session.
- **Copy** copies the visible log. **Drop link** disconnects IRC when no sniff/fetch is running (Soulseek does not use the IRC socket).
- **Enable Bark** shows the chat box (off by default). No `!` commands — pick one IRC network, not **All networks**.

## Page 7 — Fetch queue

- Lists search and download jobs: queued, running, done, failed, cancelled.
- **Call off** cancels when possible. **Clear** removes finished error/cancelled rows from view.
- One worker runs jobs **one at a time** — a long Soulseek or IRC fetch blocks the next job until it finishes.
- IRC idles out after ~4 minutes with an empty queue; the next IRC job reconnects.

## Page 8 — Kennel

- **Sharing** — ask another pup to browse your whole kennel (or approve their request). **Lend** = they can read and download; **give** = they can also **Add to my kennel** (copies, your quota unchanged). Use **Browsing** to switch between your kennel and pups who shared with you. Pack chat gets a **BookPup** note when someone requests access.

- **Fresh catches** — downloads waiting to be **Tag this book** (metadata + cover).
- **Fresh catches** — **Toss** uses a simple confirm. **Catalogued bones** — **Read**, **Cover**, **Pass to pup…**, **Toss** (type the random phrase in the dialog).
- **Import Calibre** and **Import KOReader** for bulk bring-over. Grid/list view is remembered in the browser.

## Page 9 — KOReader sync

- Catalogued books only. On the device: KOReader **Progress sync** → custom server.
- Server URL: your BookPup site (e.g. `https://bookpup.tonypup.box.ca`). Same username/password as the website.
- BookPup matches by file fingerprint — tag and stash before syncing.

## Page 10 — Your tag & pack roster

- **Pack chat** (main tab): opening the tab always lands on **Pack chat · everyone** (main household channel); pick a pup again if you need a PM. Under **Private message**, click a pup — **Open PM →** — for a one-to-one thread; a red count beside a name means new PMs from that pup (clears when you open the thread). **BookPup** — **Open alerts →** — is where scheduled-sniff notices land (same badge). Green dot = online. Remove your own lines (or alerts sent to you); admins can remove any line or clear **Pack** only (PMs stay). This is not **Den chatter** (IRC/Soulseek logs on Sniff).
- **Your tag:** rename yourself or rotate password (current password required).
- **Pack roster** (admins): create pups, **Set quota**, **Set login**, **Remove**. Passwords are reset only, never shown.
- Admins may set per-pup **Soulseek caps** (`soulseek_limits` on the account) if someone needs tighter sniff/fetch limits than the household default.
- Each pup has a private folder and storage quota (files + covers).

## Page 11 — Reader & Study

- **Read** opens PDF, EPUB, TXT, Markdown, HTML, or CBZ/CBR/CB7 in the browser. MOBI/AZW3 and FB2, DJVU, CHM, RTF, LIT convert to EPUB once (Calibre on the server).
- Position and bookmarks stay on the server. EPUB and comic **Dual page** are local toggles; in comic dual view each page pans and zooms separately.
- **Study** (when enabled on the server): summarize and Q&A — first reply can be slow on shared CPU.

## Page 12 — Good habits

- Quota applies when books are **stashed**, not while sniffing.
- IRC is flaky by nature — retry another network or row if a fetch fails. Soulseek peers go offline; try another row or sniff again later.
- Soulseek uses one household identity on the network — be kind to ratio and caps so the pack stays in good standing.
- Only fetch what you may legally keep. **What's new** is the version changelog; this guide is the walkthrough.