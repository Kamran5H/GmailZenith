# ✉️ Gmail Zenith

<div align="center">

[![CI](https://github.com/Kamran5H/GmailZenith/actions/workflows/ci.yml/badge.svg)](https://github.com/Kamran5H/GmailZenith/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](#install)
[![Gmail API](https://img.shields.io/badge/Google-Gmail%20API-EA4335?logo=gmail&logoColor=white)](https://developers.google.com/gmail/api)

**Clean up your Gmail inbox fast, from a local dashboard that runs only on your computer.**

</div>

Gmail Zenith talks directly to the official Gmail API from your own machine. There's no cloud service and no third party: your sign-in token never leaves your computer.

## Features

| | |
|---|---|
| **Overview** | Exact inbox, unread, spam and trash counts, a per-category breakdown (Primary / Promotions / Social / Updates / Forums), and your top senders with their size and unread counts. |
| **Cleaners** | One-click cleanups for promotions, social, old updates, forums, large attachments, clutter older than a year, and spam. Each shows its live match count. |
| **Search & Bulk** | Any Gmail search (`from:`, `older_than:`, `larger:`…) with paging. Act on the selected emails, or on **all matching** emails (up to 5,000 per run). |
| **Unsubscribe** | One-click (RFC 8058) unsubscribe when the sender supports it. Otherwise it opens their unsubscribe page or email. |
| **GitHub triage** | Sorts GitHub notification emails into PRs, issues, CI runs, security alerts and releases, with direct links to the exact PR or issue. |
| **Auto-Clean** | Your own rules (Gmail search + trash / archive / mark read) that run on a schedule, with a run history. |

**Safety built in**

- Every bulk action shows a **preview** first: an exact count, an approximate size and sample emails.
- Actions only move mail to **Trash** (kept by Gmail for 30 days), archive it, or mark it read. Nothing is ever permanently deleted.
- Every action can be **undone**, and undo puts each email back exactly where it was (inbox, archive or spam).
- **Starred emails are never touched** by cleaners, bulk actions or rules.
- The local API rejects requests from other websites, so a page you visit can't trigger actions.

## Install

Requires Python 3.10+.

```bash
git clone https://github.com/Kamran5H/GmailZenith.git
cd GmailZenith
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
```

## Connect Gmail (one-time)

1. In [Google Cloud Console](https://console.cloud.google.com/), create a project and **enable the Gmail API**.
2. Configure the **OAuth consent screen** (External, Testing) and add your Gmail address as a **test user**.
3. Under **Credentials**, create an **OAuth client ID** of type **Desktop app** and download its JSON.
4. Start the app (see below), open the **Setup** tab, drop in the JSON, and click **Connect Gmail**.

> Using a *Web application* client instead? Add the redirect URI shown on the Setup tab
> (by default `http://127.0.0.1:8767/oauth2callback`) to the client in Google Cloud Console.

## Run

| How | Command |
|---|---|
| Any OS | `python backend/app.py` → opens <http://127.0.0.1:8767> |
| Windows, with a console | double-click `run_gmail_zenith.bat` (installs requirements if needed) |
| Windows, silent | double-click `launch.vbs`, or run `python create_desktop_shortcut.py` once for a desktop icon |

Options: `--no-browser`. Environment variables: `ZENITH_PORT` (default `8767`) and `ZENITH_HOST` (default `127.0.0.1`).

### Background Auto-Clean

Set up rules on the **Auto-Clean** tab, then either:

```bash
python auto_sync_daemon.py          # keep running; applies rules every N minutes
python auto_sync_daemon.py --once   # apply rules once and exit (for cron / Task Scheduler)
```

On Windows, run `install_auto_sync_task.ps1` once to start the daemon automatically at every login. To remove it, add `-Uninstall`.

## Project layout

```text
backend/
  app.py            FastAPI server + local REST API
  gmail_engine.py   Gmail API: OAuth (PKCE), exact counts, batched fetches, actions + undo
  auto_sync.py      Auto-Clean rules, config validation, run history
frontend/           Dashboard (vanilla HTML/CSS/JS, no build step)
auto_sync_daemon.py Background rule runner
scan_primary_inbox.py  Print recent emails in the terminal: python scan_primary_inbox.py 50 "is:unread"
tests/              pytest suite
```

These files hold your data and are git-ignored: `credentials.json`, `token.json`, `auto_sync_config.json` and `auto_sync_log.json`.

## Development

```bash
pip install -r requirements-dev.txt
pytest
```

## License

[MIT](LICENSE) © 2024-2026 Kamran Ashraf
