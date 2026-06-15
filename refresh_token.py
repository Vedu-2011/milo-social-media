#!/usr/bin/env python3
"""Refresh the long-lived Instagram-login token (ig_refresh_token). Each refresh
rolls the 60-day clock forward, so running this periodically keeps the token alive
forever.

  python3 refresh_token.py            -> read ~/.config/milo/ig_token, refresh,
                                         write it back, update the gh secret (local)
  IG_TOKEN=... python3 refresh_token.py --print
                                      -> refresh and print ONLY the new token to
                                         stdout (logs to stderr) for CI capture
stdlib only."""
import json, os, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path

PRINT_ONLY = "--print" in sys.argv
TOKEN_FILE = Path.home() / ".config/milo/ig_token"

def log(*a):
    print(*a, file=sys.stderr)

token = (os.environ.get("IG_TOKEN") or
         (TOKEN_FILE.read_text().strip() if TOKEN_FILE.exists() else "")).strip()
if not token:
    log("no token found (set IG_TOKEN or ~/.config/milo/ig_token)")
    sys.exit(1)

params = urllib.parse.urlencode({"grant_type": "ig_refresh_token", "access_token": token})
url = f"https://graph.instagram.com/refresh_access_token?{params}"
try:
    with urllib.request.urlopen(url) as r:
        data = json.loads(r.read())
except urllib.error.HTTPError as e:
    log(f"refresh failed {e.code}: {e.read().decode()[:200]}")
    sys.exit(1)

new_token = data.get("access_token")
if not new_token:
    log("ERROR: no access_token in response:", data)
    sys.exit(1)

days = int(data.get("expires_in", 0)) // 86400
log(f"refreshed: token now valid ~{days} days")

if PRINT_ONLY:
    print(new_token)  # stdout: token only
else:
    TOKEN_FILE.write_text(new_token)
    log(f"saved to {TOKEN_FILE}")
    res = subprocess.run(
        ["gh", "secret", "set", "IG_TOKEN", "--repo", "Vedu-2011/milo-social-media"],
        input=new_token.encode(), capture_output=True)
    log("GitHub secret updated" if res.returncode == 0
        else f"gh secret update failed: {res.stderr.decode()}")
