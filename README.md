# 🗂️ Bitbucket Workspace Repository Downloader

A production-grade Python CLI tool to **download every repository** from a Bitbucket Cloud workspace as individual ZIP archives — with parallel downloads, retry logic, resume support, and CI/CD-ready configuration.

---

## 📋 Table of Contents

- [Features](#-features)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Authentication Setup](#-authentication-setup)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [CLI Reference](#-cli-reference)
- [Environment Variables](#-environment-variables)
- [Output Structure](#-output-structure)
- [Exit Codes](#-exit-codes)
- [CI/CD Integration](#-cicd-integration)
- [Troubleshooting](#-troubleshooting)
- [Architecture](#-architecture)
- [License](#-license)

---

## ✨ Features

| Feature | Detail |
|---|---|
| 🔐 **Authentication** | Bitbucket App Password or OAuth2 Access Token |
| 📄 **Full Pagination** | Handles workspaces with 100s of repositories |
| ⚡ **Parallel Downloads** | Configurable worker threads (default: 4) |
| 🔁 **Auto Retry** | Exponential backoff on 429 / 5xx errors (3 retries) |
| ♻️ **Resume Support** | Skips repos already downloaded (idempotent) |
| ✅ **ZIP Validation** | Verifies each archive is a valid ZIP before saving |
| 🌿 **Branch Detection** | Auto-detects each repo's default branch via API |
| 🔍 **Repo Filtering** | `--filter` flag for selective downloads |
| 🧪 **Dry Run Mode** | List repos without downloading anything |
| 📊 **Summary Report** | Post-run success/failure table with counts |
| 📦 **Progress Bar** | `tqdm` progress bar (graceful fallback if absent) |
| 🔧 **`.env` Support** | Reads credentials from `.env` file automatically |

---

## 📦 Requirements

- **Python** 3.10 or higher
- **pip** packages:

```
requests>=2.28.0
tqdm>=4.64.0
python-dotenv>=1.0.0
urllib3>=1.26.0
```

> `tqdm` and `python-dotenv` are optional but recommended.

---

## 🛠️ Installation

**1. Clone or download the script**

```bash
git clone https://github.com/your-org/bitbucket-repo-downloader.git
cd bitbucket-repo-downloader
```

**2. Create a virtual environment (recommended)**

```bash
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows
```

**3. Install dependencies**

```bash
pip install requests tqdm python-dotenv
```

---

## 🔐 Authentication Setup

This tool uses **Bitbucket App Passwords** (recommended) or **OAuth2 Access Tokens**.

### Option A — App Password (Recommended)

1. Log in to [bitbucket.org](https://bitbucket.org)
2. Go to **Personal Settings → App passwords → Create app password**
3. Name it (e.g. `repo-downloader`)
4. Grant the **`Repositories: Read`** permission
5. Copy the generated password — it's shown only once

### Option B — OAuth2 Token

Use `x-token-auth` as the username and your OAuth2 access token as the password:

```bash
--username x-token-auth --password <your_oauth_token>
```

---

## ⚙️ Configuration

You can configure the tool in three ways (in order of precedence):

1. **CLI flags** (highest priority)
2. **Environment variables**
3. **`.env` file** (lowest priority)

### `.env` file example

Create a `.env` file in the same directory as the script:

```dotenv
BB_WORKSPACE=your-workspace-slug
BB_USERNAME=your-bitbucket-username
BB_APP_PASSWORD=your-app-password
BB_OUTPUT_DIR=./downloads
```

> ⚠️ Add `.env` to your `.gitignore` — never commit credentials.

---

## 🚀 Usage

### Basic — download all repos

```bash
python bitbucket_repo_downloader.py \
  --workspace  your-workspace \
  --username   your-username \
  --password   your-app-password
```

### Using environment variables

```bash
export BB_WORKSPACE=your-workspace
export BB_USERNAME=your-username
export BB_APP_PASSWORD=your-app-password

python bitbucket_repo_downloader.py
```

### Custom output directory

```bash
python bitbucket_repo_downloader.py \
  --workspace myorg \
  --username  alice \
  --password  xxxx \
  --output-dir /backups/bitbucket/2024-06
```

### Increase parallel workers for faster downloads

```bash
python bitbucket_repo_downloader.py \
  --workspace myorg --username alice --password xxxx \
  --workers 8
```

### Download only repos matching a keyword

```bash
# Downloads only repos whose slug contains "api"
python bitbucket_repo_downloader.py \
  --workspace myorg --username alice --password xxxx \
  --filter api
```

### Force a specific branch for all repos

```bash
python bitbucket_repo_downloader.py \
  --workspace myorg --username alice --password xxxx \
  --branch master
```

### Dry run — list repos without downloading

```bash
python bitbucket_repo_downloader.py \
  --workspace myorg --username alice --password xxxx \
  --dry-run
```

Sample dry-run output:

```
SLUG                                      LANGUAGE         PRIVATE
-----------------------------------------------------------------
backend-api                               Python           yes
frontend-app                              TypeScript       yes
data-pipeline                             Python           no
infra-terraform                           HCL              yes

Total: 4 repositories (dry run — nothing downloaded)
```

### Enable debug logging

```bash
python bitbucket_repo_downloader.py \
  --workspace myorg --username alice --password xxxx \
  --verbose
```

---

## 📖 CLI Reference

| Flag | Env Variable | Default | Description |
|---|---|---|---|
| `--workspace` | `BB_WORKSPACE` | *(required)* | Bitbucket workspace slug |
| `--username` | `BB_USERNAME` | *(required)* | Bitbucket username |
| `--password` | `BB_APP_PASSWORD` | *(required)* | App Password or OAuth token |
| `--output-dir` | `BB_OUTPUT_DIR` | `./bitbucket_repos` | Directory to save ZIP files |
| `--branch` | — | *(repo default)* | Force a branch for all repos |
| `--workers` | — | `4` | Number of parallel download threads |
| `--filter` | — | *(none)* | Only download repos matching this substring |
| `--dry-run` | — | `False` | List repos without downloading |
| `--verbose` | — | `False` | Enable DEBUG-level logging |

---

## 🌍 Environment Variables

| Variable | Description |
|---|---|
| `BB_WORKSPACE` | Workspace slug (found in your Bitbucket workspace URL) |
| `BB_USERNAME` | Your Bitbucket account username |
| `BB_APP_PASSWORD` | App Password or OAuth2 access token |
| `BB_OUTPUT_DIR` | Override default output directory |

---

## 📁 Output Structure

Each repository is saved as `<repo-slug>.zip` in the output directory:

```
./bitbucket_repos/
├── backend-api.zip
├── frontend-app.zip
├── data-pipeline.zip
├── infra-terraform.zip
└── mobile-sdk.zip
```

At completion, a summary is printed:

```
════════════════════════════════════════════════════════════
  DOWNLOAD SUMMARY
════════════════════════════════════════════════════════════
  Output directory : /home/user/bitbucket_repos
  Total repos      : 12
  ✅ Succeeded     : 11
  ❌ Failed        : 1

  Failed repositories:
    • legacy-monolith                         HTTP 404 — branch 'main' not found
════════════════════════════════════════════════════════════
```

---

## 🔢 Exit Codes

| Code | Meaning |
|---|---|
| `0` | All repositories downloaded successfully |
| `1` | Fatal error (auth failure, no repos found, bad arguments) |
| `2` | Partial failure — some repos failed to download |

These are designed for clean integration with CI/CD pipelines and shell scripts.

---

## 🔄 CI/CD Integration

### GitHub Actions

```yaml
name: Bitbucket Backup

on:
  schedule:
    - cron: "0 2 * * 0"   # Every Sunday at 2 AM
  workflow_dispatch:

jobs:
  backup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install requests tqdm python-dotenv

      - name: Download Bitbucket repositories
        env:
          BB_WORKSPACE: ${{ secrets.BB_WORKSPACE }}
          BB_USERNAME:  ${{ secrets.BB_USERNAME }}
          BB_APP_PASSWORD: ${{ secrets.BB_APP_PASSWORD }}
        run: |
          python bitbucket_repo_downloader.py \
            --output-dir ./archives \
            --workers 8

      - name: Upload archives as artifact
        uses: actions/upload-artifact@v4
        with:
          name: bitbucket-backup-${{ github.run_number }}
          path: ./archives/*.zip
          retention-days: 30
```

### GitLab CI

```yaml
bitbucket-backup:
  image: python:3.11-slim
  script:
    - pip install requests tqdm python-dotenv
    - python bitbucket_repo_downloader.py --workers 6 --output-dir ./archives
  artifacts:
    paths:
      - archives/
    expire_in: 30 days
  variables:
    BB_WORKSPACE: $BB_WORKSPACE
    BB_USERNAME: $BB_USERNAME
    BB_APP_PASSWORD: $BB_APP_PASSWORD
```

### Cron (Linux)

```bash
# Edit crontab: crontab -e
# Run every day at midnight
0 0 * * * BB_WORKSPACE=myorg BB_USERNAME=alice BB_APP_PASSWORD=xxxx \
  /usr/bin/python3 /opt/scripts/bitbucket_repo_downloader.py \
  --output-dir /backups/bitbucket/$(date +\%Y-\%m-\%d) >> /var/log/bb-backup.log 2>&1
```

---

## 🔧 Troubleshooting

### `401 Unauthorized`
- Verify your username and App Password are correct
- Ensure the App Password has **Repositories: Read** scope
- If using an OAuth token, set `--username x-token-auth`

### `404 Not Found` on a specific repo
- The repo's default branch might be `master` instead of `main`
- Use `--branch master` to override for all repos

### Downloads are slow
- Increase `--workers` (try 8–16 for large workspaces)
- Ensure your network has sufficient bandwidth
- Large repositories with long history will naturally take longer

### `Downloaded file is not a valid ZIP archive`
- Usually indicates a redirect loop or authentication issue
- Run with `--verbose` to see the full request/response cycle

### Rate limiting (429 errors)
- The script automatically retries with backoff — no action needed
- If persistent, reduce `--workers` to lower request concurrency

---

## 🏗️ Architecture

```
bitbucket_repo_downloader.py
│
├── build_session()          # HTTP session with auth + retry adapter
├── paginate()               # Cursor-based API pagination handler
├── list_repositories()      # Fetches all repos via /2.0/repositories/{workspace}
├── get_default_branch()     # Per-repo mainbranch detection
├── download_repo_zip()      # Streaming ZIP download → temp file → validate → move
├── print_summary()          # Post-run success/failure report
├── parse_args()             # CLI argument parser with env var fallbacks
└── main()                   # Orchestrator: auth → list → filter → parallel download
```

**Concurrency model:** `ThreadPoolExecutor` with `as_completed()` — each worker independently fetches the branch name and streams the ZIP, writing to a temp file before atomically moving to the output directory.

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

## 🙏 Acknowledgements

Built against the [Bitbucket Cloud REST API v2.0](https://developer.atlassian.com/cloud/bitbucket/rest/intro/).
