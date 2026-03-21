"""
pmda_scraper.py — PMDA OTC添付文書スクレイパー（Playwright使用）
================================================================
PMDAは政府機関の公開情報であり、著作権法上の保護対象外（著作権法第13条）。
商用サービスでの利用が可能。

使い方:
  pip install playwright && playwright install chromium
  python pmda_scraper.py              # 全件スクレイピング
  python pmda_scraper.py --limit 100  # テスト用100件
  python pmda_scraper.py --cat cold   # カテゴリ指定
"""

import asyncio
import json
import re
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

try:
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("WARNING: playwright未インストール。pip install playwright && playwright install chromium")

DATA_DIR = Path(__file__).parent
OUTPUT_JSON = DATA_DIR / "medicines.json"
CACHE_DIR = DATA_DIR / "pmda_cache"
CACHE_DIR.mkdir(exist_ok=True)

PMDA_OTC_SEARCH = "https://www.pmda.go.jp/PmdaSearch/otcSearch"
DELAY = 1.5  # ページ間の待機秒数（サーバーへの負荷軽減）

# 薬効分類コード → カテゴリIDマッピング
YAKKOU_TO_CAT = {
    "110": "cold",      "114": "cold",      "115": "cold",
    "220": "cough",     "221": "cough",     "222": "cough",
    "230": "stomach",   "231": "stomach",   "232": "stomach",
    "233": "stomach",   "234": "stomach",   "235": "stomach",
    "240": "stomach",   "241": "stomach",   "250": "stomach",
    "260": "ext_pain",  "261": "ext_pain",  "264": "ext_pain",
    "265": "ext_pain",
    "269": "ext_skin",  "629": "ext_skin",
    "131": "eye",       "132": "eye",       "133": "eye",
    "135": "nose",      "136": "nose",      "441": "allergy",
    "449": "allergy",
    "310": "vitamin",   "320": "vitamin",   "330": "vitamin",
    "462": "women",     "112": "sleep",
    "510": "kampo",     "515": "kampo",
    "629": "foot",
    "226": "oral",      "255": "anal",
    "210": "circu",     "113": "motion",
    "870": "test",      "710": "disinfect",
}

WARN_KEYWORDS = {
    "アリルイソプロピルアセチル尿素": "danger",
    "ブロムワレリル尿素": "danger",
    "ジヒドロコデインリン酸塩": "danger",
    "コデインリン酸塩": "danger",
    "ジヒドロコデイン": "danger",
}


async def scrape_otc_list(page, yakkou_code="", limit=0):
    """PMDA OTC検索ページから品目リストを取得"""
    results = []
    page_num = 1

    while True:
        params = {
            "kansen": "0",
            "pageNum": str(page_num),
            "pageSize": "100",
        }
        if yakkou_code:
            params["yakkou"] = yakkou_code

        url = f"{PMDA_OTC_SEARCH}?{urlencode(params)}"
        print(f"  [リスト取得] {url}")

        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=15000)
        except PWTimeout:
            print(f"  タイムアウト: {url}")
            break

        # 検索結果テーブルから品目情報を取得
        rows = await page.query_selector_all("table.result-table tr, table tr.odd, table tr.even")
        if not rows:
            # テーブルが見つからない場合は別のセレクタを試す
            rows = await page.query_selector_all(".search-result tr")

        page_results = []
        for row in rows:
            cells = await row.query_selector_all("td")
            if len(cells) < 2:
                continue
            link_el = await cells[0].query_selector("a")
            if not link_el:
                continue
            name = (await link_el.text_content() or "").strip()
            href = await link_el.get_attribute("href") or ""
            if not name or not href:
                continue
            page_results.append({
                "name": name,
                "detail_url": href if href.startswith("http") else f"https://www.pmda.go.jp{href}"
            })

        if not page_results:
            break

        results.extend(page_results)
        print(f"    → {len(page_results)}件（累計{len(results)}件）")

        if limit and len(results) >= limit:
            results = results[:limit]
            break

        # 次のページがあるか確認
        next_btn = await page.query_selector("a:has-text('次へ'), .next-page a, [rel='next']")
        if not next_btn:
            break
        page_num += 1
        await asyncio.sleep(DELAY)

    return results


async def scrape_otc_detail(page, item):
    """個別品目の詳細ページから成分・効能等を取得"""
    cache_file = CACHE_DIR / f"{re.sub(r'[^a-zA-Z0-9]', '_', item['name'])[:50]}.json"

    # キャッシュ確認
    if cache_file.exists():
        with open(cache_file, encoding="utf-8") as f:
            cached = json.load(f)
        # 7日以内のキャッシュは再利用
        if "cached_at" in cached:
            age = (datetime.now() - datetime.fromisoformat(cached["cached_at"])).days
            if age < 7:
                return cached

    detail = {"name": item["name"], "pmda_url": item["detail_url"]}

    try:
        await page.goto(item["detail_url"], timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(0.5)

        # 成分・分量
        ings = []
        ing_sections = await page.query_selector_all(
            "th:has-text('成分'), th:has-text('有効成分'), dt:has-text('成分')"
        )
        for sec in ing_sections:
            # 次の兄弟要素（td/dd）からテキスト取得
            sibling = await sec.evaluate_handle("el => el.nextElementSibling")
            if sibling:
                text = (await sibling.text_content() or "").strip()
                # 改行・空白で分割
                for line in re.split(r"\n|　|、|，", text):
                    line = line.strip()
                    if line and len(line) > 1 and line not in ings:
                        ings.append(line)

        # 効能効果
        effect = ""
        effect_els = await page.query_selector_all(
            "th:has-text('効能'), th:has-text('効果'), dt:has-text('効能')"
        )
        for el in effect_els:
            sibling = await el.evaluate_handle("el => el.nextElementSibling")
            if sibling:
                text = (await sibling.text_content() or "").strip()
                if text:
                    effect = text[:500]
                    break

        # リスク区分
        risk = 2.5
        risk_els = await page.query_selector_all(
            "th:has-text('リスク'), th:has-text('区分'), dt:has-text('リスク')"
        )
        for el in risk_els:
            sibling = await el.evaluate_handle("el => el.nextElementSibling")
            if sibling:
                text = (await sibling.text_content() or "").strip()
                if "要指導" in text:
                    risk = 0
                elif "第１類" in text or "第1類" in text:
                    risk = 1
                elif "指定第２類" in text or "指定第2類" in text:
                    risk = 2
                elif "第２類" in text or "第2類" in text:
                    risk = 2.5
                elif "第３類" in text or "第3類" in text:
                    risk = 3
                break

        # メーカー
        maker = ""
        maker_els = await page.query_selector_all(
            "th:has-text('販売会社'), th:has-text('製造'), th:has-text('会社'), dt:has-text('会社')"
        )
        for el in maker_els:
            sibling = await el.evaluate_handle("el => el.nextElementSibling")
            if sibling:
                text = (await sibling.text_content() or "").strip()
                if text:
                    maker = text[:100]
                    break

        detail.update({
            "ings": ings[:20],
            "effect": effect,
            "risk": risk,
            "maker": maker,
        })

    except Exception as e:
        print(f"  [詳細取得失敗] {item['name']}: {e}")
        detail["error"] = str(e)

    # 後処理
    detail = enrich_detail(detail)

    # キャッシュ保存
    detail["cached_at"] = datetime.now().isoformat()
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(detail, f, ensure_ascii=False, indent=2)

    return detail


def enrich_detail(detail):
    """スクレイプ結果を medicines.json 形式に変換"""
    ings = detail.get("ings", [])
    effect = detail.get("effect", "")

    # 警告成分チェック
    warn_ings = []
    ing_text = " ".join(ings)
    for kw in WARN_KEYWORDS:
        if kw in ing_text:
            warn_ings.append(kw)

    # 眠気推定
    drowsy_kws = ["クロルフェニラミン", "ジフェンヒドラミン", "コデイン", "ジヒドロコデイン",
                  "プロメタジン", "ジフェニルピラリン"]
    drowsy = any(k in ing_text for k in drowsy_kws)

    # カテゴリ推定
    cat = estimate_cat(effect, ings, detail.get("name", ""))

    # 症状推定
    symptoms = estimate_symptoms(effect, cat)

    detail.update({
        "cat": cat,
        "symptoms": symptoms,
        "warnIngs": warn_ings,
        "drowsy": drowsy,
        "noteType": "danger" if warn_ings else ("warn" if drowsy else ""),
        "note": build_note(warn_ings, drowsy),
        "source": "pmda",
        "asin": "",
        "rakuten_url": "",
        "price": None,
    })
    return detail


def estimate_cat(effect, ings, name):
    text = f"{effect} {' '.join(ings)} {name}"
    checks = [
        ("cold",     ["解熱","鎮痛","かぜ","発熱","頭痛薬"]),
        ("stomach",  ["胃","腸","整腸","下痢","便秘","消化","胸やけ"]),
        ("allergy",  ["アレルギー","花粉","じんましん"]),
        ("cough",    ["せき","咳","たん","痰","咽喉","のど"]),
        ("nose",     ["鼻水","鼻づまり","鼻炎"]),
        ("eye",      ["点眼","眼","目薬","目の"]),
        ("ext_pain", ["湿布","貼付","肩こり","腰痛","筋肉痛","消炎鎮痛"]),
        ("ext_skin", ["湿疹","かぶれ","かゆみ","皮膚"]),
        ("foot",     ["水虫","白癬","抗真菌"]),
        ("hair",     ["育毛","発毛","脱毛","ミノキシジル"]),
        ("women",    ["更年期","月経","婦人"]),
        ("sleep",    ["不眠","睡眠","催眠"]),
        ("vitamin",  ["ビタミン","滋養","強壮"]),
        ("kampo",    ["漢方","エキス"]),
        ("smoking",  ["禁煙","ニコチン"]),
        ("motion",   ["乗物酔","乗り物"]),
        ("skin_oral",["シミ","そばかす","美白","肝斑"]),
        ("anal",     ["痔","肛門"]),
        ("disinfect",["消毒","殺菌","エタノール"]),
    ]
    for cat_id, keywords in checks:
        if any(k in text for k in keywords):
            return cat_id
    return "vitamin"


def estimate_symptoms(effect, cat):
    syms = []
    checks = [
        ("頭痛","頭痛"), ("発熱","発熱"), ("発熱","解熱"),
        ("月経痛","月経痛"), ("腰痛","腰痛"), ("関節痛","関節痛"),
        ("筋肉痛","筋肉痛"), ("神経痛","神経痛"), ("のど痛","のど"),
        ("鼻水","鼻水"), ("くしゃみ","くしゃみ"), ("鼻づまり","鼻づまり"),
        ("花粉症","花粉"), ("せき","せき"), ("たん","たん"),
        ("胃痛","胃痛"), ("胸やけ","胸やけ"), ("胃もたれ","胃もたれ"),
        ("下痢","下痢"), ("便秘","便秘"), ("整腸","整腸"),
        ("湿疹・かぶれ","湿疹"), ("かゆみ","かゆみ"),
        ("水虫","水虫"), ("不眠","不眠"),
        ("更年期障害","更年期"), ("シミ・そばかす","シミ"),
        ("薄毛・脱毛","育毛"),
    ]
    for sym, keyword in checks:
        if keyword in effect and sym not in syms:
            syms.append(sym)
    return syms[:8]


def build_note(warn_ings, drowsy):
    notes = []
    if warn_ings:
        for w in warn_ings:
            if "アリルイソプロピルアセチル尿素" in w:
                notes.append("⚠ア尿素含有：2023年AU全面規制・2025年KR麻薬類指定。依存リスクあり。")
            elif "コデイン" in w or "ジヒドロコデイン" in w:
                notes.append("⚠コデイン系含有：12歳未満禁忌・依存リスクあり。")
            elif "ブロムワレリル尿素" in w:
                notes.append("⚠ブ尿素含有：海外規制済・依存リスクあり。")
    if drowsy and not notes:
        notes.append("眠気が出ることあり。自動車運転注意。")
    return " ".join(notes)


async def run_scraper(limit=0, yakkou_code=""):
    if not PLAYWRIGHT_AVAILABLE:
        print("ERROR: playwright をインストールしてください")
        return []

    results = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (compatible; OTC-Hikaku-Bot/1.0; +https://github.com/masahiro11111/otc-hikaku)",
            locale="ja-JP"
        )
        page = await context.new_page()

        # リスト取得
        print(f"[PMDA] OTC品目リストを取得中（薬効コード:{yakkou_code or '全カテゴリ'}）...")
        items = await scrape_otc_list(page, yakkou_code, limit)
        print(f"[PMDA] {len(items)}件取得。詳細取得を開始...")

        # 詳細取得
        for i, item in enumerate(items):
            print(f"  [{i+1}/{len(items)}] {item['name']}")
            detail = await scrape_otc_detail(page, item)
            results.append(detail)
            await asyncio.sleep(DELAY)

            # 100件ごとに中間保存
            if (i+1) % 100 == 0:
                save_results(results)

        await browser.close()

    return results


def save_results(results):
    existing = []
    if OUTPUT_JSON.exists():
        with open(OUTPUT_JSON, encoding="utf-8") as f:
            data = json.load(f)
            existing = data.get("medicines", [])

    # 重複除去（名前ベース）
    existing_names = {m["name"] for m in existing}
    new_items = [r for r in results if r.get("name") and r["name"] not in existing_names]
    merged = existing + new_items

    output = {
        "medicines": merged,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(merged),
        "source": "pmda_scraper"
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"[保存] {OUTPUT_JSON} ({len(merged)}件)")


def main():
    parser = argparse.ArgumentParser(description="PMDA OTC添付文書スクレイパー")
    parser.add_argument("--limit", type=int, default=0, help="取得件数上限（0=全件）")
    parser.add_argument("--yakkou", default="", help="薬効分類コード（例: 110=解熱鎮痛）")
    parser.add_argument("--clear-cache", action="store_true", help="キャッシュをクリア")
    args = parser.parse_args()

    if args.clear_cache:
        for f in CACHE_DIR.glob("*.json"):
            f.unlink()
        print("[キャッシュクリア]")

    print("=" * 50)
    print(f"PMDA OTC Scraper 開始 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("対象: PMDAの公開情報（政府著作物・商用利用可）")
    print("=" * 50)

    results = asyncio.run(run_scraper(limit=args.limit, yakkou_code=args.yakkou))
    if results:
        save_results(results)
    print(f"\n完了: {len(results)}件取得")


if __name__ == "__main__":
    main()
