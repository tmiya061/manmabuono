# マンマボーノ コラム記事｜Claude Code × Shopify Admin API 引き継ぎ

SEO担当の方向け。**この1枚をそのまま Claude Code に読ませてもらって構いません。**
記事（`/blogs/column`）の作成・更新を API 経由で行うための手順とルールをまとめています。

担当：宮川（環境構築・テーマ側の実装）／不明点はこちらへ。

---

## 0. 前提として知っておいてほしいこと

- **サイトの見た目（テーマ）は Git で管理されていて、main への push が即・本番反映**されます。
  記事の投稿はテーマとは**別レイヤー**なので、リポジトリを clone する必要はありません。**テーマは触らないでください。**
- SEOのテンプレート実装（記事の構造化データ Article + BreadcrumbList、パンくず、カテゴリページの title/description、タグ絞り込みページの `noindex, follow`、目次の自動生成）は**すでに入っています**。
  ここを変えたい場合は自分で実装せず、宮川に言ってください。
- **記事にバージョン履歴はありません。**上書きしたら戻せません（後述の退避ルール）。

## 1. アプリと認証

`claude-seo` という専用アプリを、マンマボーノのストアにインストール済みです。
クライアントID / シークレットは別途安全な経路でお渡しします。

> 2026年1月から Shopify の「管理画面で作るカスタムアプリ」が廃止され、`shpat_` で始まる静的トークンは発行されません。
> 現行は **client credentials grant** で、24時間有効のトークンを毎回発行する方式です。

### `.env` を作る

作業ディレクトリの直下に `.env` を作り、**`.gitignore` に `.env` を必ず追加**してください。

```
SHOPIFY_STORE_DOMAIN=007a21-4.myshopify.com
SHOPIFY_CLIENT_ID=（お渡ししたもの）
SHOPIFY_CLIENT_SECRET=（お渡ししたもの）
```

**シークレットの扱い**

- チャット欄に貼らない／コードに直書きしない／Git に入れない
- Claude Code に「`.env` の中身を表示して」とはさせない。**読むのはスクリプトだけ**でよい
- 漏れた場合は宮川に連絡（Dev Dashboard でローテーションします）
- Claude Code の `settings.json` で `.env` の読み取りを deny しておくと事故が減ります

### 認証コード（これがそのまま動きます）

```python
#!/usr/bin/env python3
import json, os, sys, urllib.parse, urllib.request

API_VERSION = "2026-07"
_TOKEN = None

def load_env(path=".env"):
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)

def get_token():
    domain = os.environ["SHOPIFY_STORE_DOMAIN"]
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": os.environ["SHOPIFY_CLIENT_ID"],
        "client_secret": os.environ["SHOPIFY_CLIENT_SECRET"],
    }).encode()
    req = urllib.request.Request(
        f"https://{domain}/admin/oauth/access_token", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)["access_token"]   # 24時間で失効

def gql(query, variables=None):
    global _TOKEN
    if _TOKEN is None:
        _TOKEN = get_token()
    domain = os.environ["SHOPIFY_STORE_DOMAIN"]
    req = urllib.request.Request(
        f"https://{domain}/admin/api/{API_VERSION}/graphql.json",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Content-Type": "application/json", "X-Shopify-Access-Token": _TOKEN})
    with urllib.request.urlopen(req) as r:
        out = json.load(r)
    if "errors" in out:
        print("GraphQL error:", json.dumps(out["errors"], ensure_ascii=False, indent=2))
        sys.exit(1)
    return out["data"]
```

REST ではなく **GraphQL Admin API（`2026-07`）** を使ってください。Shopify は GraphQL に一本化する方向です。

### 疎通確認（読み取りのみ・書き込みなし）

まずこれだけ通してください。

```python
load_env()
print(gql('{ shop { name myshopifyDomain } }'))
print(gql('{ currentAppInstallation { accessScopes { handle } } }'))
```

2つ目で以下の9個が出れば正常です。

```
read_content, write_content, read_files, write_files,
read_products, read_inventory, read_reports,
read_metaobjects, read_metaobject_definitions
```

## 2. 権限の範囲

**書き込めるのは記事とファイル（画像）だけ**です。それ以外は読み取り専用にしてあります。

| できる | できない（意図的に外しています） |
|---|---|
| 記事の作成・更新・記事のメタフィールド設定 | テーマの閲覧・編集 |
| 画像のアップロード | 商品の編集（商品SEOの書き換え含む） |
| 商品・在庫・コレクションの**閲覧** | メタオブジェクト（著者・カテゴリ）の追加・定義変更 |
| 売上レポート（ShopifyQL）の**閲覧** | 注文・顧客データの閲覧 |
| 著者・カテゴリのメタオブジェクトの**閲覧** | |

権限エラーが出たら「回避策を探す」のではなく、**宮川に連絡してください**。外してあるものは理由があって外しています。

## 3. 記事を1本出すまでの流れ

1. **下書きで作る**（`published: false` 相当）。いきなり公開しない
2. 管理画面 or プレビューで確認
3. 公開
4. 記事下のおすすめ商品（CTA）が必要なら宮川に依頼 → `scripts/set_article_cta.py` で反映します

### 既存記事を更新するときは、先に退避する（必須）

記事にバージョン履歴はありません。**更新前に現在の内容を JSON で保存**してください。

```python
before = gql('query($id: ID!) { article(id: $id) { id title handle body summary tags } }',
             {"id": "gid://shopify/Article/..."})
open("backup/article_xxx.json", "w").write(json.dumps(before, ensure_ascii=False, indent=2))
```

### 書き込んだら1行残す

Shopify 側には「何をどう書き換えたか」の差分ログが残りません（管理画面にもAPIログにも）。
**書き込み系の操作をしたら、宮川に共有するか、渡されたリポジトリの `docs/admin-changelog.md` に1行追記**してください。

書式：`- 日付 | 対象 | 何を | 手段 | 復元手段`

## 4. 記事の書き方ルール（テーマ側の実装と噛み合っています）

これを外すと、カテゴリページに出ない・目次が出ない・meta description が空になる等の不具合になります。

- **ブログは `column`（`/blogs/column`）／テンプレートは `column` を選ぶ**
- **カテゴリタグを必ず1つだけ**付ける。2つ以上付けると最初に一致したものがカテゴリ扱いになります
  `choose` / `trouble` / `feeding` / `health` / `storage` / `basics` / `homemade`
- **自由タグ**は複数OK：`cat` `dog` `kitten` `puppy` `senior` `dry` `wet`
- **タグは必ず半角英字。**日本語タグは URL が文字化けします
- **抜粋（excerpt）は必ず書く**（80字前後）。一覧カードと **meta description** に使われます
- **アイキャッチ**：16:9 推奨・横1200px以上
- **見出しは H2 → H3 の順**（目次が H2/H3 から自動生成されます）
- **著者・監修者**：記事メタフィールド `custom.author` / `custom.supervisor` にメタオブジェクト `article_author` を紐付け。未設定だと「マンマボーノ編集部」表示になります
- 記事内で使える HTML パーツ（ポイントボックス／注意ボックス／メモボックス／吹き出し／CTAボタン）が用意されています → `docs/blog-column-setup.md`

新しいカテゴリや新しい著者を追加したい場合は**自分で作らず宮川へ**（メタオブジェクトは書き込み権限を外してあります。定義を壊すと全記事に波及するため）。

## 5. やらないでほしいこと（まとめ）

- テーマ（`.liquid` / CSS / 構造化データ）を触る
- いきなり公開する
- 既存記事を退避せずに上書きする
- 商品ページの SEO を書き換える（依頼は宮川へ。売上に直結するため）
- シークレットをチャット・メール本文・Git に平文で置く
