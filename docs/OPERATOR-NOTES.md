# Operator notes (public)

Condensed mechanics for VPS operators. For household feature docs, use in-app **Pup guide**.

## Ports and paths

| Item | Default |
|------|---------|
| HTTP bind | `127.0.0.1:18478` |
| Config / data | `~/.config/bookpup/` |
| App tree | `~/bookpup/` (or `BOOKPUP_APP_DIR`) |

## Mock flags (dev only)

| Env | Effect |
|-----|--------|
| `BOOKPUP_IRC_MOCK` | Fake IRC search/download |
| `BOOKPUP_XDCC_MOCK` | Fake XDCC index |
| `BOOKPUP_SLSKD_MOCK` | Fake Soulseek |

Production: unset all three; `/api/health` should show each mock `false`.

## Public URL

- Config key `public_url` or env `BOOKPUP_PUBLIC_URL` (env wins).
- Required for KOReader sync URLs, OPDS catalog links, HTTPS sideload links, and outbound HTTP User-Agent identity.
- `/api/health` exposes `public_url_configured` (does not affect liveness `ok`).

## IRC targets

| Target | Note |
|--------|------|
| `undernet:bookz` | Uses `us.undernet.org` for VPS egress |
| `irchighway:ebooks` | Fewer stable bots; intermittent failures are normal |
| `xdcc:index` | Optional; can surface non-ebook networks |

## Health vs readiness

- `GET /api/health` — liveness (`ok` === config dir writable). Add `?verbose=1` for IRC mock flags and worker snapshot (keep default URL public / cron-safe).
- `GET /api/ready` — IRC worker, optional slskd, optional tool probes.

## Staging

DCC drops live under `~/.config/bookpup/staging/` (24h TTL); not counted toward library quota until saved/registered.