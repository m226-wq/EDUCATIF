"""توليد المحتوى عبر Groq: اختيار -> كتابة -> تحقق علمي آلي."""
import os, json, time, random, requests
from textutil import deep_norm, script_problems

URL = "https://api.groq.com/openai/v1/chat/completions"

BASE = """أنت محرر علمي محترف لقناة تعليمية عربية متخصصة في علوم التربية: الديداكتيك، البيداغوجيا، علم نفس النمو، علم النفس التربوي، تكوين الأساتذة، التقويم.
الجمهور: أساتذة ومفتشون وطلبة مراكز التكوين ومترشحو مباريات التعليم.
قواعد صارمة:
1. اعتمد فقط على نص المصدر المقدم. ممنوع اختلاق نتائج أو أرقام أو أسماء باحثين أو مؤسسات. إن لم يذكر المصدر رقماً فلا تذكر رقماً.
2. صغ النتائج بحذر علمي ("تشير دراسة نُشرت في ..."، "تقترح النتائج ...") ولا تعمّم أكثر مما في المصدر.
3. عربية فصيحة مبسطة وسليمة بجمل قصيرة تُقرأ بسهولة. لا تستعمل اللهجة.
4. اكتب كل الأرقام بالأرقام اللاتينية العادية 0 1 2 3 4 5 6 7 8 9 وليس بالهندية.
5. النص المنطوق (narration) بلا إيموجي ولا رموز ولا حروف لاتينية: أسماء المجلات والمنظمات تُكتب بالعربية (مثال: منظمة التعاون والتنمية الاقتصادية).
6. أخرج JSON صالحاً فقط، بلا أي نص خارجه."""

TYPE_SPECS = {
    "qa": """النوع: سؤال وجواب. 5 إلى 7 مشاهد، حوالي 100 إلى 130 كلمة منطوقة في المجموع:
(1) جملة جذب تثير الفضول + سؤال يطرحه الأستاذ، (2-3) الجواب المبسط وفق المصدر، (4) ماذا يعني هذا لقسمي؟ بتطبيق عملي واحد، (5) دعوة قصيرة للمتابعة والتعليق.
النص المعروض on_screen أقصى 14 كلمة للمشهد.
الشكل: {"title":"عنوان جذاب ≤70 حرفاً","summary":"جملة تلخص الفيديو","hashtags":["#..","#.."],"scenes":[{"on_screen":"..","narration":".."}]}""",
    "tips": """النوع: اقتراحات تطبيقية. 5 إلى 7 مشاهد، حوالي 100 إلى 130 كلمة منطوقة:
(1) جملة جذب + ما المستجد العلمي باختصار، (2-4) ثلاثة اقتراحات عملية قابلة للتنفيذ في القسم غداً وكل واحد مشهد، ومرتبطة فعلاً بما ورد في المصدر، (5) دعوة للمتابعة.
النص المعروض on_screen أقصى 14 كلمة للمشهد. لا تقدم اقتراحاً لا يسنده المصدر.
الشكل: {"title":"..","summary":"..","hashtags":[".."],"scenes":[{"on_screen":"..","narration":".."}]}""",
    "qcm": """النوع: سؤال اختيار من متعدد مبني على المستجد. أخرج:
{"title":"عنوان جذاب ≤70 حرفاً","summary":"..","hashtags":[".."],
 "hook":"جملة جذب قصيرة منطوقة","question":"السؤال (≤18 كلمة)","options":["خيار","خيار","خيار"],"correct":0,
 "explanation":"شرح علمي قصير للجواب الصحيح بحسب المصدر (35 إلى 55 كلمة)","cta":"دعوة قصيرة للمتابعة"}
شروط: 3 خيارات بالضبط، خيار واحد صحيح فقط (correct = فهرسه من 0)، المشتتات معقولة ومن الميدان نفسه، كل خيار ≤10 كلمات، السؤال يقيس فهم النتيجة أو دلالتها لا حفظ رقم.""",
}


def chat(cfg, system, user, temperature=0.5, max_tokens=2500):
    key = os.environ["GROQ_API_KEY"]
    last = ""
    for model in cfg["groq_models"]:
        for attempt in range(3):
            try:
                r = requests.post(URL, headers={"Authorization": f"Bearer {key}"}, timeout=120, json={
                    "model": model, "temperature": temperature, "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
            except requests.RequestException as ex:
                last = repr(ex); time.sleep(5); continue
            if r.status_code == 200:
                try:
                    return json.loads(r.json()["choices"][0]["message"]["content"])
                except Exception as ex:
                    last = "bad json: " + repr(ex)[:100]; continue
            if r.status_code == 429:
                wait = float(r.headers.get("retry-after", 20)); last = "429"
                if wait > 90: break               # حصة يومية منتهية -> النموذج التالي
                time.sleep(wait + 1); continue
            if r.status_code >= 500:
                last = f"{r.status_code}"; time.sleep(5 * (attempt + 1)); continue
            last = f"{model}: {r.status_code} {r.text[:150]}"; break   # 400/404 -> النموذج التالي
        print("groq model failed:", model, last)
    raise RuntimeError("Groq: " + last)


def select(cfg, pool):
    lst = "\n".join(f"[{it['idx']}] ({it['source']}) {it['title']} :: {it['summary'][:260]}" for it in pool)
    out = chat(cfg, BASE, "اختر من القائمة ما يهم الأستاذ في عمله مباشرة (التدريس، التعلم، التقويم، نمو الطفل والمراهق، الديداكتيك). "
               "رتّب أفضل 6 مواد من الأهم، وتجنب ما كان بعيداً عن التعليم أو غامضاً أو تقنياً بحتاً.\n\n" + lst +
               '\n\nالشكل: {"picks":[رقم,رقم,...]}', temperature=0.2, max_tokens=200)
    picks = [int(i) for i in out.get("picks", []) if str(i).lstrip("-").isdigit() and 0 <= int(i) < len(pool)]
    return list(dict.fromkeys(picks)) or list(range(len(pool)))


def build_qcm_scenes(q):
    letters = ["أ", "ب", "ج"]
    opts = [str(o).strip() for o in q["options"]][:3]
    assert len(opts) == 3 and int(q["correct"]) in (0, 1, 2)
    order = list(range(3)); random.shuffle(order)            # توزيع عشوائي لموضع الجواب
    shuffled = [opts[i] for i in order]
    ci = order.index(int(q["correct"]))
    listing = "\n".join(f"{letters[i]}) {o}" for i, o in enumerate(shuffled))
    spoken = " ".join(f"الخيار {letters[i]}: {o}." for i, o in enumerate(shuffled))
    return [
        {"on_screen": q["question"], "narration": f"{q['hook'].strip()} {q['question'].strip()}"},
        {"on_screen": listing, "narration": spoken},
        {"on_screen": "فكّر قليلاً ...", "narration": "", "pause": 5},
        {"on_screen": f"الجواب الصحيح:\n{letters[ci]}) {shuffled[ci]}",
         "narration": f"الجواب الصحيح هو الخيار {letters[ci]}. {q['explanation'].strip()}"},
        {"on_screen": "تابعنا للمزيد من المستجدات", "narration": q["cta"].strip()},
    ]


def write(cfg, vtype, item, feedback=""):
    user = (f"المصدر ({item['source']}):\nالعنوان: {item['title']}\nالنص: {item['summary']}\n\n{TYPE_SPECS[vtype]}")
    if feedback:
        user += f"\n\nتصحيح مطلوب من محاولتك السابقة: {feedback}"
    v = deep_norm(chat(cfg, BASE, user, temperature=0.55, max_tokens=2200))
    if vtype == "qcm":
        v["scenes"] = build_qcm_scenes(v)
    v["type"] = vtype
    return v


def verify(cfg, v, item):
    narr = " ".join(s.get("narration", "") for s in v["scenes"])
    out = chat(cfg, "أنت مدقق علمي صارم. أخرج JSON فقط.",
               f"نص المصدر:\n{item['title']}\n{item['summary']}\n\nنص الفيديو:\n{narr}\n\n"
               "تحقق: (1) هل كل ادعاء علمي أو رقم أو اسم في نص الفيديو مدعوم صراحة بنص المصدر؟ (2) هل هناك تعميم مبالغ فيه؟ "
               "(3) إن كان الفيديو اختباراً فهل الجواب الصحيح وحده مدعوم بالمصدر؟ (4) هل اللغة العربية سليمة؟\n"
               'الشكل: {"ok":true|false,"problems":"وصف موجز للمشاكل أو فارغ"}', temperature=0, max_tokens=300)
    return bool(out.get("ok")), str(out.get("problems", ""))


def write_verified(cfg, vtype, item):
    feedback = ""
    for attempt in range(3):
        try:
            v = write(cfg, vtype, item, feedback)
        except Exception as ex:
            feedback = f"الشكل غير صحيح ({ex}); التزم بالشكل المطلوب حرفياً."; continue
        pr = script_problems(v)
        if pr:
            feedback = "؛ ".join(pr); print(" format problems:", feedback); continue
        ok, problems = verify(cfg, v, item)
        if ok:
            return v
        feedback = "المدقق العلمي رفض: " + problems; print(" verifier:", problems)
    return None


def produce(cfg, pool, types):
    ranked = select(cfg, pool)
    used, results = set(), []
    for t in types:
        for idx in ranked:
            if idx in used: continue
            print(f"[{t}] trying item {idx}: {pool[idx]['title'][:70]}")
            v = write_verified(cfg, t, pool[idx])
            if v:
                used.add(idx); results.append((v, pool[idx])); break
    return results
