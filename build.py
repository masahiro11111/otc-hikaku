#!/usr/bin/env python3
"""
build.py
medicines.json を読み込み、データを完全に内蔵した index.html を生成する。
"""
import json, argparse
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent
SRC_JSON = DATA_DIR / "medicines.json"
OUT_HTML = DATA_DIR.parent / "index.html"

def run(output=None):
    out = Path(output) if output else OUT_HTML
    with open(SRC_JSON, encoding="utf-8") as f:
        data = json.load(f)

    meds = data.get("medicines", [])
    updated = data.get("updated_at", "")
    try:
        dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        updated_str = dt.strftime("%Y年%m月%d日 更新")
    except Exception:
        updated_str = ""

    # データをJS文字列に変換（</script>をエスケープ）
    meds_js = json.dumps(meds, ensure_ascii=False).replace("</script>", "<\\/script>")
    print(f"[build] {len(meds)}件 → {out}")

    html = build(meds_js, updated_str, len(meds))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"[build] 完了 {out.stat().st_size:,} bytes")

def build(meds_js, updated_str, count):
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>くすり成分ガイド｜OTC医薬品データベース</title>
<style>
:root{{--navy:#0f1c35;--teal:#2fa18d;--tl:#e6f4f1;--amber:#fffbeb;--red:#b91c1c;--rb:#fef2f2;--sl:#f1f5f9;--bd:#e2e8f0;--bdm:#cbd5e1;--tx:#0f172a;--txm:#475569;--txl:#94a3b8;--wh:#fff;}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Hiragino Kaku Gothic ProN','Noto Sans JP',-apple-system,sans-serif;background:var(--sl);color:var(--tx);font-size:14px;line-height:1.65}}
/* HEADER */
.hdr-wrap{{background:var(--navy);border-bottom:3px solid var(--teal)}}
.hdr{{max-width:1200px;margin:0 auto;padding:14px 24px;display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:8px}}
.logo{{font-size:20px;font-weight:700;color:#fff}}.logo em{{color:var(--teal);font-style:normal}}
.tagline{{font-size:11px;color:#64748b;margin-top:2px}}
.hbadge{{font-size:10px;padding:2px 10px;background:rgba(47,161,141,.15);border:1px solid rgba(47,161,141,.3);border-radius:20px;color:var(--teal)}}
.hright{{text-align:right}}.hnote{{font-size:11px;color:#64748b;margin-top:3px}}
/* LAYOUT */
.wrap{{max-width:1200px;margin:0 auto;padding:16px 24px 48px;display:grid;grid-template-columns:256px 1fr;gap:16px;align-items:start}}
/* SIDEBAR */
.sb{{position:sticky;top:12px;display:flex;flex-direction:column;gap:10px}}
.sc{{background:var(--wh);border:1px solid var(--bd);border-radius:10px;padding:12px 14px}}
.st{{font-size:10px;font-weight:700;color:var(--txl);letter-spacing:1.2px;text-transform:uppercase;margin-bottom:8px}}
/* Search */
.srch{{position:relative}}.srch-ico{{position:absolute;left:9px;top:50%;transform:translateY(-50%);font-size:13px;pointer-events:none}}
#q{{width:100%;padding:7px 7px 7px 28px;border:1px solid var(--bd);border-radius:7px;font-size:13px;color:var(--tx);outline:none}}
#q:focus{{border-color:var(--teal);box-shadow:0 0 0 3px rgba(47,161,141,.12)}}
/* Category */
.catlist{{display:flex;flex-direction:column;gap:1px}}
.cbtn{{display:flex;align-items:center;gap:7px;width:100%;padding:5px 7px;border-radius:6px;border:none;background:transparent;cursor:pointer;font-size:12.5px;color:var(--txm);text-align:left}}
.cbtn:hover{{background:var(--tl);color:#1a7f6e}}.cbtn.active{{background:var(--tl);color:#1a7f6e;font-weight:600}}
.cico{{font-size:13px;width:18px;text-align:center}}.cbadge{{margin-left:auto;font-size:10px;padding:1px 5px;background:var(--sl);border-radius:8px;color:var(--txl)}}
.cbtn.active .cbadge{{background:rgba(26,127,110,.12);color:#1a7f6e}}
/* Symptom */
.symp-g{{margin-bottom:7px}}
.symp-gh{{display:flex;align-items:center;gap:4px;font-size:11px;font-weight:600;color:var(--txm);margin-bottom:4px;padding:2px 0;border-bottom:1px solid var(--bd);cursor:pointer;user-select:none}}
.symp-gh .gar{{margin-left:auto;font-size:10px;color:var(--txl);transition:transform .15s}}
.symp-gh.col .gar{{transform:rotate(-90deg)}}
.symp-tags{{display:flex;flex-wrap:wrap;gap:3px}}.symp-tags.hidden{{display:none}}
.stag{{font-size:11px;padding:2px 8px;border-radius:20px;border:1px solid var(--bd);cursor:pointer;color:var(--txm);background:var(--wh);user-select:none;line-height:1.5}}
.stag:hover{{border-color:#f59e0b;color:#92400e;background:#fffbeb}}
.stag.active{{background:#f59e0b;border-color:#f59e0b;color:#fff;font-weight:600}}
.sa{{max-height:290px;overflow-y:auto}}
.sa::-webkit-scrollbar{{width:3px}}.sa::-webkit-scrollbar-thumb{{background:var(--bdm);border-radius:2px}}
/* Ing chips */
.ia{{max-height:180px;overflow-y:auto;display:flex;flex-wrap:wrap;gap:3px}}
.ia::-webkit-scrollbar{{width:3px}}.ia::-webkit-scrollbar-thumb{{background:var(--bdm);border-radius:2px}}
.ichip{{font-size:11px;padding:2px 7px;border-radius:20px;border:1px solid var(--bd);cursor:pointer;color:var(--txm);background:var(--wh)}}
.ichip:hover{{border-color:var(--teal);color:var(--teal)}}.ichip.active{{background:var(--teal);border-color:var(--teal);color:#fff}}
/* Filters */
.fsel{{width:100%;padding:5px 7px;border:1px solid var(--bd);border-radius:6px;font-size:12px;color:var(--tx);background:var(--wh);outline:none;margin-top:5px}}
.chk{{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--txm);cursor:pointer;padding:2px 0}}
.chk input{{accent-color:var(--teal)}}
.rbtn{{width:100%;padding:6px;border:1px dashed var(--bdm);border-radius:6px;background:transparent;font-size:12px;color:var(--txl);cursor:pointer;margin-top:8px}}
.rbtn:hover{{border-color:var(--red);color:var(--red);background:var(--rb)}}
.sfbox{{background:#fff7ed;border:1px solid #fed7aa;border-radius:7px;padding:9px 11px;font-size:11px;color:#7c2d12;line-height:1.7}}
.sfbox strong{{color:#c2410c;display:block;margin-bottom:2px}}
/* Main */
.main{{min-width:0}}
.resbar{{margin-bottom:10px}}
.resinfo{{font-size:13px;color:var(--txm)}}.resinfo strong{{color:var(--tx);font-size:15px}}
.afchips{{display:flex;flex-wrap:wrap;gap:4px;margin-top:5px}}
.afc{{display:inline-flex;align-items:center;gap:3px;font-size:11px;padding:2px 7px;background:var(--tl);color:#1a7f6e;border-radius:20px;border:1px solid rgba(26,127,110,.2)}}
.afc button{{background:none;border:none;cursor:pointer;font-size:13px;color:#1a7f6e;line-height:1;padding:0 2px}}
/* Cards */
.grid{{display:flex;flex-direction:column;gap:8px}}
.card{{background:var(--wh);border:1px solid var(--bd);border-radius:10px;padding:13px 16px;box-shadow:0 1px 3px rgba(15,23,42,.05)}}
.card:hover{{box-shadow:0 4px 12px rgba(15,23,42,.09);border-color:#c5d5e5}}
.chard{{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:5px}}
.cname{{font-size:15px;font-weight:700}}.cmaker{{font-size:11px;color:var(--txl);margin-top:1px}}
.cprice{{text-align:right;flex-shrink:0}}
.cpval{{font-size:18px;font-weight:700}}.cpval.nopr{{font-size:12px;color:var(--txl);font-weight:400}}
.cpnote{{font-size:10px;color:var(--txl)}}
.badges{{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:6px}}
.badge{{display:inline-block;font-size:10px;padding:2px 6px;border-radius:4px;font-weight:600;white-space:nowrap}}
.bc{{background:#1c2b4a;color:#cbd5e1}}
.r0,.r1{{background:#fee2e2;color:#991b1b;border:1px solid #fecaca}}
.r2{{background:#fff7ed;color:#92400e;border:1px solid #fed7aa}}
.r25{{background:#fef3c7;color:#78350f;border:1px solid #fde68a}}
.r3{{background:#f0fdf4;color:#166534;border:1px solid #bbf7d0}}
.bd{{background:#f5f3ff;color:#5b21b6;border:1px solid #ddd6fe}}
.bw{{background:#fef9c3;color:#713f12;border:1px solid #fde047}}
.csymp{{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:6px}}
.sym{{font-size:10px;padding:2px 6px;border-radius:12px;background:#fef3c7;color:#92400e;border:1px solid #fde68a}}
.sym.hit{{background:#f59e0b;color:#fff;border-color:#f59e0b;font-weight:600}}
.cef{{font-size:12.5px;color:var(--txm);margin-bottom:7px;line-height:1.6}}
.ings{{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:7px}}
.itag{{font-size:11px;padding:2px 7px;border-radius:4px}}
.in{{background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe}}
.im{{background:var(--tl);color:#1a7f6e;border:1px solid #99d4cd;font-weight:600}}
.iw{{background:#fee2e2;color:#991b1b;border:1px solid #fca5a5}}
.note{{font-size:11.5px;padding:6px 9px;border-radius:5px;margin-bottom:7px;line-height:1.65}}
.nn{{background:var(--sl);color:var(--txm);border-left:3px solid var(--bdm)}}
.nw{{background:var(--amber);color:#713f12;border-left:3px solid #f59e0b}}
.nd{{background:var(--rb);color:#7f1d1d;border-left:3px solid var(--red)}}
.cfoot{{display:flex;justify-content:space-between;align-items:center;padding-top:7px;border-top:1px solid var(--bd);font-size:11px}}
.cfoot a{{color:#2563eb;text-decoration:none}}.cfoot a:hover{{text-decoration:underline}}
.cfoot-l{{color:var(--txl)}}
/* Pagination */
.pagi{{display:flex;justify-content:center;align-items:center;gap:4px;margin-top:16px;flex-wrap:wrap}}
.pgb{{min-width:32px;height:32px;padding:0 7px;border:1px solid var(--bd);border-radius:6px;background:var(--wh);cursor:pointer;font-size:13px;color:var(--txm)}}
.pgb:hover:not(:disabled){{border-color:var(--teal);color:var(--teal)}}
.pgb.active{{background:var(--teal);border-color:var(--teal);color:#fff;font-weight:600}}
.pgb:disabled{{opacity:.35;cursor:not-allowed}}
.pgi{{font-size:12px;color:var(--txl);padding:0 3px}}
.nores{{text-align:center;padding:50px 20px;color:var(--txl)}}
.nores .ico{{font-size:32px;margin-bottom:8px}}
/* Footer */
.ft{{max-width:1200px;margin:0 auto;padding:0 24px 24px}}
.fti{{background:var(--wh);border:1px solid var(--bd);border-radius:7px;padding:10px 14px;font-size:11px;color:var(--txl);line-height:1.9}}
@media(max-width:800px){{.wrap{{grid-template-columns:1fr}}.sb{{position:static}}}}
</style>
</head>
<body>
<header class="hdr-wrap">
  <div class="hdr">
    <div><div class="logo">くすり成分<em>ガイド</em></div><div class="tagline">広告なし · 成分で選ぶ OTC医薬品データベース</div></div>
    <div class="hright"><span class="hbadge">PMDA添付文書ベース {count}品目</span><div class="hnote">{updated_str}</div></div>
  </div>
</header>
<div class="wrap">
  <aside class="sb">
    <div class="sc"><div class="st">検索</div>
      <div class="srch"><span class="srch-ico">🔍</span><input type="text" id="q" placeholder="商品名・成分・症状・メーカー…" autocomplete="off"></div>
    </div>
    <div class="sc"><div class="st">カテゴリ</div><div class="catlist" id="catlist"></div></div>
    <div class="sc"><div class="st">症状で絞り込む</div><div class="sa" id="sa"></div></div>
    <div class="sc"><div class="st">成分で絞り込む</div><div class="ia" id="ia"></div></div>
    <div class="sc">
      <div class="st">絞り込み</div>
      <select class="fsel" id="frisk"><option value="">リスク区分：すべて</option><option value="0">要指導医薬品</option><option value="1">第1類</option><option value="2">第2類（指定含む）</option><option value="3">第3類</option></select>
      <select class="fsel" id="fsort" style="margin-top:6px"><option value="default">並び替え：デフォルト</option><option value="price_asc">価格：安い順</option><option value="price_desc">価格：高い順</option><option value="name">名前：五十音順</option><option value="risk">リスク区分順</option></select>
      <div style="margin-top:8px;display:flex;flex-direction:column;gap:4px">
        <label class="chk"><input type="checkbox" id="cnd"> 眠気なしのみ表示</label>
        <label class="chk"><input type="checkbox" id="cnw"> 要注意成分を含まない</label>
      </div>
      <button class="rbtn" id="rbtn">✕ すべてリセット</button>
    </div>
    <div class="sfbox"><strong>⚠ 赤タグ成分について</strong>
      <b>ア尿素</b>（アリルイソプロピルアセチル尿素）→ 2023年AU全面規制・2025年KR麻薬類指定<br>
      <b>コデイン系</b> → 12歳未満禁忌・依存リスク
    </div>
  </aside>
  <main class="main">
    <div class="resbar"><div class="resinfo" id="ri"></div><div class="afchips" id="af"></div></div>
    <div class="grid" id="grid"></div>
    <div class="pagi" id="pagi"></div>
  </main>
</div>
<div class="ft"><div class="fti">【ご注意】本サイトはPMDA添付文書等の公開情報を元にした一般情報提供です。服用前に必ず添付文書をお読みください。広告収入を得ていません。</div></div>

<script>
const SYMP_GROUPS=[
  {{g:"痛み・熱",i:"🔥",s:["頭痛","偏頭痛","歯痛","のど痛","月経痛","腰痛","関節痛","筋肉痛","神経痛","打撲・ねんざ","発熱"]}},
  {{g:"鼻・目・のど",i:"👃",s:["鼻水","くしゃみ","鼻づまり","目のかゆみ","充血","目の疲れ","乾き目","花粉症","のどの炎症","のど痛"]}},
  {{g:"咳・痰・声",i:"😮‍💨",s:["せき","たん","声がれ","口腔殺菌"]}},
  {{g:"胃腸・お腹",i:"🫃",s:["胃痛","胸やけ","胃もたれ","食べ過ぎ","飲み過ぎ","吐き気","下痢","便秘","腹部膨満","整腸"]}},
  {{g:"皮膚・かゆみ",i:"🧴",s:["湿疹・かぶれ","かゆみ","虫刺され","乾燥肌","にきび","口内炎","水虫","肌荒れ"]}},
  {{g:"疲労・神経",i:"💪",s:["肉体疲労","眼精疲労","手足のしびれ","冷え","めまい・立ちくらみ","動悸"]}},
  {{g:"美容",i:"✨",s:["シミ・そばかす","肝斑","肌荒れ","薄毛・脱毛"]}},
  {{g:"女性・メンタル",i:"🌙",s:["更年期障害","月経不順","不眠","乗物酔い"]}},
  {{g:"その他",i:"💊",s:["禁煙","痔","排卵確認","妊娠確認","消毒"]}},
];
const CATS=[
  {{id:"all",l:"すべて",i:"💊"}},{{id:"cold",l:"かぜ薬・解熱鎮痛",i:"🤒"}},
  {{id:"stomach",l:"消化器官用薬",i:"🫃"}},{{id:"allergy",l:"アレルギー用薬",i:"🌸"}},
  {{id:"cough",l:"鎮咳・去痰・含嗽薬",i:"😮‍💨"}},{{id:"nose",l:"鼻炎用薬",i:"👃"}},
  {{id:"ext_pain",l:"外皮用薬（鎮痛）",i:"🩹"}},{{id:"ext_skin",l:"外皮用薬（皮膚）",i:"🧴"}},
  {{id:"eye",l:"眼科用薬",i:"👁"}},{{id:"joint",l:"関節・筋肉（内服）",i:"🦴"}},
  {{id:"skin_oral",l:"皮膚科・シミ（内服）",i:"✨"}},{{id:"hair",l:"育毛・発毛薬",i:"💈"}},
  {{id:"women",l:"女性用薬",i:"🌙"}},{{id:"sleep",l:"催眠鎮静薬",i:"😴"}},
  {{id:"vitamin",l:"ビタミン・滋養強壮",i:"💪"}},{{id:"kampo",l:"漢方製剤",i:"🌿"}},
  {{id:"foot",l:"水虫・皮膚感染",i:"🦶"}},{{id:"oral",l:"歯科口腔用薬",i:"🦷"}},
  {{id:"anal",l:"痔疾用薬",i:"🔴"}},{{id:"circu",l:"循環器・血液用薬",i:"❤️"}},
  {{id:"smoking",l:"禁煙補助剤",i:"🚭"}},{{id:"motion",l:"乗物酔い",i:"🚢"}},
  {{id:"test",l:"一般用検査薬",i:"🔬"}},{{id:"disinfect",l:"消毒薬",i:"🧪"}},
];
const RLABEL={{0:"要指導",1:"第1類",2:"第2類（指定）",2.5:"第２類",3:"第3類"}};
const RCLS={{0:"r0",1:"r1",2:"r2",2.5:"r25",3:"r3"}};

const MEDS={meds_js};

const S={{cat:"all",q:"",ings:new Set(),syms:new Set(),risk:"",sort:"default",nd:false,nw:false,page:1,pp:20}};

// カテゴリ構築
const catEl=document.getElementById("catlist");
CATS.forEach(c=>{{
  const cnt=c.id==="all"?MEDS.length:MEDS.filter(m=>m.cat===c.id).length;
  if(cnt===0&&c.id!=="all")return;
  const b=document.createElement("button");
  b.className="cbtn"+(c.id==="all"?" active":"");
  b.dataset.cat=c.id;
  b.innerHTML=`<span class="cico">${{c.i}}</span>${{c.l}}<span class="cbadge">${{cnt}}</span>`;
  b.addEventListener("click",()=>{{
    document.querySelectorAll(".cbtn").forEach(x=>x.classList.remove("active"));
    b.classList.add("active");S.cat=c.id;S.page=1;render();
  }});
  catEl.appendChild(b);
}});

// 症状パネル
function buildSymp(){{
  const sa=document.getElementById("sa");sa.innerHTML="";
  SYMP_GROUPS.forEach(grp=>{{
    const d=document.createElement("div");d.className="symp-g";
    const h=document.createElement("div");h.className="symp-gh";
    h.innerHTML=`<span style="font-size:13px">${{grp.i}}</span>${{grp.g}}<span class="gar">▼</span>`;
    const t=document.createElement("div");t.className="symp-tags";
    grp.s.forEach(sym=>{{
      const cnt=MEDS.filter(m=>m.symptoms&&m.symptoms.includes(sym)).length;
      const sp=document.createElement("span");
      sp.className="stag"+(S.syms.has(sym)?" active":"");
      sp.innerHTML=`${{sym}} <span style="opacity:.6;font-size:9px">${{cnt}}</span>`;
      sp.addEventListener("click",()=>{{
        if(S.syms.has(sym))S.syms.delete(sym);else S.syms.add(sym);
        sp.classList.toggle("active");S.page=1;render();
      }});
      t.appendChild(sp);
    }});
    h.addEventListener("click",()=>{{h.classList.toggle("col");t.classList.toggle("hidden");}});
    d.appendChild(h);d.appendChild(t);sa.appendChild(d);
  }});
}}
buildSymp();

// 成分チップ
function buildIngs(){{
  const map={{}};
  MEDS.forEach(m=>(m.ings||[]).forEach(ing=>{{
    const k=ing.replace(/[\\(（][^)）]*[\\)）]/g,"").trim();
    if(k)map[k]=(map[k]||0)+1;
  }}));
  const sorted=Object.entries(map).sort((a,b)=>b[1]-a[1]).slice(0,60).map(e=>e[0]);
  const ia=document.getElementById("ia");ia.innerHTML="";
  sorted.forEach(ing=>{{
    const c=document.createElement("span");
    c.className="ichip"+(S.ings.has(ing)?" active":"");
    c.textContent=ing;
    c.addEventListener("click",()=>{{
      if(S.ings.has(ing)){{S.ings.delete(ing);c.classList.remove("active");}}
      else{{S.ings.add(ing);c.classList.add("active");}}
      S.page=1;render();
    }});
    ia.appendChild(c);
  }});
}}
buildIngs();

function filter(){{
  let r=[...MEDS];
  if(S.cat!=="all")r=r.filter(m=>m.cat===S.cat);
  if(S.q){{const q=S.q.toLowerCase();r=r.filter(m=>
    m.name.toLowerCase().includes(q)||
    (m.maker||"").toLowerCase().includes(q)||
    (m.effect||"").toLowerCase().includes(q)||
    (m.ings||[]).some(i=>i.toLowerCase().includes(q)));}}
  if(S.syms.size>0)r=r.filter(m=>m.symptoms&&[...S.syms].some(s=>m.symptoms.includes(s)));
  if(S.ings.size>0)r=r.filter(m=>[...S.ings].some(si=>(m.ings||[]).some(mi=>mi.replace(/[\\(（][^)）]*[\\)）]/g,"").trim().includes(si))));
  if(S.risk!==""){{const rv=parseFloat(S.risk);r=rv===2?r.filter(m=>m.risk>=2&&m.risk<3):r.filter(m=>m.risk===rv);}}
  if(S.nd)r=r.filter(m=>!m.drowsy);
  if(S.nw)r=r.filter(m=>!(m.warnIngs&&m.warnIngs.length));
  if(S.sort==="price_asc")r.sort((a,b)=>(a.price||999999)-(b.price||999999));
  else if(S.sort==="price_desc")r.sort((a,b)=>(b.price||0)-(a.price||0));
  else if(S.sort==="name")r.sort((a,b)=>a.name.localeCompare(b.name,"ja"));
  else if(S.sort==="risk")r.sort((a,b)=>(a.risk||9)-(b.risk||9));
  return r;
}}

function card(m){{
  const cat=CATS.find(c=>c.id===m.cat)||{{}};
  const wSet=new Set((m.warnIngs||[]).map(w=>w.replace(/[\\(（][^)）]*[\\)）]/g,"").trim()));
  const ingsH=(m.ings||[]).map(ing=>{{
    const base=ing.replace(/[\\(（][^)）]*[\\)）]/g,"").trim();
    const isM=[...S.ings].some(si=>base.includes(si));
    const isW=wSet.has(base)||(m.warnIngs||[]).some(w=>ing.includes(w.replace(/[\\(（][^)）]*[\\)）]/g,"").trim()));
    return `<span class="itag ${{isW?"iw":isM?"im":"in"}}">${{ing}}</span>`;
  }}).join("");
  const symH=(m.symptoms&&m.symptoms.length)?
    `<div class="csymp">${{m.symptoms.map(s=>`<span class="sym${{S.syms.has(s)?" hit":""}}">
${{s}}</span>`).join("")}}</div>`:"";
  const nc=m.noteType==="danger"?"nd":m.noteType==="warn"?"nw":"nn";
  const pr=m.price?`<div class="cpval">¥${{m.price.toLocaleString()}}</div><div class="cpnote">参考価格（税込）</div>`
                  :`<div class="cpval nopr">価格要確認</div>`;
  return `<div class="card">
    <div class="chard"><div><div class="cname">${{m.name}}</div><div class="cmaker">${{m.maker||""}}</div></div>
    <div class="cprice">${{pr}}</div></div>
    <div class="badges">
      <span class="badge bc">${{cat.i||""}} ${{cat.l||m.cat||""}}</span>
      <span class="badge ${{RCLS[m.risk]||"r25"}}">${{RLABEL[m.risk]||""}}</span>
      ${{m.drowsy?'<span class="badge bd">🌙 眠気注意</span>':""}}
      ${{(m.warnIngs&&m.warnIngs.length)?'<span class="badge bw">⚠ 要注意成分含有</span>':""}}
    </div>
    ${{symH}}
    <div class="cef">${{m.effect||""}}</div>
    <div class="ings">${{ingsH}}</div>
    ${{m.note?`<div class="note ${{nc}}">${{m.note}}</div>`:""}}
    <div class="cfoot">
      <span class="cfoot-l">成分数: ${{(m.ings||[]).length}}</span>
      <a href="https://www.pmda.go.jp/PmdaSearch/otcSearch" target="_blank" rel="noopener">📄 PMDA添付文書 ↗</a>
    </div>
  </div>`;
}}

function afChips(){{
  const el=document.getElementById("af");el.innerHTML="";
  const add=(label,fn)=>{{
    const s=document.createElement("span");s.className="afc";
    s.innerHTML=`${{label}} <button>×</button>`;
    s.querySelector("button").addEventListener("click",fn);el.appendChild(s);
  }};
  if(S.cat!=="all"){{const c=CATS.find(x=>x.id===S.cat);if(c)add(c.l,()=>{{S.cat="all";document.querySelectorAll(".cbtn").forEach(b=>b.classList.remove("active"));document.querySelector('[data-cat="all"]').classList.add("active");S.page=1;render();}});}}
  if(S.q)add(`"${{S.q}}"`,()=>{{S.q="";document.getElementById("q").value="";S.page=1;render();}});
  S.syms.forEach(s=>add(`🔥 ${{s}}`,()=>{{S.syms.delete(s);buildSymp();S.page=1;render();}}));
  S.ings.forEach(i=>add(i,()=>{{S.ings.delete(i);buildIngs();S.page=1;render();}}));
  if(S.risk)add(RLABEL[parseFloat(S.risk)],()=>{{S.risk="";document.getElementById("frisk").value="";S.page=1;render();}});
  if(S.nd)add("眠気なし",()=>{{S.nd=false;document.getElementById("cnd").checked=false;S.page=1;render();}});
  if(S.nw)add("要注意成分なし",()=>{{S.nw=false;document.getElementById("cnw").checked=false;S.page=1;render();}});
}}

function pagi(total){{
  const pages=Math.ceil(total/S.pp);
  const el=document.getElementById("pagi");el.innerHTML="";
  if(pages<=1)return;
  const mk=(lb,pg,dis,act)=>{{
    const b=document.createElement("button");b.className="pgb"+(act?" active":"");
    b.textContent=lb;if(dis)b.disabled=true;
    else b.addEventListener("click",()=>{{S.page=pg;render();scrollTo({{top:0,behavior:"smooth"}});}});
    return b;
  }};
  el.appendChild(mk("‹",S.page-1,S.page===1,false));
  let prev=0;
  for(let i=1;i<=pages;i++){{
    if(i===1||i===pages||(i>=S.page-2&&i<=S.page+2)){{
      if(prev&&i-prev>1){{const d=document.createElement("span");d.className="pgi";d.textContent="…";el.appendChild(d);}}
      el.appendChild(mk(i,i,false,i===S.page));prev=i;
    }}
  }}
  el.appendChild(mk("›",S.page+1,S.page===pages,false));
}}

function render(){{
  const filtered=filter();const total=filtered.length;
  const start=(S.page-1)*S.pp;const paged=filtered.slice(start,start+S.pp);
  document.getElementById("ri").innerHTML=`<strong>${{total.toLocaleString()}}件</strong>表示中（全${{MEDS.length}}件）`;
  afChips();
  const grid=document.getElementById("grid");
  grid.innerHTML=paged.length===0?
    `<div class="nores"><div class="ico">🔍</div><p>条件に合う医薬品が見つかりません</p></div>`:
    paged.map(card).join("");
  pagi(total);
}}

let t;
document.getElementById("q").addEventListener("input",e=>{{clearTimeout(t);t=setTimeout(()=>{{S.q=e.target.value.trim();S.page=1;render();}},180);}});
document.getElementById("frisk").addEventListener("change",e=>{{S.risk=e.target.value;S.page=1;render();}});
document.getElementById("fsort").addEventListener("change",e=>{{S.sort=e.target.value;S.page=1;render();}});
document.getElementById("cnd").addEventListener("change",e=>{{S.nd=e.target.checked;S.page=1;render();}});
document.getElementById("cnw").addEventListener("change",e=>{{S.nw=e.target.checked;S.page=1;render();}});
document.getElementById("rbtn").addEventListener("click",()=>{{
  S.cat="all";S.q="";S.ings.clear();S.syms.clear();S.risk="";S.sort="default";S.nd=false;S.nw=false;S.page=1;
  document.getElementById("q").value="";
  document.getElementById("frisk").value="";
  document.getElementById("fsort").value="default";
  document.getElementById("cnd").checked=false;
  document.getElementById("cnw").checked=false;
  document.querySelectorAll(".cbtn").forEach(b=>b.classList.remove("active"));
  document.querySelector('[data-cat="all"]').classList.add("active");
  buildIngs();buildSymp();render();
}});
render();
</script>
</body>
</html>"""

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", default=str(OUT_HTML))
    a = p.parse_args()
    run(output=a.output)
