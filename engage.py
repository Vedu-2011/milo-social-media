#!/usr/bin/env python3
"""Milo comment engagement bot — official Instagram API, own media only.

Every few hours: fetch recent comments on our posts, auto-reply to clear FAQ
matches (free? / what app? / link?) with rotating templates, log everything
else to engage_log.md for the human. State in engage_state.json. stdlib only.
"""
import json, os, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = "https://graph.instagram.com/v23.0"
STATE = ROOT / "engage_state.json"
LOG = ROOT / "engage_log.md"
OWN = "heymilo999"
MAX_REPLIES = 15

FAQS = [
    (("is it free", "it's free?", "actually free", "free??", "free?"), [
        "100% free, no caps, no card — that's the whole point 🙂",
        "free forever. a student built it because $45/yr to study is insane",
    ]),
    (("what app", "which app", "what's the app", "whats the app", "app name", "name of the app"), [
        "milo 🙂 link in bio — free forever",
        "it's milo — milo-ai-info.vercel.app, free forever",
    ]),
    (("link", "website", "site?"), [
        "milo-ai-info.vercel.app 🙂 free forever",
    ]),
]


def api(path, params=None, method="GET"):
    tok = os.environ["IG_TOKEN"].strip()
    params = {**(params or {}), "access_token": tok}
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        f"{API}{path}" + ("?" + data.decode() if method == "GET" else ""),
        data=None if method == "GET" else data, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"API {e.code} on {path}: {e.read().decode()[:200]}", file=sys.stderr)
        return {}


def main():
    state = json.loads(STATE.read_text()) if STATE.exists() else {"replied": []}
    replied = set(state["replied"])
    new_log, replies_sent = [], 0

    media = api("/me/media", {"fields": "id,caption,timestamp", "limit": "10"}).get("data", [])
    for m in media:
        comments = api(f"/{m['id']}/comments",
                       {"fields": "id,text,username,timestamp", "limit": "50"}).get("data", [])
        for c in comments:
            if c["id"] in replied or c.get("username") == OWN:
                continue
            text = (c.get("text") or "").lower()
            matched = None
            for keys, templates in FAQS:
                if any(k in text for k in keys):
                    matched = templates[hash(c["id"]) % len(templates)]
                    break
            if matched and replies_sent < MAX_REPLIES:
                res = api(f"/{c['id']}/replies", {"message": matched}, "POST")
                if res.get("id"):
                    replied.add(c["id"]); replies_sent += 1
                    print(f"replied to @{c.get('username')}: {text[:60]!r}")
            elif not matched:
                replied.add(c["id"])  # don't re-log next run
                new_log.append(f"- **@{c.get('username')}** on {m['id'][-6:]}: {c.get('text','')[:140]}")

    state["replied"] = sorted(replied)[-2000:]
    STATE.write_text(json.dumps(state))
    if new_log:
        prev = LOG.read_text() if LOG.exists() else "# Comments needing a human reply\n"
        LOG.write_text(prev + "\n" + "\n".join(new_log) + "\n")
    print(f"done: {replies_sent} auto-replies, {len(new_log)} flagged for human")

    subprocess.run(["git", "config", "user.name", "milo-engage"], cwd=ROOT)
    subprocess.run(["git", "config", "user.email", "bot@milo"], cwd=ROOT)
    subprocess.run(["git", "add", "-A"], cwd=ROOT)
    subprocess.run(["git", "commit", "-qm", "engage: state update", "--allow-empty"], cwd=ROOT)
    subprocess.run(["git", "pull", "--rebase", "-q"], cwd=ROOT)
    subprocess.run(["git", "push", "-q"], cwd=ROOT)


if __name__ == "__main__":
    main()
