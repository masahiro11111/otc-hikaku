"""
app.py — OTC医薬品データベース Flask REST API
エンドポイント:
  GET  /api/medicines       全件（フィルタ・ページネーション）
  GET  /api/medicines/<id>  1件取得
  POST /api/medicines       新規登録
  PUT  /api/medicines/<id>  更新
  DELETE /api/medicines/<id> 削除
  GET  /api/ingredients     成分一覧
  GET  /api/symptoms        症状グループ
  GET  /api/categories      カテゴリ一覧
  GET  /api/stats           統計
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from sqlalchemy import or_, func
import os, json, re
from datetime import datetime, timezone
from pathlib import Path

app = Flask(__name__, static_folder="frontend/dist", static_url_path="")
CORS(app)

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///otc_medicines.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JSON_AS_ASCII"] = False
db = SQLAlchemy(app)

# ── Model ─────────────────────────────────────────

class Medicine(db.Model):
    __tablename__ = "medicines"
    id            = db.Column(db.Integer, primary_key=True)
    pmda_id       = db.Column(db.String(64), unique=True, nullable=True, index=True)
    csv_product_id= db.Column(db.String(64), nullable=True, index=True)
    name          = db.Column(db.String(200), nullable=False, index=True)
    maker         = db.Column(db.String(100), nullable=True)
    cat           = db.Column(db.String(50),  nullable=True, index=True)
    risk          = db.Column(db.Float, nullable=True)
    drowsy        = db.Column(db.Boolean, default=False)
    price         = db.Column(db.Integer, nullable=True)
    price_updated_at = db.Column(db.DateTime, nullable=True)
    asin          = db.Column(db.String(20), nullable=True)
    rakuten_url   = db.Column(db.Text, nullable=True)
    _ings         = db.Column("ings",     db.Text, default="[]")
    _warn_ings    = db.Column("warn_ings",db.Text, default="[]")
    _symptoms     = db.Column("symptoms", db.Text, default="[]")
    effect        = db.Column(db.Text, nullable=True)
    note          = db.Column(db.Text, nullable=True)
    note_type     = db.Column(db.String(20), nullable=True)
    source        = db.Column(db.String(20), default="pmda")
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                              onupdate=lambda: datetime.now(timezone.utc))

    @property
    def ings(self): return json.loads(self._ings or "[]")
    @ings.setter
    def ings(self, v): self._ings = json.dumps(v, ensure_ascii=False)

    @property
    def warn_ings(self): return json.loads(self._warn_ings or "[]")
    @warn_ings.setter
    def warn_ings(self, v): self._warn_ings = json.dumps(v, ensure_ascii=False)

    @property
    def symptoms(self): return json.loads(self._symptoms or "[]")
    @symptoms.setter
    def symptoms(self, v): self._symptoms = json.dumps(v, ensure_ascii=False)

    def to_dict(self):
        return {
            "id": self.id, "pmda_id": self.pmda_id,
            "csv_product_id": self.csv_product_id,
            "name": self.name, "maker": self.maker or "",
            "cat": self.cat or "", "risk": self.risk,
            "drowsy": self.drowsy, "price": self.price,
            "price_updated_at": self.price_updated_at.isoformat() if self.price_updated_at else None,
            "asin": self.asin or "", "rakuten_url": self.rakuten_url or "",
            "ings": self.ings, "warnIngs": self.warn_ings,
            "symptoms": self.symptoms, "effect": self.effect or "",
            "note": self.note or "", "noteType": self.note_type or "",
            "source": self.source or "pmda",
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

# ── API ───────────────────────────────────────────

def parse_int(v, d):
    try: return int(v)
    except: return d

SORT_MAP = {"name": Medicine.name, "price": Medicine.price,
            "risk": Medicine.risk, "updated_at": Medicine.updated_at}

@app.route("/api/medicines", methods=["GET"])
def list_medicines():
    q          = request.args.get("q","").strip()
    cat        = request.args.get("cat","").strip()
    risk_str   = request.args.get("risk","").strip()
    symptom    = request.args.get("symptom","").strip()
    ingredient = request.args.get("ingredient","").strip()
    no_drowsy  = request.args.get("no_drowsy") == "1"
    no_warn    = request.args.get("no_warn") == "1"
    sort_key   = request.args.get("sort","name")
    order      = request.args.get("order","asc")
    page       = max(1, parse_int(request.args.get("page"),1))
    per_page   = min(100, max(1, parse_int(request.args.get("per_page"),20)))

    qs = Medicine.query
    if q:
        like = f"%{q}%"
        qs = qs.filter(or_(Medicine.name.ilike(like), Medicine.maker.ilike(like),
                           Medicine.effect.ilike(like), Medicine._ings.ilike(like)))
    if cat: qs = qs.filter(Medicine.cat == cat)
    if risk_str:
        try:
            rv = float(risk_str)
            qs = qs.filter(Medicine.risk.between(2.0,2.9)) if rv==2 else qs.filter(Medicine.risk==rv)
        except: pass
    if symptom:
        for s in symptom.split(","):
            s = s.strip()
            if s: qs = qs.filter(Medicine._symptoms.ilike(f"%{s}%"))
    if ingredient: qs = qs.filter(Medicine._ings.ilike(f"%{ingredient}%"))
    if no_drowsy:  qs = qs.filter(Medicine.drowsy == False)
    if no_warn:    qs = qs.filter(or_(Medicine._warn_ings=="[]",
                                      Medicine._warn_ings.is_(None)))

    col = SORT_MAP.get(sort_key, Medicine.name)
    qs = qs.order_by(col.desc().nullslast() if order=="desc" else col.asc().nullslast())

    total = qs.count()
    items = qs.offset((page-1)*per_page).limit(per_page).all()
    return jsonify({"total":total,"page":page,"per_page":per_page,
                    "pages":(total+per_page-1)//per_page,
                    "items":[m.to_dict() for m in items]})

@app.route("/api/medicines/<int:mid>", methods=["GET"])
def get_medicine(mid):
    return jsonify(Medicine.query.get_or_404(mid).to_dict())

@app.route("/api/medicines", methods=["POST"])
def create_medicine():
    data = request.get_json(silent=True) or {}
    if not data.get("name"): return jsonify({"error":"name必須"}), 400
    m = Medicine(name=data["name"], maker=data.get("maker"),
                 cat=data.get("cat"), risk=data.get("risk"),
                 drowsy=bool(data.get("drowsy",False)), price=data.get("price"),
                 asin=data.get("asin"), rakuten_url=data.get("rakuten_url"),
                 effect=data.get("effect"), note=data.get("note"),
                 note_type=data.get("noteType"), source=data.get("source","manual"),
                 pmda_id=data.get("pmda_id"), csv_product_id=data.get("csv_product_id"))
    m.ings=data.get("ings",[]); m.warn_ings=data.get("warnIngs",[]); m.symptoms=data.get("symptoms",[])
    db.session.add(m); db.session.commit()
    return jsonify(m.to_dict()), 201

@app.route("/api/medicines/<int:mid>", methods=["PUT"])
def update_medicine(mid):
    m = Medicine.query.get_or_404(mid)
    data = request.get_json(silent=True) or {}
    for f in ["name","maker","cat","risk","drowsy","price","asin","rakuten_url","effect","note"]:
        if f in data: setattr(m, f, data[f])
    if "noteType" in data: m.note_type = data["noteType"]
    if "ings" in data: m.ings = data["ings"]
    if "warnIngs" in data: m.warn_ings = data["warnIngs"]
    if "symptoms" in data: m.symptoms = data["symptoms"]
    m.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(m.to_dict())

@app.route("/api/medicines/<int:mid>", methods=["DELETE"])
def delete_medicine(mid):
    m = Medicine.query.get_or_404(mid)
    db.session.delete(m); db.session.commit()
    return jsonify({"deleted": mid})

@app.route("/api/ingredients")
def list_ingredients():
    rows = db.session.query(Medicine._ings).all()
    counter = {}
    for (ings_json,) in rows:
        for ing in json.loads(ings_json or "[]"):
            key = re.sub(r"[\(（][^)）]*[\)）]","",ing).strip()
            if key: counter[key] = counter.get(key,0)+1
    return jsonify([{"name":k,"count":v} for k,v in sorted(counter.items(),key=lambda x:-x[1])])

@app.route("/api/symptoms")
def list_symptoms():
    return jsonify([
        {"group":"痛み・熱","icon":"🔥","symptoms":["頭痛","偏頭痛","歯痛","のど痛","月経痛","腰痛","関節痛","筋肉痛","神経痛","打撲・ねんざ","発熱"]},
        {"group":"鼻・目・のど","icon":"👃","symptoms":["鼻水","くしゃみ","鼻づまり","目のかゆみ","充血","目の疲れ","乾き目","花粉症","のどの炎症","のど痛"]},
        {"group":"咳・痰・声","icon":"😮‍💨","symptoms":["せき","たん","声がれ","口腔殺菌"]},
        {"group":"胃腸・お腹","icon":"🫃","symptoms":["胃痛","胸やけ","胃もたれ","食べ過ぎ","飲み過ぎ","吐き気","下痢","便秘","腹部膨満","整腸"]},
        {"group":"皮膚・かゆみ","icon":"🧴","symptoms":["湿疹・かぶれ","かゆみ","虫刺され","乾燥肌","にきび","口内炎","水虫"]},
        {"group":"疲労・神経","icon":"💪","symptoms":["肉体疲労","眼精疲労","手足のしびれ","冷え","めまい・立ちくらみ","動悸"]},
        {"group":"美容","icon":"✨","symptoms":["シミ・そばかす","肝斑","肌荒れ","薄毛・脱毛"]},
        {"group":"女性・メンタル","icon":"🌙","symptoms":["更年期障害","月経不順","不眠","乗物酔い"]},
        {"group":"その他","icon":"💊","symptoms":["禁煙","痔","排卵確認","妊娠確認","消毒"]},
    ])

@app.route("/api/categories")
def list_categories():
    rows = db.session.query(Medicine.cat, func.count(Medicine.id)).group_by(Medicine.cat).all()
    return jsonify([{"id":c,"count":n} for c,n in rows if c])

@app.route("/api/stats")
def stats():
    total = Medicine.query.count()
    with_price = Medicine.query.filter(Medicine.price.isnot(None)).count()
    updated = db.session.query(func.max(Medicine.updated_at)).scalar()
    return jsonify({"total":total,"with_price":with_price,
                    "last_updated":updated.isoformat() if updated else None})

# フロントエンド配信
@app.route("/", defaults={"path":""})
@app.route("/<path:path>")
def serve(path):
    dist = Path(app.static_folder)
    if path and (dist/path).exists():
        return send_from_directory(app.static_folder, path)
    idx = dist/"index.html"
    if idx.exists():
        return send_from_directory(app.static_folder, "index.html")
    return jsonify({"status":"OTC API running","endpoints":["/api/medicines","/api/ingredients","/api/symptoms"]}), 200

# ── インポートCLI ─────────────────────────────────

def import_from_json(json_path):
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    meds = data.get("medicines", data) if isinstance(data, dict) else data
    added = skipped = 0
    for item in meds:
        name = item.get("name","").strip()
        if not name: continue
        if Medicine.query.filter_by(name=name, maker=item.get("maker","")).first():
            skipped += 1; continue
        m = Medicine(name=name, maker=item.get("maker",""), cat=item.get("cat",""),
                     risk=item.get("risk"), drowsy=bool(item.get("drowsy",False)),
                     price=item.get("price"), asin=item.get("asin",""),
                     rakuten_url=item.get("rakuten_url",""), effect=item.get("effect",""),
                     note=item.get("note",""), note_type=item.get("noteType",""),
                     source=item.get("source","pmda"),
                     pmda_id=item.get("pmda_id") or item.get("kegg_id"),
                     csv_product_id=item.get("csv_product_id"))
        m.ings=item.get("ings",[]); m.warn_ings=item.get("warnIngs",[]); m.symptoms=item.get("symptoms",[])
        db.session.add(m); added += 1
    db.session.commit()
    print(f"インポート完了: {added}件追加, {skipped}件スキップ")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        json_path = Path(__file__).parent / "scraper" / "medicines.json"
        if json_path.exists() and Medicine.query.count() == 0:
            print(f"[初期インポート] {json_path}")
            import_from_json(str(json_path))
    app.run(debug=True, host="0.0.0.0", port=5000)
