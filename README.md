# BookPup

[![test](https://github.com/lovelyspacedog/bookpup/actions/workflows/test.yml/badge.svg)](https://github.com/lovelyspacedog/bookpup/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Household web portal for **[Whatbox Expedition](https://whatbox.ca/)** (or any VPS): search ebook IRC channels via `@search`, optional **[XDCC index](https://xdccsearch.com)** metasearch, DCC downloads, per-user libraries with quotas, in-browser reader, OPDS, Calibre import, and KOReader progress sync.

**Stack:** Python 3 stdlib HTTP server + static SPA (no pip deps for IRC). **Data:** `~/.config/bookpup/` on the host.

## Features

- **Sniff** — IRCHighway `#ebooks`, Undernet `#bookz`, Rizon `#ebookz`, XDCC index, optional Soulseek via [slskd](https://github.com/slskd/slskd)
- **Fetch queue** — DCC staging, batch fetch, Project Gutenberg fallback for some Undernet refusals
- **Kennel** — library catalog, covers, reader (PDF/EPUB/TXT/comics + Calibre conversion path), OPDS, KOReader wireless sync
- **Pack** — multi-user accounts, per-user quotas, admin roster, send-to-household-member

In-app help: **Guide** and **What's new** tabs after you sign in.

## Requirements

- Python **3.10+** (3.12+ tested in CI)
- For live IRC: outbound IRC (6667) and working DCC from the host
- Optional on server: `ebook-convert` (Calibre), `7z` / `unrar` (CBR/CB7), [llama.cpp](https://github.com/ggerganov/llama.cpp) for optional Reader Study

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
| `config.json` | Port, `public_url`, IRC/XDCC/Soulseek options, optional ntfy |
| `accounts.json` | Household users (admin creates accounts in UI) |
| `users/<name>/` | Per-user library files, covers, indexes |
| `sessions.json` | Bearer sessions (7-day TTL) |

See `GET /api/health` and `GET /api/config` (after login) for effective settings. Mock flags: `BOOKPUP_IRC_MOCK`, `BOOKPUP_XDCC_MOCK`, `BOOKPUP_SLSKD_MOCK`.

## Deploy (Whatbox / VPS)

1. Copy the tree to the server (rsync, git pull, etc.).
2. Run `python3 bookpup.py` bound to `127.0.0.1` and your chosen port (default **18478**).
3. Point your reverse proxy / Whatbox custom app at that port and set `public_url` to the public HTTPS URL.

Optional: `deploy.sh` rsyncs the working tree and installs a cron **start** hook when `EXPEDITION_HOST` and `EXPEDITION_SECRET` are set (Whatbox-style SSH + password file). **Do not commit secrets.**

Post-deploy smoke on the box:

```bash
python3 ~/bookpup/scripts/smoke_expedition.py
```

Optional Calibre bundle: `scripts/install_calibre.sh`. Optional reader AI: `scripts/install_reader_ai.sh`.

## HTTP API (summary)

Authenticated unless noted. Full handlers live under `lib/routes/`.

| Area | Endpoints |
|------|-----------|
| Auth | `POST /api/login`, `GET /api/session`, `POST /api/logout`, `POST /api/account` |
| Search | `POST /api/search`, `GET /api/jobs/{id}`, `POST /api/jobs/{searchId}/select`, batch select |
| Library | `GET/POST/DELETE /api/library…`, upload, export, reader, send-to-user, OPDS `/opds/catalog` |
| Admin | accounts CRUD, digest, backup |
| Public | `GET /api/health`, `GET /api/irc/targets` |

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

## Legal & good citizenship

IRC bots are community-operated. Use BookPup only for material you are entitled to obtain. XDCC metasearch can reach non-ebook networks; disable with `"xdcc_search_enabled": false` in config if you do not want that surface.

## License

MIT — see [LICENSE](LICENSE).