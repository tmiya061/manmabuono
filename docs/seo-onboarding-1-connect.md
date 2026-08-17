# STEP1｜Claude Code と Shopify を繋ぐ（垣谷さん向け）

**この1枚をそのまま Claude Code に読ませてください。**

> 例：「このファイルの手順どおりに、Shopify Admin API との接続をセットアップして。
> 疎通確認（読み取りのみ）まで通ったら止めて。書き込み系は実行しないで。」

**このSTEPのゴール＝疎通確認が通ること。記事はまだ1本も書きません。**
記事の書き方・注意事項は、接続が終わったら STEP2 をお渡しします。

担当：宮川（環境構築・テーマ側の実装）／詰まったらこちらへ。

---

## 前提（30秒で読めます）

- 書くのは `/blogs/column` のコラム記事です。記事は**管理画面側のデータ**で、サイトの見た目（テーマ）とは**別レイヤー**です
- 🔴 **テーマのリポジトリは clone しないでください。`shopify theme pull` も不要です。**
  テーマは Git で管理されていて、main への push が即・本番反映される構成になっています。記事の投稿にテーマは一切関係ありません
- SEOのテンプレート実装（構造化データ・パンくず・noindex・目次の自動生成）は**すでに入っています**。自分で実装しないでください

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

### 🔴 シークレットの扱い（ここだけは今やってください）

シークレットは**無期限**です。渡した後に回収できないので、最初の時点で閉じておく必要があります。

- チャット欄に貼らない／コードに直書きしない／Git に入れない
- Claude Code に「`.env` の中身を表示して」とはさせない。**読むのはスクリプトだけ**でよい
- Claude Code の `settings.json` で `.env` の読み取りを deny しておくと事故が減ります
- 漏れた場合は宮川に連絡（Dev Dashboard でローテーションします）

## 2. 認証コード（これがそのまま動きます）

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

## 3. 疎通確認（🔴 読み取りのみ。書き込みは試さない）

```python
load_env()
print(gql('{ shop { name myshopifyDomain } }'))
print(gql('{ currentAppInstallation { accessScopes { handle } } }'))
```

2つ目で以下の9個が出れば**接続完了**です。

```
read_content, write_content, read_files, write_files,
read_products, read_inventory, read_reports,
read_metaobjects, read_metaobject_definitions
```

**繋がった勢いで記事の作成・更新を試さないでください。**
記事にはバージョン履歴が無く、上書きすると戻せません。テスト投稿の前に守ってほしいルールが STEP2 にあります。

## 4. 完了したら

宮川に「疎通確認まで通りました」と連絡してください。**STEP2（記事を書くときのルール）**をお渡しします。

権限エラーやトークン発行のエラーが出た場合も、回避策を探さずに連絡してください。
権限は用途に合わせて絞ってあるので、**エラー＝設定ミスか、やろうとしていることが想定外**のどちらかです。
