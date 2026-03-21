# OTC医薬品データベース API

## 構成

```
otc-hikaku/
├── app.py                  # Flask REST API
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── scraper/
│   ├── pmda_scraper.py     # PMDA Playwrightスクレイパー
│   ├── scraper.py          # 価格更新（Amazon/楽天）
│   ├── build.py            # 静的HTML生成（GitHub Pages用）
│   ├── medicines.json      # マスタデータ
│   └── requirements.txt
└── .github/workflows/
    └── update.yml          # 自動更新
```

## セットアップ

```bash
# 依存インストール
pip install -r requirements.txt
playwright install chromium

# .envコピー
cp .env.example .env

# DB初期化 + 起動
python app.py
```

## Docker で起動

```bash
docker compose up -d
```

## PMDA スクレイピング（初回）

```bash
# テスト（50件）
python scraper/pmda_scraper.py --limit 50

# 解熱鎮痛薬カテゴリのみ
python scraper/pmda_scraper.py --yakkou 110

# 全件（時間がかかります）
python scraper/pmda_scraper.py
```

## API エンドポイント

| Method | Path | 説明 |
|--------|------|------|
| GET | /api/medicines | 全件取得（フィルタ・ページネーション） |
| GET | /api/medicines?q=ロキソプロフェン | キーワード検索 |
| GET | /api/medicines?symptom=頭痛 | 症状絞り込み |
| GET | /api/medicines?ingredient=アセトアミノフェン | 成分絞り込み |
| GET | /api/medicines?cat=cold&risk=1 | カテゴリ＋リスク区分絞り込み |
| GET | /api/medicines?no_drowsy=1 | 眠気なしのみ |
| GET | /api/medicines?sort=price&order=asc | 価格昇順 |
| GET | /api/medicines/<id> | 1件取得 |
| POST | /api/medicines | 新規登録 |
| PUT | /api/medicines/<id> | 更新 |
| DELETE | /api/medicines/<id> | 削除 |
| GET | /api/ingredients | 成分一覧 |
| GET | /api/symptoms | 症状グループ |
| GET | /api/categories | カテゴリ一覧 |
| GET | /api/stats | 統計情報 |

## データについて

PMDAの添付文書情報は政府公開情報であり、著作権法第13条に基づき商用利用が可能です。
