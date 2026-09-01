# 🚀 Gmail Zenith Pro — AI Inbox Optimizer & Triage Suite
**Created for Kamran Ashraf (Kami)**

An ultra-high aesthetic (4K HD Glassmorphism) web application and Python backend to effortlessly triage, clean, and organize your Gmail inbox.

---

## ✨ Features

- 🎯 **1-Click Rapid Purges:**
  - **Promotions Purge:** Delete marketing emails & sales blasts (`category:promotions`).
  - **Social Media Clear:** Remove LinkedIn, Twitter/X, Instagram, TikTok digests (`category:social`).
  - **Automated Updates:** Clean subscription notifications & digests (`category:updates`).
  - **Spam Box Sweep:** Empty junk and phishing items.
  - **Storage Reclaimer:** Identify and remove massive emails with attachments (`>10MB`, `>5MB`).
  - **Ancient Mail Cleaner:** Safely trash promotional/social emails older than 1 year.
- 🐙 **GitHub Triage Command Center:**
  - Specialized triage for `notifications@github.com`.
  - Auto-categorizes emails into **Pull Requests**, **Issue Mentions**, **CI/CD Workflow Failures**, **Dependabot Security Alerts**, and **Releases**.
  - Direct 1-click links to GitHub threads, batch mark-as-read, or archive.
- 🔍 **Universal Filter & Smart Query Builder:**
  - Real-time search with instant preview table, sender filters, size filters, unread flags, and multi-selection checkboxes.
- 🛡️ **Safety Shield (Dry-Run Preview):**
  - Preview exact matched emails and estimated storage space to be reclaimed before confirming any deletion.
  - Defaults to **Gmail Trash** (recoverable for 30 days).
- 📊 **Visual Analytics Dashboard:**
  - Category breakdown chart, storage space reclaimer, top clutter spammer rankings.
  - Real-time live log terminal streaming background operations.

---

## 🔑 1-Minute Google OAuth Setup

1. Go to [Google Cloud Console Credentials](https://console.cloud.google.com/apis/credentials).
2. Enable the **Gmail API** under *APIs & Services* > *Library*.
3. Click **Create Credentials** $\rightarrow$ **OAuth client ID** $\rightarrow$ select **Desktop app**.
4. Click **Download JSON** $\rightarrow$ drag & drop your `credentials.json` into the **Connection & Setup** tab in Gmail Zenith Pro.
5. Click **"Authorize Google Account"** $\rightarrow$ a standard browser window will open to safely sign in and authenticate.

---

## 🖥️ How to Run

- **Desktop Shortcut:** Double-click **`Gmail Zenith Pro - Kamran Ashraf.lnk`** on your Desktop.
- **Silent Launcher:** Double-click `launch.vbs`.
- **Command Line:** Run `python backend\app.py` or double-click `run_gmail_zenith.bat`.
- The dashboard will open automatically in your browser at: **`http://127.0.0.1:8765`**
