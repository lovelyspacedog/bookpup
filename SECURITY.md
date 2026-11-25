# Security

BookPup is designed for a **private household** VPS. Household passwords are stored in plaintext in `accounts.json` so KOReader sync (MD5 of password) and OPDS Basic auth can work without a separate sync secret.

**Do not expose BookPup to the open internet without TLS, strong passwords, and trust in your household users.**

## Reporting

Open a [GitHub issue](https://github.com/lovelyspacedog/bookpup/issues) for vulnerabilities you are willing to disclose publicly. For sensitive reports, use GitHub private vulnerability reporting if enabled on the repo.

## Secrets

Never commit deploy credentials, live `config.json`, or `accounts.json` from a deployment.

| Secret / file | Use |
|---------------|-----|
| `BOOKPUP_DEPLOY_SECRET` / `EXPEDITION_SECRET` | SSH password for `scripts/deploy-remote.sh` or `./deploy.sh` (mode **600** or **400**) |
| `~/.ssh/expedition_secret` | Default path for Expedition wrapper |
| `~/.config/bookpup/config.json` | IRC, SMTP, slskd, admin password |
| `~/.config/bookpup/accounts.json` | Household user passwords (plaintext by design for KOReader/OPDS) |
| `~/.config/bookpup/login_throttle.json` | Recent failed login timestamps per client IP (mode **600**) |

Prefer **SSH keys** for `BOOKPUP_DEPLOY_HOST` deploys; use a password file only when the host requires it (e.g. Whatbox).