"""المرحلة 2: النشر على يوتيوب وإنستغرام + تحديث السجل."""
import os, json, time, pathlib
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
DRY = os.environ.get("DRY_RUN") == "true"


def upload_youtube(path, title, desc, tags):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                        token_uri="https://oauth2.googleapis.com/token",
                        client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
                        scopes=["https://www.googleapis.com/auth/youtube.upload"])
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    body = {"snippet": {"title": (title + " #Shorts")[:100], "description": desc + "\n#Shorts",
                        "tags": tags, "categoryId": "27", "defaultLanguage": "ar", "defaultAudioLanguage": "ar"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(path), mimetype="video/mp4", resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return resp["id"]


def upload_instagram(video_url, caption):
    ig, tok = os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"]
    base = "https://graph.facebook.com/v21.0"
    for _ in range(30):  # انتظر ظهور الملف على GitHub Pages
        if requests.head(video_url, allow_redirects=True, timeout=30).status_code == 200:
            break
        time.sleep(10)
    r = requests.post(f"{base}/{ig}/media", data={"media_type": "REELS", "video_url": video_url,
                      "caption": caption[:2200], "share_to_feed": "true", "access_token": tok}, timeout=60)
    r.raise_for_status()
    cid = r.json()["id"]
    for _ in range(60):
        s = requests.get(f"{base}/{cid}", params={"fields": "status_code", "access_token": tok}, timeout=30).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") == "ERROR":
            raise RuntimeError(f"instagram processing error: {s}")
        time.sleep(10)
    p = requests.post(f"{base}/{ig}/media_publish", data={"creation_id": cid, "access_token": tok}, timeout=60)
    p.raise_for_status()
    return p.json()["id"]


manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
hist_path = ROOT / "data" / "history.json"
hist = json.loads(hist_path.read_text())
pages = os.environ.get("PAGES_URL", "").rstrip("/")
done_any = False

for v in manifest["videos"]:
    path = OUT / "site" / "videos" / v["file"]
    rec = {"file": v["file"], "title": v["title"]}
    if DRY:
        print("[dry-run]", v["file"], v["title"]); continue
    if all(os.environ.get(k) for k in ("YT_REFRESH_TOKEN", "YT_CLIENT_ID", "YT_CLIENT_SECRET")):
        try:
            rec["youtube"] = upload_youtube(path, v["title"], v["description"], v["tags"]); print("YT ok", rec["youtube"])
        except Exception as ex:
            print("YT failed:", repr(ex)[:300])
    if pages and all(os.environ.get(k) for k in ("IG_USER_ID", "IG_ACCESS_TOKEN")):
        try:
            cap = v["description"].split("\nhttp")[0] + "\n\n" + " ".join("#" + t for t in v["tags"][:15])
            rec["instagram"] = upload_instagram(f"{pages}/videos/{v['file']}", cap); print("IG ok", rec["instagram"])
        except Exception as ex:
            print("IG failed:", repr(ex)[:300])
    if "youtube" in rec or "instagram" in rec:
        done_any = True
        hist["published"].append(rec)

if done_any:
    hist["used_ids"] = (hist["used_ids"] + manifest["used_ids"])[-2000:]
    hist["published"] = hist["published"][-500:]
    hist_path.write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")
