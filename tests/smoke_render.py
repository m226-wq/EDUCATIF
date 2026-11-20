"""اختبار محلي للتركيب بدون شبكة: يستبدل edge-tts و reshaper بنسخ وهمية. FONT_PATH يجب أن يشير لأي خط."""
import sys, types, subprocess, pathlib, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
for name in ("arabic_reshaper", "bidi", "bidi.algorithm", "edge_tts"):
    if name in sys.modules: continue
    try: __import__(name)
    except ImportError:
        m = types.ModuleType(name); sys.modules[name] = m
        if name == "arabic_reshaper": m.reshape = lambda s: s
        if name == "bidi.algorithm": m.get_display = lambda s: s
        if name == "edge_tts":
            class C:
                def __init__(self, t, v, rate=None): self.t = t
                async def save(self, p):
                    d = max(len(self.t.split()) * 0.4, 0.8)
                    subprocess.run(["ffmpeg","-y","-loglevel","error","-f","lavfi","-i",f"sine=f=300:d={d}","-ar","24000","-ac","1",p],check=True)
            m.Communicate = C
sys.modules["bidi"].algorithm = sys.modules["bidi.algorithm"]
import random; random.seed(1)
os.environ.setdefault("FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
from generate import build_qcm_scenes
from media import render_video
q = {"hook": "Did you know that spaced practice helps memory?", "question": "Which strategy improved retention in the study?",
     "options": ["Spaced review over weeks", "Cramming the night before", "Rereading once"], "correct": 0,
     "explanation": "The study found spaced review produced better retention than massed practice. Teachers can schedule short reviews.", "cta": "Follow us for more."}
v = {"type": "qcm", "scenes": build_qcm_scenes(q)}
cfg = {"voice": "x", "voice_rate": "+0%", "channel_name": "Test channel", "music_volume": 0.1}
out = pathlib.Path("/tmp/smoke"); out.mkdir(exist_ok=True)
print("duration", render_video(v, "Journal X", cfg, out / "w", out / "t.mp4"))
