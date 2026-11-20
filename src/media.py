"""صوت (edge-tts) + ترجمة متزامنة + موسيقى + تركيب ffmpeg => فيديو عمودي 1080x1920."""
import asyncio, os, random, subprocess, pathlib, functools
import edge_tts, arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont
from textutil import split_chunks

W, H = 1080, 1920
THEMES = {
    "qcm":  ((20, 30, 110), (0, 140, 190), "اختبر معلوماتك"),
    "qa":   ((70, 20, 130), (220, 40, 110), "سؤال وجواب"),
    "tips": ((0, 70, 60), (30, 160, 140), "اقتراحات للأستاذ"),
}
ROOT = pathlib.Path(__file__).resolve().parent.parent


def shape(s):
    return get_display(arabic_reshaper.reshape(s))


@functools.lru_cache(maxsize=1)
def font_path():
    if os.environ.get("FONT_PATH"):
        return os.environ["FONT_PATH"]
    for fam in ("Noto Sans Arabic:bold", "Noto Naskh Arabic:bold", "Amiri:bold"):
        p = subprocess.run(["fc-match", "-f", "%{file}", fam], capture_output=True, text=True).stdout
        if p and ("rabic" in p or "Amiri" in p):
            return p
    raise RuntimeError("لم يتم العثور على خط عربي: ثبّت fonts-noto-core أو حدّد FONT_PATH")


@functools.lru_cache(maxsize=64)
def load_font(size):
    f = ImageFont.truetype(font_path(), size)
    try:
        f.set_variation_by_name("Bold")
    except Exception:
        pass
    return f


def wrap(draw, text, font, maxw):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for w in para.split():
            t = (cur + " " + w).strip()
            if draw.textlength(shape(t), font=font) <= maxw:
                cur = t
            else:
                if cur: lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def fit(draw, text, maxw, maxh, hi, lo, spacing=1.5):
    for size in range(hi, lo - 1, -4):
        f = load_font(size)
        lines = wrap(draw, text, f, maxw)
        if len(lines) * int(size * spacing) <= maxh:
            break
    return f, lines, int(size * spacing)


def draw_frame(vtype, main, caption, progress, channel, source, out_png, big_caption=False):
    c1, c2, label = THEMES[vtype]
    grad = Image.linear_gradient("L").resize((W, H))
    img = Image.composite(Image.new("RGB", (W, H), c2), Image.new("RGB", (W, H), c1), grad).convert("RGBA")
    deco = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(deco)
    dd.ellipse([-250, 1250, 450, 1950], fill=(255, 255, 255, 18))
    dd.ellipse([700, -200, 1300, 400], fill=(255, 255, 255, 22))
    img = Image.alpha_composite(img, deco)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, int(W * progress), 14], fill=(255, 255, 255, 255))
    d.text((W / 2, 120), shape(channel), font=load_font(54), fill="white", anchor="mm")
    pf = load_font(46)
    pw = d.textlength(shape(label), font=pf) + 80
    d.rounded_rectangle([W / 2 - pw / 2, 190, W / 2 + pw / 2, 270], radius=40, fill="white")
    d.text((W / 2, 230), shape(label), font=pf, fill=c1, anchor="mm")
    # النص الرئيسي
    f, lines, lh = fit(d, main, W - 160, 880, 88, 44)
    y = 360 + (880 - len(lines) * lh) / 2
    for ln in lines:
        d.text((W / 2, y), shape(ln), font=f, fill="white", anchor="ma")
        y += lh
    # الترجمة المتزامنة داخل لوحة شفافة
    if caption:
        panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(panel).rounded_rectangle([60, 1300, W - 60, 1720], radius=44, fill=(0, 0, 0, 105))
        img = Image.alpha_composite(img, panel)
        d = ImageDraw.Draw(img)
        if big_caption:
            d.text((W / 2, 1510), caption, font=load_font(220), fill="white", anchor="mm")
        else:
            cf, cl, clh = fit(d, caption, W - 220, 340, 56, 36, 1.45)
            cy = 1510 - len(cl) * clh / 2
            for ln in cl:
                d.text((W / 2, cy), shape(ln), font=cf, fill=(255, 235, 150), anchor="ma")
                cy += clh
    d.text((W / 2, 1805), shape("المصدر: " + source)[:200], font=load_font(34), fill=(225, 235, 245), anchor="mm")
    img.convert("RGB").save(out_png)


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


async def _tts_all(jobs, voice, rate):
    sem = asyncio.Semaphore(4)

    async def one(text, path):
        async with sem:
            for attempt in range(4):
                try:
                    await edge_tts.Communicate(text, voice, rate=rate).save(str(path)); return
                except Exception:
                    if attempt == 3: raise
                    await asyncio.sleep(2 * (attempt + 1))
    await asyncio.gather(*(one(t, p) for t, p in jobs))


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def make_music(duration, path, volume_src_dir):
    tracks = sorted(pathlib.Path(volume_src_dir).glob("*.mp3"))
    if tracks:                                  # موسيقى يضعها المستخدم
        ff("-stream_loop", "-1", "-i", str(random.choice(tracks)), "-t", f"{duration:.2f}",
           "-af", f"afade=t=out:st={max(duration - 1.5, 0):.2f}:d=1.5", "-ar", "44100", "-ac", "2", str(path))
        return
    d = f"{duration:.2f}"                       # موسيقى هادئة مولَّدة (لا مشاكل حقوق)
    ff("-f", "lavfi", "-i", f"sine=f=110:d={d}", "-f", "lavfi", "-i", f"sine=f=220:d={d}",
       "-f", "lavfi", "-i", f"sine=f=277.18:d={d}", "-f", "lavfi", "-i", f"sine=f=329.63:d={d}",
       "-filter_complex", f"[0][1][2][3]amix=inputs=4,lowpass=f=900,tremolo=f=0.25:d=0.6,"
       f"afade=t=out:st={max(duration - 1.5, 0):.2f}:d=1.5,aformat=sample_rates=44100:channel_layouts=stereo[m]",
       "-map", "[m]", str(path))


def render_video(video, source, cfg, workdir, out_mp4):
    wd = pathlib.Path(workdir); wd.mkdir(parents=True, exist_ok=True)
    # 1) تفكيك المشاهد إلى مقاطع (ترجمة متزامنة)
    chunks = []
    for sc in video["scenes"]:
        narr = (sc.get("narration") or "").strip()
        if narr:
            for c in split_chunks(narr):
                chunks.append({"main": sc["on_screen"], "text": c})
        else:
            for k in range(int(sc.get("pause") or 3), 0, -1):
                chunks.append({"main": sc["on_screen"], "silent": 1.0, "count": str(k)})
    # 2) كل الأصوات بالتوازي
    jobs = []
    for i, c in enumerate(chunks):
        if "text" in c:
            c["mp3"] = wd / f"c{i}.mp3"; jobs.append((c["text"], c["mp3"]))
    asyncio.run(_tts_all(jobs, cfg["voice"], cfg["voice_rate"]))
    # 3) إطار + مقطع فيديو لكل جزء
    segs = []
    for i, c in enumerate(chunks):
        png, seg = wd / f"c{i}.png", wd / f"c{i}.mp4"
        draw_frame(video["type"], c["main"], c.get("text") or c.get("count"), (i + 1) / len(chunks),
                   cfg["channel_name"], source, png, big_caption="count" in c)
        if "text" in c:
            dur = probe(c["mp3"]) + 0.30
            audio = ["-i", str(c["mp3"]), "-af", "apad"]
        else:
            dur = c["silent"]
            audio = ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        ff("-loop", "1", "-framerate", "30", "-i", str(png), *audio, "-t", f"{dur:.2f}",
           "-vf", "fade=t=in:st=0:d=0.18,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-r", "30",
           "-c:a", "aac", "-ar", "44100", "-ac", "2", str(seg))
        segs.append(seg)
    lst = wd / "list.txt"
    lst.write_text("".join(f"file '{s.resolve()}'\n" for s in segs))
    raw = wd / "raw.mp4"
    ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(raw))
    # 4) موسيقى خلفية خافتة
    total = probe(raw)
    music = wd / "music.wav"
    make_music(total, music, ROOT / "assets" / "music")
    vol = float(cfg.get("music_volume", 0.10))
    ff("-i", str(raw), "-i", str(music), "-filter_complex",
       f"[0:a]volume=1.5[v];[1:a]volume={vol}[m];[v][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
       "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out_mp4))
    return probe(out_mp4)
