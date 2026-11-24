# About BookPup

**BookPup** is a household web portal for searching ebook IRC channels, fetching files via DCC, and organizing per-user libraries on your [Whatbox Expedition](https://whatbox.ca/) box.

## What you can do

- **Sniff** — query IRC ebook bots (IRCHighway, Undernet, Rizon), or the **XDCC index** for general files beyond ebooks (video, comics, packs, archives via [xdccsearch.com](https://xdccsearch.com))
- **Fetch queue** — download and land files in **Fresh catches**; **Tag** into **Catalogued bones**
- **Kennel** — fresh catches, catalogued bones, covers, in-browser reader, OPDS, Calibre import, KOReader progress sync
- **Your tag** / **Pack roster** — household accounts and kennel quotas; **Pack chat** for the pack

## Good citizenship

IRC bots are run by the community. BookPup only talks to channels your household chooses — **only fetch and keep books you have the right to hold**. See **Pup guide** for a full walkthrough.

## Tech

Python stdlib server on the VPS plus a static single-page app (no pip dependencies for IRC). Your data lives under `~/.config/bookpup/` on Expedition.

## What's new

Open the **What's new** tab for release notes, or ask your pack admin which version is deployed.