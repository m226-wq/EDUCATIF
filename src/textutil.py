"""أدوات نصية خفيفة بلا اعتماديات خارجية (قابلة للاختبار)."""
import re

DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
LATIN = re.compile(r"[A-Za-z]")


def norm(s):
    return str(s).translate(DIGITS).replace("٪", "%").replace("٫", ".")


def deep_norm(o):
    if isinstance(o, str): return norm(o)
    if isinstance(o, list): return [deep_norm(i) for i in o]
    if isinstance(o, dict): return {k: deep_norm(v) for k, v in o.items()}
    return o


def words(s):
    return len(s.split())


def split_chunks(text, max_words=11):
    """يقسّم النص المنطوق إلى مقاطع قصيرة تصلح كترجمة متزامنة."""
    text = " ".join((text or "").split())
    if not text:
        return []
    sents = [s for s in re.split(r"(?<=[\.\!\?؟…؛:])\s+", text) if s.strip()]
    chunks = []
    for s in sents:
        if words(s) <= max_words:
            chunks.append(s); continue
        parts = [p for p in re.split(r"(?<=[،,])\s+", s) if p.strip()]
        cur = ""
        for p in parts:
            if cur and words(cur + " " + p) > max_words:
                chunks.append(cur); cur = p
            else:
                cur = (cur + " " + p).strip()
        if cur: chunks.append(cur)
    out = []
    for c in chunks:                      # تقسيم إجباري لما بقي طويلاً
        w = c.split()
        for i in range(0, len(w), max_words + 3):
            out.append(" ".join(w[i:i + max_words + 3]))
    merged = []                           # دمج المقاطع القصيرة جداً مع ما قبلها
    for c in out:
        if merged and words(c) <= 3 and words(merged[-1]) + words(c) <= max_words + 3:
            merged[-1] += " " + c
        else:
            merged.append(c)
    return merged


def script_problems(v, lo=60, hi=170):
    """فحوص آلية للسيناريو؛ تعيد قائمة مشاكل (فارغة = سليم)."""
    pr = []
    sc = v.get("scenes", [])
    if len(sc) < 4: pr.append("عدد المشاهد أقل من 4")
    narr = " ".join(s.get("narration", "") for s in sc)
    n = words(narr)
    if not lo <= n <= hi: pr.append(f"عدد الكلمات المنطوقة {n} خارج المجال {lo}-{hi}")
    if LATIN.search(narr): pr.append("النص المنطوق يحتوي حروفاً لاتينية؛ اكتبها بالعربية")
    for s in sc:
        if not s.get("on_screen"): pr.append("مشهد بلا نص معروض")
        elif words(s["on_screen"]) > 22: pr.append("نص معروض طويل جداً")
    return pr
