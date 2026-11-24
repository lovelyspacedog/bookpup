# Security

BookPup is designed for a **private household** VPS. Household passwords are stored in plaintext in `accounts.json` so KOReader sync (MD5 of password) and OPDS Basic auth can work without a separate sync secret.

**Do not expose BookPup to the open internet without TLS, strong passwords, and trust in your household users.**

## Reporting

Open a [GitHub issue](https://github.com/lovelyspacedog/bookpup/issues) for vulnerabilities you are willing to disclose publicly. For sensitive reports, use GitHub private vulnerability reporting if enabled on the repo.

## Secrets

Never commit `EXPEDITION_SECRET`, `~/.ssh/expedition_secret`, `config.json`, or `accounts.json` from a live deployment.