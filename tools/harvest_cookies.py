"""
tools/harvest_cookies.py
Harvest browser cookies from real Edge sessions and push them to GitHub secrets.

Run this locally whenever you get bot-blocked (DataDome resets fix in minutes)
or your Facebook session expires (~90 days).

Usage:
    python tools/harvest_cookies.py

Edge is used instead of Chrome so the harvest doesn't interfere with your
normal browsing. Since you don't use Edge daily, the profile is never locked.

The script opens each site and polls until the target cookie appears — no
keyboard input needed. Just interact with the browser (log in, solve puzzles)
and the script will detect when it's done automatically.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

EDGE_USER_DATA = Path.home() / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data"

POLL_INTERVAL = 3   # seconds between cookie checks
MAX_WAIT      = 180  # seconds before giving up on a site

# Each entry describes one site to harvest. Add new sites here as needed.
SITES = [
    {
        "name": "Facebook Marketplace",
        "url": "https://www.facebook.com",
        # Matches OverlandFinder's facebook_scraper.py: FB_COOKIES = full JSON cookie array
        # 'c_user' is the Facebook user-ID cookie — only present when logged in
        "secret_name": "FB_COOKIES",
        "mode": "all_cookies",
        "domain_filter": "facebook.com",
        "wait_for_cookie": "c_user",
        "verify_url": "https://www.facebook.com/marketplace/vehicles/",
    },
    {
        "name": "RVTrader (DataDome)",
        "url": "https://www.rvtrader.com",
        # DataDome sets a single 'datadome' cookie that authorises subsequent requests
        "secret_name": "RVTRADER_DATADOME",
        "mode": "single_cookie",
        "cookie_name": "datadome",
        "wait_for_cookie": "datadome",
    },
]


def push_secret(name: str, value: str) -> bool:
    proc = subprocess.run(
        ["gh", "secret", "set", name, "--body", value],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(f"    gh error: {proc.stderr.strip()}")
    return proc.returncode == 0


def _kill_edge() -> None:
    """Kill any running Edge processes so Playwright can own the profile lock."""
    result = subprocess.run(
        ["taskkill", "/F", "/IM", "msedge.exe"],
        capture_output=True, text=True,
    )
    if "SUCCESS" in result.stdout:
        print("Closed running Edge instance.")
        time.sleep(2)


def _wait_for_cookie(context, url: str, cookie_name: str) -> bool:
    """Poll until the named cookie appears, or MAX_WAIT seconds elapse."""
    deadline = time.time() + MAX_WAIT
    elapsed = 0
    while time.time() < deadline:
        cookies = context.cookies(url)
        if any(c.get("name") == cookie_name for c in cookies):
            return True
        if elapsed % 15 == 0:
            remaining = int(deadline - time.time())
            print(f"  Waiting for '{cookie_name}' cookie ... ({remaining}s remaining)")
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
    return False


def harvest() -> None:
    print(f"Edge profile: {EDGE_USER_DATA}\n")
    if not EDGE_USER_DATA.exists():
        print("ERROR: Edge user data directory not found. Is Edge installed?")
        sys.exit(1)

    _kill_edge()

    results: list[tuple[str, bool]] = []

    with sync_playwright() as pw:
        # Strip only the flags that crash a real user profile; keep --remote-debugging-pipe
        # and other flags Playwright needs to connect to and control the browser.
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(EDGE_USER_DATA),
            channel="msedge",
            headless=False,
            ignore_default_args=[
                "--disable-extensions",
                "--disable-sync",
                "--no-service-autorun",
                "--disable-default-apps",
                "--disable-component-update",
            ],
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
                "--profile-directory=Default",
            ],
            locale="en-US",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        for site in SITES:
            print(f"\n[{site['name']}] -> {site['url']}")
            try:
                page.goto(site["url"], wait_until="load", timeout=60_000)
            except Exception as e:
                print(f"  FAIL Navigation failed: {e}")
                results.append((site["secret_name"], False))
                continue

            wait_cookie = site.get("wait_for_cookie", "")
            verify_url = site.get("verify_url", "")
            if wait_cookie:
                print(f"  Log in / solve any puzzle in the browser window.")
                print(f"  Script will auto-continue once '{wait_cookie}' cookie appears.")
                found = _wait_for_cookie(context, site["url"], wait_cookie)
                if not found:
                    print(f"  FAIL Timed out waiting for '{wait_cookie}' after {MAX_WAIT}s")
                    results.append((site["secret_name"], False))
                    continue
                print(f"  '{wait_cookie}' detected — verifying session is active...")
                if verify_url:
                    try:
                        page.goto(verify_url, wait_until="domcontentloaded", timeout=30_000)
                        time.sleep(3)
                        if "login" in page.url.lower() or "checkpoint" in page.url.lower():
                            print(f"  FAIL Session invalid — redirected to login. Log out of Facebook in Edge and log back in fresh, then re-run.")
                            results.append((site["secret_name"], False))
                            continue
                        print(f"  Session verified active.")
                    except Exception as e:
                        print(f"  WARNING Could not verify session: {e} — capturing anyway.")
                else:
                    print(f"  '{wait_cookie}' detected — capturing cookies.")
            else:
                time.sleep(5)

            cookies = context.cookies(site["url"])

            if site["mode"] == "all_cookies":
                domain = site.get("domain_filter", "")
                if domain:
                    cookies = [c for c in cookies if domain in c.get("domain", "")]
                print(f"  {len(cookies)} cookies captured for {domain}")
                value = json.dumps(cookies)
                ok = push_secret(site["secret_name"], value)
                status = "OK stored" if ok else "FAIL push failed"
                print(f"  {status}: {site['secret_name']}")
                results.append((site["secret_name"], ok))

            elif site["mode"] == "single_cookie":
                cookie_name = site["cookie_name"]
                cookie_map = {c.get("name", ""): c.get("value", "") for c in cookies if c.get("name")}
                value = cookie_map.get(cookie_name, "")
                if not value:
                    available = [k for k in cookie_map if "dome" in k.lower() or "dd" in k.lower()]
                    print(f"  FAIL '{cookie_name}' not found")
                    print(f"  DataDome-adjacent cookies: {available or list(cookie_map.keys())[:8]}")
                    results.append((site["secret_name"], False))
                    continue
                print(f"  OK {cookie_name}: {len(value)} chars")
                ok = push_secret(site["secret_name"], value)
                status = "OK stored" if ok else "FAIL push failed"
                print(f"  {status}: {site['secret_name']}")
                results.append((site["secret_name"], ok))

        context.close()

    print("\n" + "=" * 52)
    print("SUMMARY")
    print("=" * 52)
    for secret_name, ok in results:
        mark = "OK" if ok else "FAIL"
        print(f"  {mark}  {secret_name}")

    failed = sum(1 for _, ok in results if not ok)
    if failed:
        print(f"\n{failed} secret(s) failed — check `gh auth status` and retry.")
        sys.exit(1)
    print(f"\nAll {len(results)} secret(s) stored. Re-run the scraper workflow to pick them up.")


if __name__ == "__main__":
    harvest()
