#!/usr/bin/env python3
"""
Bitbucket Workspace Repository Downloader
==========================================
Author      : Tanmoy Mitra
Purpose     : Download all repositories from a Bitbucket workspace as individual ZIP archives
Auth Support: App Password (recommended) or OAuth2 Access Token
API         : Bitbucket Cloud REST API v2.0

Usage:
    python bitbucket_repo_downloader.py

    Or with environment variables:
    BB_WORKSPACE=myworkspace BB_USERNAME=myuser BB_APP_PASSWORD=xxxx python bitbucket_repo_downloader.py

Requirements:
    pip install requests tqdm python-dotenv
"""

import os
import sys
import time
import logging
import argparse
import zipfile
import tempfile
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── Optional: load .env file if present ──────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not required

# ── Optional: rich progress bar ───────────────────────────────────────────────
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION — override via environment variables or CLI flags
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_OUTPUT_DIR   = "./bitbucket_repos"
DEFAULT_MAX_WORKERS  = 4        # Parallel download threads
DEFAULT_PAGE_LEN     = 50       # Bitbucket API page size (max 100)
BITBUCKET_API_BASE   = "https://api.bitbucket.org/2.0"
CONNECT_TIMEOUT      = 10       # seconds
READ_TIMEOUT         = 120      # seconds (large repos need time)
MAX_RETRIES          = 3
BACKOFF_FACTOR       = 1.0

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HTTP SESSION WITH RETRY
# ─────────────────────────────────────────────────────────────────────────────
def build_session(username: str, password_or_token: str) -> requests.Session:
    """Build a persistent session with retry logic and Basic Auth."""
    session = requests.Session()
    session.auth = (username, password_or_token)
    session.headers.update({
        "Accept": "application/json",
        "User-Agent": "BitbucketRepoDownloader/1.0",
    })

    retry_strategy = Retry(
        total=MAX_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# ─────────────────────────────────────────────────────────────────────────────
# BITBUCKET API HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def paginate(session: requests.Session, url: str, params: dict) -> list[dict]:
    """Fetch all pages from a paginated Bitbucket endpoint."""
    results = []
    while url:
        resp = session.get(url, params=params, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        resp.raise_for_status()
        data = resp.json()
        results.extend(data.get("values", []))
        url = data.get("next")   # Bitbucket provides next page URL directly
        params = {}              # next URL already includes query params
    return results


def list_repositories(session: requests.Session, workspace: str) -> list[dict]:
    """Return all repositories in the given workspace."""
    log.info("Fetching repository list for workspace: %s", workspace)
    url = f"{BITBUCKET_API_BASE}/repositories/{workspace}"
    repos = paginate(session, url, {"pagelen": DEFAULT_PAGE_LEN})
    log.info("Found %d repositories.", len(repos))
    return repos


# ─────────────────────────────────────────────────────────────────────────────
# ZIP DOWNLOAD
# ─────────────────────────────────────────────────────────────────────────────
def get_default_branch(session: requests.Session, workspace: str, slug: str) -> str:
    """Retrieve the repository's default/mainbranch name."""
    url = f"{BITBUCKET_API_BASE}/repositories/{workspace}/{slug}"
    try:
        resp = session.get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        resp.raise_for_status()
        main = resp.json().get("mainbranch", {})
        return main.get("name", "main")
    except Exception:
        return "main"


def download_repo_zip(
    session: requests.Session,
    workspace: str,
    slug: str,
    branch: str,
    output_dir: Path,
) -> tuple[str, bool, str]:
    """
    Download a repository branch as ZIP from Bitbucket's source archive endpoint.
    Returns (slug, success, message).
    """
    zip_url = (
        f"https://bitbucket.org/{workspace}/{slug}/get/{branch}.zip"
    )
    dest_path = output_dir / f"{slug}.zip"

    # Skip if already downloaded
    if dest_path.exists():
        return slug, True, f"Skipped (already exists): {dest_path}"

    try:
        with session.get(
            zip_url,
            stream=True,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            allow_redirects=True,
        ) as resp:
            resp.raise_for_status()

            total_bytes = int(resp.headers.get("Content-Length", 0))
            downloaded = 0

            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
                tmp_path = tmp_file.name
                for chunk in resp.iter_content(chunk_size=1024 * 256):  # 256 KB chunks
                    if chunk:
                        tmp_file.write(chunk)
                        downloaded += len(chunk)

        # Validate it's a real ZIP
        if not zipfile.is_zipfile(tmp_path):
            os.unlink(tmp_path)
            return slug, False, "Downloaded file is not a valid ZIP archive"

        shutil.move(tmp_path, dest_path)
        size_mb = dest_path.stat().st_size / (1024 * 1024)
        return slug, True, f"Saved {size_mb:.2f} MB → {dest_path}"

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else "?"
        if status == 404:
            return slug, False, f"HTTP 404 — branch '{branch}' not found (try --branch master)"
        return slug, False, f"HTTP {status}: {e}"
    except Exception as e:
        return slug, False, f"Error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY REPORT
# ─────────────────────────────────────────────────────────────────────────────
def print_summary(results: list[tuple[str, bool, str]], output_dir: Path) -> None:
    success = [r for r in results if r[1]]
    failed  = [r for r in results if not r[1]]

    print("\n" + "═" * 60)
    print("  DOWNLOAD SUMMARY")
    print("═" * 60)
    print(f"  Output directory : {output_dir.resolve()}")
    print(f"  Total repos      : {len(results)}")
    print(f"  ✅ Succeeded     : {len(success)}")
    print(f"  ❌ Failed        : {len(failed)}")

    if failed:
        print("\n  Failed repositories:")
        for slug, _, msg in failed:
            print(f"    • {slug:40s}  {msg}")
    print("═" * 60 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download all Bitbucket workspace repositories as individual ZIP files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment variables (alternative to flags):
  BB_WORKSPACE     Bitbucket workspace slug
  BB_USERNAME      Bitbucket username (or 'x-token-auth' for OAuth tokens)
  BB_APP_PASSWORD  Bitbucket App Password or OAuth2 access token

Examples:
  python bitbucket_repo_downloader.py --workspace myorg --username alice --password xxxx
  BB_WORKSPACE=myorg BB_USERNAME=alice BB_APP_PASSWORD=xxxx python bitbucket_repo_downloader.py
        """,
    )
    parser.add_argument("--workspace",  default=os.getenv("BB_WORKSPACE"),   help="Bitbucket workspace slug")
    parser.add_argument("--username",   default=os.getenv("BB_USERNAME"),    help="Bitbucket username")
    parser.add_argument("--password",   default=os.getenv("BB_APP_PASSWORD"),help="App Password or OAuth token")
    parser.add_argument("--output-dir", default=os.getenv("BB_OUTPUT_DIR", DEFAULT_OUTPUT_DIR), help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--branch",     default=None,  help="Force specific branch for all repos (default: repo's mainbranch)")
    parser.add_argument("--workers",    default=DEFAULT_MAX_WORKERS, type=int, help=f"Parallel download threads (default: {DEFAULT_MAX_WORKERS})")
    parser.add_argument("--filter",     default=None,  help="Only download repos whose slug contains this string (case-insensitive)")
    parser.add_argument("--dry-run",    action="store_true", help="List repos without downloading")
    parser.add_argument("--verbose",    action="store_true", help="Enable DEBUG logging")
    return parser.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main() -> int:
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # ── Validate required args ────────────────────────────────────────────────
    missing = [f for f, v in [("--workspace", args.workspace), ("--username", args.username), ("--password", args.password)] if not v]
    if missing:
        log.error("Missing required arguments: %s", ", ".join(missing))
        log.error("Set them via flags or BB_WORKSPACE / BB_USERNAME / BB_APP_PASSWORD env vars.")
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log.info("Output directory: %s", output_dir.resolve())

    # ── Build session ─────────────────────────────────────────────────────────
    session = build_session(args.username, args.password)

    # ── Fetch repo list ───────────────────────────────────────────────────────
    try:
        repos = list_repositories(session, args.workspace)
    except requests.exceptions.HTTPError as e:
        log.error("Failed to fetch repositories: %s", e)
        if e.response is not None and e.response.status_code == 401:
            log.error("Authentication failed — check your username and App Password.")
        return 1

    # ── Apply filter ──────────────────────────────────────────────────────────
    if args.filter:
        before = len(repos)
        repos = [r for r in repos if args.filter.lower() in r["slug"].lower()]
        log.info("Filter '%s' applied: %d → %d repos", args.filter, before, len(repos))

    if not repos:
        log.warning("No repositories found matching criteria.")
        return 0

    # ── Dry run ───────────────────────────────────────────────────────────────
    if args.dry_run:
        print(f"\n{'SLUG':40s}  {'LANGUAGE':15s}  {'PRIVATE'}")
        print("-" * 65)
        for r in repos:
            print(f"{r['slug']:40s}  {(r.get('language') or '—'):15s}  {'yes' if r.get('is_private') else 'no'}")
        print(f"\nTotal: {len(repos)} repositories (dry run — nothing downloaded)\n")
        return 0

    # ── Download ──────────────────────────────────────────────────────────────
    log.info("Starting download with %d parallel worker(s)...", args.workers)
    results: list[tuple[str, bool, str]] = []
    start_time = time.time()

    def task(repo: dict) -> tuple[str, bool, str]:
        slug = repo["slug"]
        branch = args.branch or get_default_branch(session, args.workspace, slug)
        log.debug("[%s] Using branch: %s", slug, branch)
        result = download_repo_zip(session, args.workspace, slug, branch, output_dir)
        status_icon = "✅" if result[1] else "❌"
        log.info("%s  %-40s  %s", status_icon, slug, result[2])
        return result

    iterator = repos
    if HAS_TQDM:
        iterator = tqdm(repos, desc="Downloading", unit="repo", ncols=80)

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(task, repo): repo for repo in repos}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                slug = futures[future]["slug"]
                results.append((slug, False, str(exc)))

    elapsed = time.time() - start_time
    log.info("All downloads completed in %.1f seconds.", elapsed)

    print_summary(results, output_dir)

    # Exit code: 0 if all succeeded, 2 if some failed
    return 0 if all(r[1] for r in results) else 2


if __name__ == "__main__":
    sys.exit(main())
