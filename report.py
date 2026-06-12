#!/usr/bin/env python3
"""Weekly analytics report — pulls per-post insights via official API,
writes reports/week-of-YYYY-MM-DD.md, committed by the workflow. stdlib only."""
import datetime, json, os, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = "https://graph.instagram.com/v23.0"


def api(path, params=None):
    tok = os.environ["IG_TOKEN"].strip()
    params = {**(params or {}), "access_token": tok}
    url = f"{API}{path}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"API {e.code} on {path}: {e.read().decode()[:200]}", file=sys.stderr)
        return {}


def media_insights(mid):
    out = {}
    for metric in ("views", "reach", "likes", "comments", "saved", "shares", "total_interactions"):
        d = api(f"/{mid}/insights", {"metric": metric}).get("data", [])
        if d and d[0].get("values"):
            out[metric] = d[0]["values"][0].get("value", 0)
    return out


def main():
    me = api("/me", {"fields": "username,followers_count,media_count"})
    rows = []
    media = api("/me/media", {"fields": "id,caption,media_type,timestamp,permalink", "limit": "25"}).get("data", [])
    cutoff = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
    for m in media:
        if m.get("timestamp", "")[:10] < cutoff:
            continue
        ins = media_insights(m["id"])
        cap = (m.get("caption") or "").split("\n")[0][:60]
        rows.append((m.get("timestamp", "")[:10], cap, m.get("media_type", ""), ins, m.get("permalink", "")))

    rows.sort(key=lambda r: -(r[3].get("views") or r[3].get("reach") or 0))
    today = datetime.date.today().isoformat()
    lines = [f"# Week of {today} — @{me.get('username')} ({me.get('followers_count','?')} followers)\n",
             "| date | post | type | views | reach | likes | comments | saves | shares |",
             "|---|---|---|---|---|---|---|---|---|"]
    for d, cap, typ, ins, link in rows:
        lines.append(f"| {d} | [{cap}]({link}) | {typ} | {ins.get('views','—')} | {ins.get('reach','—')} | "
                     f"{ins.get('likes','—')} | {ins.get('comments','—')} | {ins.get('saved','—')} | {ins.get('shares','—')} |")
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / f"week-of-{today}.md").write_text("\n".join(lines) + "\n")
    print(f"report written: {len(rows)} posts, followers={me.get('followers_count')}")

    subprocess.run(["git", "config", "user.name", "milo-report"], cwd=ROOT)
    subprocess.run(["git", "config", "user.email", "bot@milo"], cwd=ROOT)
    subprocess.run(["git", "add", "-A"], cwd=ROOT)
    subprocess.run(["git", "commit", "-qm", f"report: {today}", "--allow-empty"], cwd=ROOT)
    subprocess.run(["git", "pull", "--rebase", "-q"], cwd=ROOT)
    subprocess.run(["git", "push", "-q"], cwd=ROOT)


if __name__ == "__main__":
    main()
