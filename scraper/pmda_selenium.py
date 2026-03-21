#!/usr/bin/env python3
"""
pmda_selenium.py - PMDA OTC添付文書スクレイパー
PMDAは政府公開情報（著作権法第13条）→ 商用利用可
"""

import json, re, time, argparse, hashlib, sys
from pathlib import Path
from datetime import datetime, timezone

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service
        USE_WDM = True
    except ImportError:
        USE_WDM = False
except ImportError:
    print("ERROR: pip install selenium webdriver-manager")
    sys.exit(1)

DATA_DIR  = Path(__file__).parent
OUTPUT    = DATA_DIR / "medicines.json"
CACHE_DIR = DATA_DIR / "pmda_cache"
CACHE_DIR.mkdir(exist_ok=True)
LOG_PATH  = DATA_DIR / "scraper.log"

PMDA_BASE   = "https://www.pmda.go.jp/PmdaSearch/otcSearch"
PAGE_DELAY  = 2.5
DET_DELAY   = 2.0

# 薬効分類コード → カテゴリ
YAKKOU = {
    "1110":"cold","1114":"cold","1115":"cold",
    "1120":"sleep","1113":"motion",
    "2100":"circu","2200":"cough","2210":"cough",
    "2300":"stomach","2310":"stomach","2320":"stomach",
    "2330":"stomach","2340":"stomach","2360":"stomach",
    "2370":"stomach","2380":"stomach",
    "2540":"anal","2550":"anal","2590":"smoking",
    "2600":"ext_skin","2620":"ext_skin","2640":"ext_pain",
    "2650":"foot","2670":"hair",
    "2260":"oral","2270":"oral","2280":"oral",
    "3100":"vitamin","3110":"vitamin","3120":"vitamin",
    "3130":"vitamin","3140":"vitamin","3150":"vitamin",
    "3190":"vitamin","3200":"vitamin",
    "4410":"allergy","4490":"allergy","4620":"women",
    "5100":"kampo",
    "1310":"eye","1320":"eye","1330":"eye","1340":"eye",
    "1350":"nose","1360":"nose",
    "8700":"test",
}

WARN_CHECK   = ["アリルイソプロピルアセチル尿素","ブロムワレリル尿素",
                "ジヒドロコデインリン酸塩","コデインリン酸塩","ジヒドロコデイン"]
DROWSY_CHECK = ["クロルフェニラミン","ジフェンヒドラミン","プロメタジン",
                "ジフェニルピラリン","コデイン","ジヒドロコデイン"]

CAT_MAP = [
    ("cold",      ["解熱","鎮痛","かぜ","感冒","発熱"]),
    ("stomach",   ["胃","腸","整腸","下痢","便秘","消化","胸やけ","H2"]),
    ("allergy",   ["アレルギー","花粉","蕁麻疹"]),
    ("cough",     ["鎮咳","去痰","せき","咳","含嗽"]),
    ("nose",      ["鼻炎","鼻水","鼻づまり"]),
    ("eye",       ["点眼","眼科","目薬"]),
    ("ext_pain",  ["湿布","貼付","肩こり","腰痛","筋肉痛","消炎鎮痛"]),
    ("ext_skin",  ["皮膚","湿疹","かぶれ","殺菌","しもやけ"]),
    ("foot",      ["水虫","白癬","抗真菌"]),
    ("hair",      ["育毛","発毛","脱毛","ミノキシジル"]),
    ("women",     ["更年期","月経","婦人"]),
    ("sleep",     ["催眠","不眠","睡眠"]),
    ("vitamin",   ["ビタミン","滋養","強壮","保健"]),
    ("kampo",     ["漢方","生薬"]),
    ("smoking",   ["禁煙","ニコチン"]),
    ("motion",    ["乗物酔","乗り物"]),
    ("skin_oral", ["シミ","そばかす","美白","肝斑"]),
    ("anal",      ["痔","肛門"]),
    ("disinfect", ["消毒","殺菌消毒","エタノール"]),
    ("test",      ["検査薬","妊娠","排卵"]),
    ("circu",     ["強心","センソ","循環器"]),
    ("oral",      ["口腔","咽喉","口内炎","歯痛","歯槽"]),
]

SYM_MAP = [
    ("頭痛",["頭痛"]),("発熱",["発熱","解熱"]),("月経痛",["月経痛","生理痛"]),
    ("腰痛",["腰痛"]),("関節痛",["関節痛"]),("筋肉痛",["筋肉痛"]),
    ("神経痛",["神経痛"]),("のど痛",["咽喉痛","のどの痛み"]),
    ("鼻水",["鼻水"]),("くしゃみ",["くしゃみ"]),("鼻づまり",["鼻づまり"]),
    ("花粉症",["花粉症","アレルギー性鼻炎"]),
    ("目のかゆみ",["目のかゆみ","眼のかゆみ"]),("充血",["充血"]),
    ("目の疲れ",["眼精疲労","目の疲れ"]),("乾き目",["乾き目","ドライアイ"]),
    ("せき",["せき","咳"]),("たん",["たん","痰"]),
    ("胃痛",["胃痛"]),("胸やけ",["胸やけ"]),("胃もたれ",["胃もたれ"]),
    ("食べ過ぎ",["食べ過ぎ"]),("飲み過ぎ",["飲み過ぎ","二日酔"]),
    ("吐き気",["吐き気","悪心"]),("下痢",["下痢"]),("便秘",["便秘"]),
    ("整腸",["整腸"]),
    ("湿疹・かぶれ",["湿疹","かぶれ","皮膚炎"]),
    ("かゆみ",["かゆみ"]),("水虫",["水虫","白癬"]),("不眠",["不眠"]),
    ("更年期障害",["更年期"]),("月経不順",["月経不順"]),
    ("乗物酔い",["乗物酔い","乗り物酔"]),("肉体疲労",["肉体疲労","疲労"]),
    ("眼精疲労",["眼精疲労"]),("手足のしびれ",["しびれ"]),("冷え",["冷え"]),
    ("シミ・そばかす",["シミ","そばかす","肝斑"]),
    ("薄毛・脱毛",["脱毛","薄毛","育毛"]),
    ("禁煙",["禁煙"]),("痔",["痔"]),("消毒",["消毒","殺菌"]),
    ("肌荒れ",["肌荒れ"]),("にきび",["にきび"]),("口内炎",["口内炎"]),
]

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--lang=ja-JP")
    opts.add_argument("user-agent=Mozilla/5.0 (compatible; OTC-Hikaku/2.0)")
    if USE_WDM:
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=opts)
    return webdriver.Chrome(options=opts)

def cache_path(url):
    return CACHE_DIR / (hashlib.md5(url.encode()).hexdigest() + ".json")

def read_cache(url):
    p = cache_path(url)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        age = (datetime.now() - datetime.fromisoformat(data.get("_at","2000-01-01"))).days
        return data if age < 30 else None
    except Exception:
        return None

def write_cache(url, data):
    data["_at"] = datetime.now().isoformat()
    cache_path(url).write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8")

def get_list(driver, yakkou, page=1):
    """1ページ分のリスト取得"""
    url = f"{PMDA_BASE}?pageNum={page}&pageSize=100&yakkou={yakkou}&kansen=0"
    log(f"  GET: {url}")
    driver.get(url)
    time.sleep(PAGE_DELAY)

    # ページのHTMLを取得してリンクを探す
    # PMDAは動的レンダリングなのでJSで全aタグを取得
    raw = driver.execute_script("""
        var out = [];
        var anchors = document.querySelectorAll('a[href]');
        for (var i = 0; i < anchors.length; i++) {
            var a = anchors[i];
            var href = a.getAttribute('href') || '';
            var text = a.textContent.trim();
            // 詳細ページへのリンクを判定
            if (text.length > 1 && (
                href.indexOf('otcDetail') > -1 ||
                href.indexOf('Detail') > -1 ||
                href.indexOf('detail') > -1
            )) {
                out.push({name: text, href: href});
            }
        }
        return out;
    """) or []

    log(f"  → rawリンク数: {len(raw)}")

    # デバッグ：最初の5件を表示
    for r in raw[:5]:
        log(f"    sample: {r.get('name','')[:30]} | {r.get('href','')[:60]}")

    items = []
    seen = set()
    for r in raw:
        href = r.get("href","")
        name = r.get("name","").strip()
        if not name or len(name) < 2:
            continue
        if not href.startswith("http"):
            href = "https://www.pmda.go.jp" + href
        if href not in seen:
            seen.add(href)
            items.append({"name": name, "url": href})

    # 次ページ確認
    has_next = bool(driver.execute_script(
        "var links = document.querySelectorAll('a');"
        "for(var i=0;i<links.length;i++){"
        "  if(links[i].textContent.trim()==='次へ') return true;"
        "}"
        "return false;"
    ))

    log(f"  → ユニーク品目: {len(items)}件 / 次ページ: {has_next}")

    # リストが0件の場合はページ全体のテキストをデバッグ出力
    if len(items) == 0:
        body_text = driver.find_element(By.TAG_NAME, "body").text[:500]
        log(f"  ⚠ 0件取得。ページ内容: {body_text}")

    return items, has_next

def get_detail(driver, item, default_cat):
    """詳細ページから成分・効能等を取得"""
    url = item["url"]
    cached = read_cache(url)
    if cached:
        cached.pop("_at", None)
        return cached

    result = {"name": item["name"], "pmda_url": url}
    try:
        driver.get(url)
        time.sleep(DET_DELAY)
        body = driver.find_element(By.TAG_NAME, "body").text

        ings   = parse_ings(driver, body)
        effect = extract_between(body,
            ["効能又は効果","効能・効果","効能効果"],
            ["用法及び用量","用法・用量","【用法"])
        risk = 2.5
        if   "要指導"      in body: risk = 0
        elif "指定第２類"  in body or "指定第2類" in body: risk = 2
        elif "第１類"      in body or "第1類" in body:    risk = 1
        elif "第２類"      in body or "第2類" in body:    risk = 2.5
        elif "第３類"      in body or "第3類" in body:    risk = 3

        maker = extract_between(body,
            ["販売会社名","製造販売元","会社名"],
            ["\n\n","\n※","\n【"])

        result.update({
            "ings":   ings,
            "effect": effect[:400],
            "risk":   risk,
            "maker":  maker[:80],
        })
    except Exception as e:
        log(f"  詳細エラー [{item['name']}]: {e}")

    result = enrich(result, default_cat)
    write_cache(url, result)
    return result

def parse_ings(driver, body):
    ings = []
    # テーブルから成分行を探す
    try:
        for table in driver.find_elements(By.TAG_NAME, "table"):
            rows = table.find_elements(By.TAG_NAME, "tr")
            in_ing = False
            for row in rows:
                ths = [c.text.strip() for c in row.find_elements(By.TAG_NAME,"th")]
                tds = [c.text.strip() for c in row.find_elements(By.TAG_NAME,"td")]
                if any("成分" in t or "分量" in t for t in ths):
                    in_ing = True
                    continue
                if in_ing:
                    val = tds[0] if tds else ""
                    if not val:
                        break
                    if not any(s in val for s in ["添加物","合計","注","備考"]):
                        ings.append(val)
    except Exception:
        pass

    if not ings:
        sec = extract_between(body,
            ["成分及び分量","成分・分量","有効成分"],
            ["【用法","添加物","次の注意"])
        for line in re.split(r"[\n、，,/]", sec or ""):
            line = line.strip()
            if 2 <= len(line) <= 60 and not line[0].isdigit():
                name = re.split(r"\s+\d|\(|\（", line)[0].strip()
                if name and name not in ings:
                    ings.append(name)
    return ings[:20]

def extract_between(text, starts, ends):
    for s in starts:
        idx = text.find(s)
        if idx < 0:
            continue
        rest = text[idx+len(s):]
        end_pos = len(rest)
        for e in ends:
            p = rest.find(e)
            if 0 < p < end_pos:
                end_pos = p
        content = rest[:end_pos].strip()
        if content:
            return content
    return ""

def enrich(d, default_cat="vitamin"):
    ings    = d.get("ings", [])
    effect  = d.get("effect", "")
    ing_str = " ".join(ings)

    warn_ings = [w for w in WARN_CHECK if w in ing_str]
    drowsy    = any(k in ing_str for k in DROWSY_CHECK)

    text = f"{effect} {ing_str} {d.get('name','')}"
    cat  = default_cat
    for cid, kws in CAT_MAP:
        if any(k in text for k in kws):
            cat = cid
            break

    syms = []
    for sym, kws in SYM_MAP:
        if any(k in effect for k in kws):
            syms.append(sym)

    notes = []
    for w in warn_ings:
        if "アリルイソプロピルアセチル尿素" in w:
            notes.append("⚠ア尿素含有：2023年AU全面規制・2025年KR麻薬類指定。依存リスクあり。")
        elif "コデイン" in w or "ジヒドロコデイン" in w:
            notes.append("⚠コデイン系：12歳未満禁忌・依存リスク。眠気・運転不可。")
        elif "ブロムワレリル" in w:
            notes.append("⚠ブ尿素含有：海外規制済・依存リスク。")
    if drowsy and not notes:
        notes.append("眠気が出ることあり。自動車運転注意。")

    d.update({
        "cat":      cat,
        "symptoms": syms[:8],
        "warnIngs": warn_ings,
        "drowsy":   drowsy,
        "noteType": "danger" if warn_ings else ("warn" if drowsy else ""),
        "note":     " ".join(notes),
        "source":   "pmda",
        "asin":     d.get("asin", ""),
        "rakuten_url": d.get("rakuten_url", ""),
        "price":    d.get("price"),
    })
    if "id" not in d:
        d["id"] = int(hashlib.md5(d["name"].encode()).hexdigest()[:8], 16) % 1000000
    return d

def load_existing():
    if not OUTPUT.exists():
        return []
    try:
        return json.loads(OUTPUT.read_text(encoding="utf-8")).get("medicines", [])
    except Exception:
        return []

def save(meds):
    data = {
        "medicines":  meds,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total":      len(meds),
        "source":     "pmda_selenium",
    }
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"保存: {len(meds)}件 → {OUTPUT}")

def _merge(existing, new_items):
    seen, out = set(), []
    for m in (existing + new_items):
        n = m.get("name","")
        if n and n not in seen:
            seen.add(n)
            out.append(m)
    return out

def run(limit=0, resume=False):
    log(f"PMDA OTC スクレイパー開始 limit={limit} resume={resume}")
    existing      = load_existing()
    existing_names = {m["name"] for m in existing}
    log(f"既存: {len(existing)}件")

    driver    = make_driver()
    new_items = []
    found     = 0

    try:
        for yakkou, default_cat in YAKKOU.items():
            log(f"\n薬効分類 {yakkou} ({default_cat})")
            page = 1
            while True:
                items, has_next = get_list(driver, yakkou, page)

                for item in items:
                    found += 1
                    if limit and found > limit:
                        break
                    if resume and item["name"] in existing_names:
                        continue
                    log(f"  [{found}] {item['name']}")
                    det = get_detail(driver, item, default_cat)
                    new_items.append(det)

                    # 50件ごとに中間保存
                    if len(new_items) % 50 == 0:
                        merged = _merge(existing, new_items)
                        save(merged)

                if limit and found >= limit:
                    break
                if not has_next:
                    break
                page += 1
                time.sleep(PAGE_DELAY)

            if limit and found >= limit:
                log(f"limit={limit} に達したため終了")
                break

    except KeyboardInterrupt:
        log("中断されました")
    finally:
        driver.quit()

    merged = _merge(existing if resume else [], new_items)
    save(merged)
    log(f"\n完了: 新規 {len(new_items)}件 / 合計 {len(merged)}件")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit",  type=int, default=0)
    p.add_argument("--resume", action="store_true")
    a = p.parse_args()
    run(limit=a.limit, resume=a.resume)
