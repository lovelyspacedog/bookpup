<div align="center">
  <img src="static/pwa/icon-brand-login.png" alt="BookPup logo — hound and book in a neon kennel mark" width="140" />
</div>

# BookPup

[![test](https://github.com/lovelyspacedog/bookpup/actions/workflows/test.yml/badge.svg)](https://github.com/lovelyspacedog/bookpup/actions/workflows/test.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

Household web portal for **[Whatbox Expedition](https://whatbox.ca/)** (or any VPS): search ebook IRC channels via `@search`, optional **[XDCC index](https://xdccsearch.com)** metasearch, DCC downloads, per-user libraries with quotas, in-browser reader, OPDS, Calibre import, and KOReader progress sync.

**Stack:** Python 3 stdlib HTTP server + static SPA (no pip deps for IRC). **Data:** `~/.config/bookpup/` on the host.

## Features

- **Sniff** — IRCHighway `#ebooks`, Undernet `#bookz`, Rizon `#ebookz`, XDCC index, optional Soulseek via [slskd](https://github.com/slskd/slskd)
- **Fetch queue** — DCC staging, batch fetch, Project Gutenberg fallback for some Undernet refusals
- **Kennel** — **Fresh catches**, **Tag** → **Catalogued bones**, covers, reader (PDF/EPUB/TXT/comics + Calibre conversion path), **Pass to pup…**, OPDS, KOReader wireless sync
- **Your tag** / **Pack roster** — household accounts and per-pup kennel quotas (admins manage pups on **Pack roster**)
- **Pack chat** — household group messages, PMs, BugBot, FeatureCat

In-app help: **Pup guide** (overflow **More** menu) includes **Guide** and **What's new**. **Dig** tab suggests books to sniff (catalog taste, Open Library, popular list from `static/data/dig-bestsellers.json` or auto-refreshed `dig-bestsellers-live.json` when `dig_bestsellers_url` is set in config).

## Requirements

- Python **3.10+** (3.12+ tested in CI)
- For live IRC: outbound IRC (6667) and working DCC from the host
- Optional on server: `ebook-convert` (Calibre), `7z` / `unrar` (CBR/CB7), [llama.cpp](https://github.com/ggerganov/llama.cpp) for optional in-reader **Study** (`scripts/install_reader_ai.sh`)

## Quick start (local)

```bash
git clone https://github.com/lovelyspacedog/bookpup.git
cd bookpup

# Mock IRC/XDCC — no network bots required
BOOKPUP_IRC_MOCK=1 BOOKPUP_XDCC_MOCK=1 python3 bookpup.py
# Open http://127.0.0.1:18478 — first-run credentials print to stderr

python3 -m unittest discover -s tests -v
./scripts/smoke_mock.sh
```

Set **`BOOKPUP_PUBLIC_URL`** (or `public_url` in config) to your HTTPS URL for KOReader / OPDS links.

## Configuration

Runtime config and libraries live under `~/.config/bookpup/`:

| Path | Purpose |
|------|---------|
| `config.json` | Port, `public_url`, IRC/XDCC/Soulseek options, optional ntfy, optional **household Gmail SMTP** for Send-to-Kindle (`smtp_*` keys below), optional scheduled-sniff tuning (`sniff_schedule_tick_seconds`, `sniff_schedule_min_interval_hours`, `sniff_schedule_max_per_user`) |
| `accounts.json` | Household users (admin creates accounts in UI) |
| `users/<name>/` | Per-user library files, covers, indexes |
| `sessions.json` | Bearer sessions (7-day TTL) |
| `pack_chat.json` | Household pack chat history (capped on disk) |

See `GET /api/health` (liveness), `GET /api/ready` (readiness), `GET /api/config` (minimal public shell before login), and `GET /api/session` (authenticated settings for the logged-in pup). Mock flags: `BOOKPUP_IRC_MOCK`, `BOOKPUP_XDCC_MOCK`, `BOOKPUP_SLSKD_MOCK`.

### Send-to-Kindle email (one household Gmail)

On **Expedition** or any VPS, add to `~/.config/bookpup/config.json` (mode `600`). Use a [Google App Password](https://myaccount.google.com/apppasswords), not your normal Gmail password. The **From** address must appear in each Amazon account’s **Send to Kindle → Approved personal document e-mail addresses**.

```json
"smtp_enabled": true,
"smtp_host": "smtp.gmail.com",
"smtp_port": 587,
"smtp_starttls": true,
"smtp_user": "household@gmail.com",
"smtp_password": "your-16-char-app-password",
"smtp_from": "household@gmail.com"
```

Each pup saves their `@kindle.com` address under **Your tag**. In Kennel, **Send to e-reader…** → **Email to my Kindle** (attachments up to 24 MB; larger books use the one-time link). `GET /api/health` reports `kindle_smtp: true` when configured (no secrets exposed).

## Deploy (Whatbox / VPS)

**Third-party VPS:** full checklist in [`docs/DEPLOY.md`](docs/DEPLOY.md) (SSH key deploy via `scripts/deploy-remote.sh`, nginx/systemd, `packaging/config.example.json`).

1. Copy the tree to the server (rsync, git pull, etc.).
2. Run `python3 bookpup.py` bound to `127.0.0.1` and your chosen port (default **18478**).
3. Point your reverse proxy / Whatbox custom app at that port and set `public_url` to the public HTTPS URL.

Sample **nginx** reverse-proxy block: [`packaging/nginx-bookpup.conf.snippet`](packaging/nginx-bookpup.conf.snippet). Whatbox custom apps usually skip nginx and map the public hostname straight to your loopback port.

### systemd (user unit)

```bash
mkdir -p ~/.config/systemd/user
cp packaging/bookpup-user.service ~/.config/systemd/user/bookpup.service
# Edit WorkingDirectory if the tree is not ~/bookpup
systemctl --user daemon-reload
systemctl --user enable --now bookpup.service
```

An example **Arch PKGBUILD** (installs under `/opt/bookpup`) lives in [`packaging/PKGBUILD`](packaging/PKGBUILD).

### Health vs readiness

| Endpoint | Semantics | Use |
|----------|-----------|-----|
| `GET /api/health` | **Liveness** — process up and `~/.config/bookpup` writable; `ok` is **only** `config_dir_writable` (unchanged contract for deploy scripts). Also reports `public_url_configured`. Add `?verbose=1` for IRC/mock diagnostics (default omits them). | Cron, Whatbox custom app, deploy scripts |
| `GET /api/ready` | **Readiness** — IRC worker alive; optional Soulseek sidecar reachable when enabled; reports optional tools (`calibre`, `7z`, `unrar`) without failing liveness. | Operator dashboards, “can we sniff/fetch now?” |

Optional remote sync: `scripts/deploy-remote.sh` (SSH key/agent; optional password file via `BOOKPUP_DEPLOY_SECRET`). [`deploy.sh`](deploy.sh) is a Whatbox Expedition wrapper (`EXPEDITION_HOST` / `EXPEDITION_SECRET`). **Do not commit secrets.**

Post-deploy smoke on the box:

```bash
python3 ~/bookpup/scripts/smoke_production.py
curl -fsS http://127.0.0.1:18478/api/ready | python3 -m json.tool
```

### Quality gates (local / CI)

```bash
python3 -m unittest discover -s tests -v
./scripts/smoke_mock.sh
python3 scripts/e2e_browser.py   # optional; needs playwright
```

Optional Calibre bundle: `scripts/install_calibre.sh`. Optional **Study**: `scripts/install_reader_ai.sh`.

## HTTP API (summary)

Authenticated unless noted. Full handlers live under `lib/routes/`.

| Area | Endpoints |
|------|-----------|
| Auth | `POST /api/login`, `GET /api/session`, `POST /api/logout`, `POST /api/account`, `GET /api/account/wipe-preview`, `POST /api/account/wipe` |
| Search | `POST /api/search`, `GET /api/jobs/{id}`, `POST /api/jobs/{searchId}/select`, batch select, `GET /api/dig-picks` (Dig tab taste picks) |
| IRC | `GET /api/irc/feed`, `GET /api/irc/targets`, `POST /api/irc/chat`, `POST /api/irc/disconnect` |
| Library | `GET/POST/DELETE /api/library…`, upload, export, reader, send-to-user, `GET/POST /api/library/{id}/sideload` (format picker + one-time link), custom shelves `GET/POST/PATCH/DELETE /api/library/shelves`, `PUT /api/library/shelves/{id}/items`, whole-kennel `/api/library/shares…`, OPDS `/opds/catalog` |
| Admin | accounts CRUD, digest, backup |
| Pack chat | `GET /api/pack/chat?after=&del_after=`, `GET /api/pack/chat/peers`, `GET /api/pack/chat/bugbot/open` / `featurecat/open` (first-open intros), `POST /api/pack/chat` (`message`, optional `to`, `parent_id`, `attachments[]`), `POST /api/pack/chat/{id}/reactions`, `POST /api/pack/chat/attachments/claim-copy`, `DELETE /api/pack/chat/{id}`, `POST /api/pack/chat/clear` (admin, pack channel only). Kennel owner invite via attachments or `POST /api/library/shares/invite`; `POST /api/library/shares/{id}/accept-invite`. Scheduled sniff alerts → owner PM from `bookpup` (not ntfy). Bug / feature messages → admin **Bug inbox** / **Feature inbox** (`GET/DELETE /api/admin/bug-inbox`, `/api/admin/feature-inbox`). Failed fetches → **Fetch fail inbox** (`GET/DELETE /api/admin/fetch-fail-inbox`, `GET /api/admin/fetch-fail-inbox/{id}` → markdown log). |
| Public | `GET /api/health`, `GET /api/ready`, `GET /api/config`, `GET /api/capabilities`, `GET /api/sideload/{token}` (one-time catalogued-book download; set `public_url` or `BOOKPUP_PUBLIC_URL` for correct HTTPS links) |

Frontend loads `static/app-*.js` in order; shared state is on `window.BookPup`.

## Project layout

```
bookpup.py          # entrypoint
lib/                # server, IRC, jobs, library, routes/
static/             # SPA, reader, in-app changelog & guide
tests/              # unittest suite
scripts/            # smoke tests, Calibre/AI installers, IRC spike
vendor/             # vendored kindleunpack / mobi helpers (no pip for core IRC path)
```

## Manual QA & browser automation

Household users should use a normal browser or installed PWA. **Cursor’s embedded browser** is stricter about clipboard, checkbox state, and login clicks — not a product bug.

| Topic | Workaround |
|-------|------------|
| Sign-in | `document.getElementById("login-form").requestSubmit()` or `BookPup.doLogin(username, password)` |
| Pack chat DMs | Click `[data-pack-dm-peer="bookpup"]` (lowercase peer id); mobile: scroll past tab dock or use CDP coordinates |
| Offline read | Do not hard-reload while offline; use **Keep offline** then **Read** in-session, or test on installed PWA |
| Study copy | Clipboard API may block in embed; reader falls back to `execCommand("copy")` where allowed |
| Sniff toggles | **Enable Bark** / **Hide other pups** may look read-only in embed; verify in Chrome/Firefox |
| Reader Tab trap | `trapReaderFocus` in `reader.js`; verify Tab wrap in a real browser with Study open |

**Test household cleanup (optional sign-off):** toss **Walk the Trail** practice `.mobi` if you skipped cleanup; trim duplicate QA fetches, old shares, and oversized sniff bookmarks on **testpup** before calling prod done.

## Legal & good citizenship

IRC bots are community-operated. Use BookPup only for material you are entitled to obtain. XDCC metasearch can reach non-ebook networks; disable with `"xdcc_search_enabled": false` in config if you do not want that surface.

## License

Copyright © 2025 Tony Pup.

BookPup is free software: you can redistribute it and/or modify it under the terms of the [GNU General Public License v3.0](LICENSE) (or, at your option, any later version).

Bundled third-party code under `vendor/` and `static/vendor/` keeps its original licenses (see those trees).