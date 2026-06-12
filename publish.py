#!/usr/bin/env python3
"""Milo IG cloud publisher — runs inside GitHub Actions daily.

Reads social-queue/<slug>/post.json entries due today (or earlier), publishes
them to Instagram via the official Graph API, then moves them to
social-queue/_posted/ and commits. Token comes from the IG_TOKEN env secret.
Media URLs are raw.githubusercontent.com paths to the committed queue files.

stdlib only — no dependencies.
"""
import datetime, json, os, shutil, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "social-queue"
API = "https://graph.instagram.com/v23.0"
RAW = "https://raw.githubusercontent.com/Vedu-2011/milo-social-media/main"


def api(path, params, method="GET"):
    tok = os.environ["IG_TOKEN"].strip()
    params = {**params, "access_token": tok}
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        f"{API}{path}" + ("?" + data.decode() if method == "GET" else ""),
        data=None if method == "GET" else data, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"API error {e.code} on {path}: {e.read().decode()[:400]}")


def wait_finished(cid, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = api(f"/{cid}", {"fields": "status_code"})["status_code"]
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            sys.exit(f"container {cid}: {st}")
        time.sleep(10)
    sys.exit("container timeout")


def publish(folder: Path):
    meta = json.loads((folder / "post.json").read_text())
    slug = folder.name
    url = lambda name: f"{RAW}/social-queue/{urllib.parse.quote(slug)}/{urllib.parse.quote(name)}"
    print(f"== publishing {slug} ({meta['type']})")

    if meta["type"] == "reel":
        params = {"media_type": "REELS", "video_url": url(meta["media"][0]),
                  "caption": meta["caption"], "share_to_feed": "true"}
        if meta.get("cover"):
            params["cover_url"] = url(meta["cover"])
        c = api("/me/media", params, "POST")["id"]
        wait_finished(c)
        res = api("/me/media_publish", {"creation_id": c}, "POST")
    else:
        children = []
        for m in meta["media"]:
            cid = api("/me/media", {"image_url": url(m), "is_carousel_item": "true"}, "POST")["id"]
            children.append(cid)
        for cid in children:
            wait_finished(cid)
        parent = api("/me/media", {"media_type": "CAROUSEL",
                                   "children": ",".join(children),
                                   "caption": meta["caption"]}, "POST")["id"]
        wait_finished(parent)
        res = api("/me/media_publish", {"creation_id": parent}, "POST")

    print("   published:", res.get("id"))
    posted = QUEUE / "_posted"
    posted.mkdir(exist_ok=True)
    shutil.move(str(folder), str(posted / slug))


def main():
    dry = "--dry-run" in sys.argv
    today = datetime.date.today().isoformat()
    due = sorted(
        f for f in QUEUE.iterdir()
        if f.is_dir() and not f.name.startswith("_")
        and json.loads((f / "post.json").read_text())["date"] <= today)
    if not due:
        print("nothing due"); return
    for f in due:
        if dry:
            print("DUE:", f.name)
        else:
            publish(f)
    if not dry:
        subprocess.run(["git", "config", "user.name", "milo-publisher"], cwd=ROOT, check=True)
        subprocess.run(["git", "config", "user.email", "bot@milo"], cwd=ROOT, check=True)
        subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
        subprocess.run(["git", "commit", "-m", f"posted: {today}", "--allow-empty"], cwd=ROOT, check=True)
        subprocess.run(["git", "push"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
