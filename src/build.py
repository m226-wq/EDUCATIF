"""المرحلة 1: جمع -> توليد -> تحقق -> فيديو. المخرجات في out/."""
import json, os, pathlib, sys, datetime as dt
import yaml
from sources import collect
from generate import produce
from media import render_video

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
SITE = OUT / "site" / "videos"
SITE.mkdir(parents=True, exist_ok=True)
(OUT / "site" / "index.html").write_text("<meta charset=utf-8><title>edu-shorts</title>", encoding="utf-8")

cfg = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
hist = json.loads((ROOT / "data" / "history.json").read_text())
types = [t.strip() for t in os.environ.get("VIDEO_TYPES", "qcm,qa,tips").split(",") if t.strip()]

pool = collect(cfg, hist["used_ids"])
print(f"pool size: {len(pool)} | types: {types}")
if len(pool) < max(len(types), 3):
    sys.exit("مواد غير كافية اليوم")

results = produce(cfg, pool, types)
if not results:
    sys.exit("لم يُنتج أي فيديو اجتاز التحقق")

stamp = dt.datetime.utcnow().strftime("%Y%m%d-%H%M")
manifest = {"stamp": stamp, "videos": [], "used_ids": []}
for v, item in results:
    name = f"{stamp}-{v['type']}.mp4"
    dur = render_video(v, item["source"], cfg, OUT / "work" / v["type"], SITE / name)
    tags = list(dict.fromkeys(v.get("hashtags", []) + cfg["hashtags"]))[:15]
    desc = (f"{v['summary']}\n\nالمصدر: {item['source']}\n{item['url']}\n\n"
            "أُنتج هذا المحتوى بمساعدة الذكاء الاصطناعي انطلاقاً من مصادر علمية منشورة؛ "
            "ننصح بالرجوع إلى المصدر الأصلي.\n\n" + " ".join(tags))
    manifest["videos"].append({"file": name, "title": v["title"][:90], "description": desc,
                               "tags": [t.lstrip("#") for t in tags], "type": v["type"], "duration": round(dur, 1)})
    manifest["used_ids"].append(item["id"])
    print("built", name, round(dur, 1), "s")

(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
