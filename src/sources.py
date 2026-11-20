"""جمع المستجدات من Crossref (مجلات محكّمة) + ERIC + RSS."""
import re, html, random, datetime as dt
import requests, feedparser

UA = "edu-shorts-bot/1.0"
TIMEOUT = 30


def clean(t):
    t = re.sub(r"<[^>]+>", " ", t or "")
    t = re.sub(r"^\s*abstract\s*", "", html.unescape(t), flags=re.I)
    return re.sub(r"\s+", " ", t).strip()


def from_crossref(issn, name, days, mailto):
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    r = requests.get(
        "https://api.crossref.org/works",
        params={"filter": f"issn:{issn},from-pub-date:{since},type:journal-article",
                "sort": "published", "order": "desc", "rows": 15, "mailto": mailto},
        headers={"User-Agent": f"{UA} (mailto:{mailto})"}, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for w in r.json()["message"]["items"]:
        title = clean((w.get("title") or [""])[0])
        out.append(dict(id="doi:" + w["DOI"], title=title, summary=clean(w.get("abstract")),
                        url=w.get("URL"), source=name, kind="research"))
    return out


def from_eric(query, days):
    year = dt.date.today().year
    r = requests.get(
        "https://api.ies.ed.gov/eric/",
        params={"search": f"({query}) AND publicationdateyear:{year}", "format": "json",
                "rows": 15, "fields": "id,title,description,source,publicationdateyear"},
        headers={"User-Agent": UA}, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for d in r.json().get("response", {}).get("docs", []):
        out.append(dict(id="eric:" + d["id"], title=clean(d.get("title")), summary=clean(d.get("description")),
                        url=f"https://eric.ed.gov/?id={d['id']}", source="ERIC - " + (d.get("source") or "IES"),
                        kind="research"))
    return out


def from_rss(name, url):
    f = feedparser.parse(url, agent=UA)
    out = []
    for e in f.entries[:10]:
        out.append(dict(id=e.get("id") or e.get("link"), title=clean(e.get("title")),
                        summary=clean(e.get("summary", "")), url=e.get("link"), source=name, kind="news"))
    return out


def collect(cfg, used_ids, max_research=10, max_news=5):
    days, mail = cfg["lookback_days"], cfg.get("contact_email", "example@example.com")
    items, seen_j, jobs = [], set(), []
    for j in cfg["journals"]:
        if j["issn"] not in seen_j:
            seen_j.add(j["issn"]); jobs.append(lambda j=j: from_crossref(j["issn"], j["name"], days, mail))
    for q in cfg.get("eric_queries", []):
        jobs.append(lambda q=q: from_eric(q, days))
    for s in cfg.get("rss", []):
        jobs.append(lambda s=s: from_rss(s["name"], s["url"]))
    for job in jobs:
        try:
            items += job()
        except Exception as ex:  # مصدر معطّل لا يوقف العملية
            print("source failed:", repr(ex)[:150])
    uniq, ids = [], set(used_ids)
    for it in items:
        if not it["id"] or it["id"] in ids or len(it["summary"]) < 200 or len(it["title"]) < 15:
            continue
        ids.add(it["id"]); uniq.append(it)
    random.shuffle(uniq)
    research = [i for i in uniq if i["kind"] == "research"][:max_research]
    news = [i for i in uniq if i["kind"] == "news"][:max_news]
    pool = research + news
    for i, it in enumerate(pool):
        it["idx"] = i
        it["summary"] = it["summary"][:1100]
    return pool
