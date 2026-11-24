# Deploy BookPup on a VPS

BookPup listens on **loopback** (default `127.0.0.1:18478`). You expose it with your provider’s reverse proxy, panel “custom app”, or nginx/Caddy in front of TLS.

## Requirements

- Python **3.10+**
- Outbound IRC (**6667**) and working **DCC** from the host (datacenter VPS is fine; Undernet uses `us.undernet.org` by default)
- Writable `~/.config/bookpup/`
- HTTPS public URL for KOReader sync, OPDS, and one-time sideload links (`public_url` or `BOOKPUP_PUBLIC_URL`)

Optional: `ebook-convert` (Calibre), `7z` / `unrar` (comics), [slskd](https://github.com/slskd/slskd) for Soulseek.

## Quick path (any VPS)

1. Clone or rsync the repo to the server (e.g. `~/bookpup`).
2. Start once: `python3 ~/bookpup/bookpup.py` — first-run admin password prints to stderr.
3. Set `public_url` in `~/.config/bookpup/config.json` (see [`packaging/config.example.json`](../packaging/config.example.json)).
4. Point HTTPS at port **18478** (see [`packaging/nginx-bookpup.conf.snippet`](../packaging/nginx-bookpup.conf.snippet)).
5. Keep it running: [`packaging/bookpup-user.service`](../packaging/bookpup-user.service) or `~/bookpup/start` + cron.

Verify:

```bash
curl -fsS http://127.0.0.1:18478/api/health | python3 -m json.tool
curl -fsS http://127.0.0.1:18478/api/ready | python3 -m json.tool
```

`ok` on `/api/health` is **liveness only** (config dir writable). `public_url_configured` is false until you set a public URL.

## Remote deploy script (SSH)

From your **local** machine with the BookPup tree:

### SSH key or agent (default)

```bash
export BOOKPUP_DEPLOY_HOST='you@your.vps'
./scripts/deploy-remote.sh
```

Optional:

| Variable | Purpose |
|----------|---------|
| `BOOKPUP_DEPLOY_APP_DIR` | Remote app dir (default `~/bookpup`) |
| `BOOKPUP_DEPLOY_REMOTE_HOME` | Override remote `$HOME` if auto-detect fails |
| `BOOKPUP_DEPLOY_PUBLIC_URL_HINT` | Printed reminder after deploy |
| `BOOKPUP_DEPLOY_SSH_OPTS` | Extra SSH options (default `-4`, timeouts) |

The script rsyncs the tree, ensures cron + `start`, optional one-time Calibre install, and curls `/api/health` on the remote loopback.

### Password-only SSH (e.g. Whatbox Expedition)

Store the SSH password in a **mode 600** file and point the secret at it:

```bash
export BOOKPUP_DEPLOY_HOST='user@expedition.whatbox.ca'
export BOOKPUP_DEPLOY_SECRET="$HOME/.ssh/expedition_secret"
./scripts/deploy-remote.sh
```

Or use the Expedition wrapper (same behavior + optional kennel fonts):

```bash
./deploy.sh
```

Never commit deploy secrets. See [SECURITY.md](../SECURITY.md).

## Whatbox custom app

No nginx required on many Whatbox plans: add a **custom app** → name BookPup → port **18478** → your HTTPS subdomain. Set `public_url` in config to that URL.

## systemd (user unit)

```bash
mkdir -p ~/.config/systemd/user
cp packaging/bookpup-user.service ~/.config/systemd/user/bookpup.service
# Edit WorkingDirectory if the tree is not ~/bookpup
systemctl --user daemon-reload
systemctl --user enable --now bookpup.service
```

## Production smoke (on the VPS)

```bash
python3 ~/bookpup/scripts/smoke_production.py
```

Uses loopback by default (`BOOKPUP_SMOKE_BASE`). Set `BOOKPUP_APP_DIR` if the tree is not `~/bookpup`.

## Mock / local dev

```bash
BOOKPUP_IRC_MOCK=1 BOOKPUP_XDCC_MOCK=1 python3 bookpup.py
./scripts/smoke_mock.sh
```

## More operator detail

Short reference: [OPERATOR-NOTES.md](OPERATOR-NOTES.md). Full API and config tables: [README.md](../README.md).