# Pup guide

Step through with **Previous** / **Next**. Each `##` heading is one page.

## Page 1 — Welcome

- **BookPup** helps your household **find** ebooks online, **download** them to your shared book server, **organize** them on your shelf, and **read** them in the browser.
- This site is **not** your hosting provider’s control panel. Sign in here with the **username** and **password** an admin gave you.
- You stay signed in in this browser until you choose **Head out** or the server restarts.
- Admins add accounts under **Pack roster**. Everyone can change their own password under **Your tag**.
- **Walk the Trail** is a hands-on tour on **Sniff**: practice sniff/fetch, Fresh catches, Tag, then **Pack chat** (household channel, DMs, BugBot/FeatureCat).
- Start or repeat it with **Walk the Trail** at the bottom of this page (the label says **Walk the Trail again** after you finish once).

## Page 2 — Sniff, fetch, catalog, read

BookPup’s everyday loop is four steps:

| Step | Plain meaning |
|------|----------------|
| **Sniff** | Search the internet (and our household’s book sources) for titles that match what you typed. You get a list of matches — no file on your shelf yet. |
| **Fetch** | Ask BookPup to **download** one of those matches. The file lands in **Fresh catches** — like a landing tray for new arrivals. |
| **Catalog** | Open **Tag this book**, fix title/author/cover, then save. The book moves to **Catalogued bones** — your real library shelf. Only catalogued books count toward your storage limit. |
| **Read** | From **Catalogued bones**, choose **Read** to open the book here (or download to your device). |

You can sniff many times, fetch several books, then catalog when you are ready. **Sniff** and **Fresh catches** do not use your quota; **Catalogued bones** do.

## Page 3 — Sniff for books

- Open **Sniff**. Type an author, title, or keywords, then press the sniff button (the label changes depending on which source you picked).
- Under **Sniff source**, choose where to search:
  - **Main trail** — best first stop for most novels and common ebook types.
  - **Every ebook net** — searches all of our ebook chat sources at once (slower).
  - **Warez yard** — wider file index beyond ebooks only.
  - **Peer trail** — searches other people’s shared folders on Soulseek (can take 10–20 seconds; status updates while it works).
- When results appear, use **Filter results** if you want (for example EPUB only). Filtering only changes what you **see** — it does not delete matches.
- Hints under the search box may show **sniffs left this hour** or **fetches left today** if the household sets limits (admins are not capped personally).
- Your recent searches can autocomplete in the box (saved in this browser).

## Page 4 — Dig for ideas

- Open **Dig** (between **Sniff** and **Kennel**) when you want suggestions without inventing a query.
- **From your kennel** — more by authors, tags, and series you already tagged.
- **Along the trail** — related titles from Open Library (needs the server online).
- **Popular on the trail** — bundled list plus optional auto-refresh: set `dig_bestsellers_url` in server config to an HTTPS JSON feed (same shape as `static/data/dig-bestsellers.json`).
- Each row has **Sniff this** — jumps to **Sniff** and runs that query. **In kennel** means you already have a close match catalogued.

## Page 5 — Fetch a book

- In the results table, **Fetch** on a row starts the download for that line.
- **Fetch selected** or **Queue highlighted picks** grabs several at once (small batch limit).
- When the file is ready, BookPup puts it in **Kennel** → **Fresh catches** and shows a short on-screen note.
- Watch progress on **Sniff** (bottom) or the **Fetch queue** tab: queued → running → done or failed.
- If a download fails, try another row or another sniff source — online sources come and go.
- On some networks BookPup can try **Project Gutenberg** automatically when a bot says a title is not offered in the format you wanted.

## Page 6 — Catalog (tag) a book

- Go to **Kennel** → **Fresh catches**. Each item is a download waiting for you to name and shelve it.
- Open **Tag** (or **Tag this book**) — a compact dialog: set title, author, and tags; use **More details** for ISBN, series, and description; cover art and **Search Online** sit in the side column on wider screens.
- Save. The book moves to **Catalogued bones**. That is **cataloging**: it is on your shelf, searchable, and ready for **Read** or sharing.
- **Toss** removes something from **Fresh catches** if you do not want it (simple confirm).
- In **Catalogued bones**, **Edit tags** updates metadata; **Toss** needs you to type a short random phrase so deletes are deliberate.
- **Shelves** (toolbar): **New shelf…** for a custom list (e.g. beach reads). Pick a shelf to show only those catalogued books; **Manage shelf…** checks which bones belong on it. A book can sit on more than one shelf. Tossing a book removes it from every shelf.
- **Catalogued bones** — toolbar **View → Flow** flips through cover art (arrow keys or swipe); the centred jacket shows a floor reflection. **Flow** is only available when **Group by** is **None** (use **Grid** or **List** for grouped shelves).
- Filter **In progress** shows books you have started but not finished; **Sort by → Last read** orders by your latest reading session. Cover pills show rough progress (e.g. **42%**).
- **Surprise me** picks a random readable catalogued book and opens **Read**. **Copy link** on a catalogued book copies a URL that opens **Kennel** and highlights that title (use `?owner=` when browsing a shared shelf).

## Page 7 — Read

- **Catalogued bones** → **Read** opens the book in the browser (common types work directly; some older formats are converted once on the server).
- **Cover** shows the jacket. Reading position and in-book bookmarks sync to your account on the server.
- Comic-style books (CBZ and similar) can use **Dual page** (**D** on a keyboard, or the toolbar button). In dual view, click a page or press **1** / **2** (or **[** / **]**) to choose which page zoom and pan apply to — the active page gets a thin outline. **+** / **−** zoom; arrow keys pan when zoomed. Preference is remembered on this device.
- **Study** (if your admin turned it on): ask questions or get a summary about the open book — the first answer can be slow on a busy server. Press **S** to open Study; **Escape** closes it before closing the book. **Copy study notes** includes where you were reading; reopening Study on the same section can pick up your last notes.

## Page 8 — Save a search list

- **Sniff again** (next to recent queries) re-runs your latest sniff text on whatever **Sniff source** is selected now.
- **Open results** is your last finished sniff — full list, query, and filters — tied to your account.
- **Bookmark** keeps that list (up to 25 bookmarks). Use **Load**, **Remove**, or **↑↓** to manage them.
- A new sniff replaces open results when it finishes — bookmark first if you need the old list.
- **Scheduled sniff** (small **▸** row on the sniff card or on a bookmark) re-runs the same search on a timer while BookPup is running. Brand-new rows can arrive as a private **BookPup** message — open **Pack chat** → **Private message** → **BookPup**. Busy download queues can delay scheduled sniffs.

## Page 9 — Fetch queue

- **Fetch queue** lists every sniff and download job: waiting, in progress, finished, failed, or cancelled.
- **Cancel** stops a job when possible. **Dismiss** clears finished errors from the list.
- Jobs run **one at a time** — one long download means the next waits its turn.
- IRC connections may rest when nothing is queued; the next job wakes them again.

## Page 10 — Den chatter

- **Den chatter** is the live log when a sniff or fetch is talking to chat bots or Soulseek. It stays hidden until there is something to show.
- **Hide other pups** (default) shows only your activity.
- **Copy** copies the visible log. **Drop link** disconnects idle chat when you are not downloading (Soulseek does not use that chat link).
- **Enable Bark** shows a message box for normal chat (not bot commands). Pick one network, not “all at once.”
- This is separate from **Pack chat** (household messages between pups).

## Page 11 — Share your library

- Under **Kennel** → **Sharing**, ask another pup to browse your shelf, or approve their request.
- **Lend** — they can read and download your books.
- **Give** — they can also **Add to my kennel** (a copy lands in their library; your quota is unchanged).
- **Browsing** switches between your kennel and shelves pups shared with you.
- Pack chat gets a **BookPup** note when someone requests access.
- **Pass to pup…** on a catalogued book sends a copy to someone else’s kennel.

## Page 12 — Calibre, e-readers & KOReader

- **Import Calibre** and **Import KOReader** on **Kennel** bring existing libraries in bulk (secondary path if you already use those apps).
- **Send to e-reader…** (catalogued bones only): choose **original** or **EPUB** (converted when needed). **Create download link** (one-time URL, ~1 hour) or, when your server has household Gmail set up, **Email to my Kindle** (save your `@kindle.com` address on **Your tag** first). Amazon must approve the server’s Gmail **From** address.
- **OPDS:** URL on **Your tag** — username and password match this site; catalogued bones only.
- **KOReader sync** (device): **Progress sync** → custom server at your BookPup URL — same username/password. Only **Catalogued bones** sync — tag books first. BookPup matches by file fingerprint.

## Page 13 — Pack chat, account & habits

- **Pack chat:** household channel and private messages. **Attach…** sends a **catalogued book** (recommend or **send copy**) or an **invite to your kennel** (the other pup accepts lend/give on the card). **Reply** on a line to thread; react with **paw**, **heart**, or **laugh**. **BookPup** holds scheduled-sniff alerts. **BugBot** and **FeatureCat** collect bug reports and feature ideas for admins (**Pack roster** → **Bug inbox** / **Feature inbox**). Failed fetches land in **Fetch fail inbox** (markdown log with Den chatter). Type **clear** in a bot thread to reset it. Green dot = pup online. This is not **Den chatter**.
- **Your tag:** change display name or password (current password required).
- **Pack roster** (admins): **Add pup**, set **Quota**, **Set login**, **Wipe**, or **Remove**. Passwords are reset, never displayed.
- **Good habits:** only fetch what you may legally keep. Storage quota applies in **Catalogued bones**, not in **Fresh catches**. Online sources fail sometimes — retry or try another match. Soulseek uses one household identity — respect caps and ratio so the pack stays welcome. **What's new** is the version list; this guide is the walkthrough.

## Page 14 — Phone & home screen

- On a phone, use the browser menu **Add to Home Screen** / **Install app** (wording varies), or tap **Install BookPup** on the sign-in page or under **Your tag** when the browser offers a one-tap install.
- Installed BookPup opens full screen like an app and keeps your sign-in in this browser profile.
- **Offline (no server):** sign-in shell, **Pup guide**, and **What's new** from cache. If you used **Keep offline** on catalogued **EPUB** or **PDF**, reopen from your home screen — **Kennel** lists those books and **Read** works on this device.
- **Keep offline:** on a catalogued bone, tap **Keep offline** while online (2 GiB cap per device). **Remove offline copy** frees space. Filter **On this device** shows only downloaded titles. Reading position syncs when you are back online.
- **Online only:** sniffing, fetching, full **Kennel**, **Pack chat**, and OPDS need a live connection (except books you kept offline).