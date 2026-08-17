# Admin API アプリの2本立て運用

マンマボーノのストア（`007a21-4.myshopify.com`）に対して Admin API を叩くカスタムアプリは **2本**ある。
用途と権限で分けてあり、**混ぜて使わない**。

| アプリ | 使う人 | write | 用途 |
|---|---|---|---|
| `claude-admin` | 宮川 | 商品・在庫・記事・ファイル・メタオブジェクト（定義含む） | 管理画面作業全般 |
| `claude-seo` | 垣谷さん（SEO・業務委託） | **記事とファイルのみ** | コラム記事の作成・更新 |

`claude-seo` は 2026-08-17 に作成（→ [admin-changelog.md](admin-changelog.md)）。

## なぜ分けたか

Shopify 側に「**何をどう書き換えたか**」の差分ログは残らない。Dev Dashboard の API リクエストログはエンドポイントと回数のレベルまでで、記事にバージョン履歴も無い。
つまり事後に追跡できないので、**事前に権限で閉じる**しかない。

- アプリを分ける → 少なくとも「どちらのアプリの操作か」は切り分けられる
- write を最小化 → 事故の上限が「記事と画像」に閉じる。商品も在庫もメタオブジェクト定義も、そもそも壊せない

### ただし「アクセスの遮断」にはなっていない（2026-08-17 の前提）

**垣谷さんは Dev Dashboard（組織 103630706）に招待済み**なので、`claude-admin` の設定ページも開ける＝そちらのシークレットも取得できる状態にある。
つまりこの2本立ては **「うっかり事故の防止」と「操作の切り分け」** であって、**アクセス権の遮断ではない**。委託でほぼメンバーという位置づけを踏まえた上での判断（オーナー決定）。

この前提が変わるとき（＝本当に遮断が必要になったとき）は、アプリのアンインストールだけでは足りない。**Dev Dashboard の組織メンバーから外す**ところまでやる必要がある。

## claude-seo のスコープ

```
read_content,write_content,read_files,write_files,read_products,read_inventory,read_reports,read_metaobjects,read_metaobject_definitions
```

**あえて外したもの（付けない）**

| 外したスコープ | 理由 |
|---|---|
| `write_themes` / `read_themes` | テーマは Git 管理（Shopify GitHub連携＝main push が即本番）。API から触られると Git と噛み合わなくなる。SEO のテーマ側実装（構造化データ・noindex・パンくず等）は**実装済み**なので、必要なら宮川が対応 → [blog-column-architecture.md](blog-column-architecture.md) 「7. SEO設計」 |
| `write_products` | 商品SEO（メタタイトル/ディスクリプション）の書き換えは売上直結。宮川経由にする |
| `write_metaobjects` / `write_metaobject_definitions` | 著者・カテゴリの追加は宮川。定義を壊すと全記事に波及する |
| `write_inventory` | SEO用途に在庫の書き込みは不要 |
| `read_orders` / `read_customers` | 個人情報。売上把握は `read_reports`（ShopifyQL）で足りる |

スコープを変えるときは Dev Dashboard → claude-seo → バージョン → 「バージョンを作成」でスコープを編集し、**リリースしてからストアに再インストール**（リリースしないと反映されない）。

## 認証（2026年以降の方式）

2026-01-01 から管理画面での「レガシーカスタムアプリ」新規作成が廃止され、静的な `shpat_` トークンは発行されない。
現行は **client credentials grant**：

```
POST https://{store}.myshopify.com/admin/oauth/access_token
  grant_type=client_credentials
  client_id=...
  client_secret=...
→ access_token（24時間で失効。毎回発行し直す）
```

実装の見本は `scripts/shopifyql.py` の `load_env()` / `get_token()` / `gql()`。
`claude-admin` も `claude-seo` も**まったく同じコードで動く**（`.env` の中身が違うだけ）。API バージョンは `2026-07`。

## 垣谷さんへの引き継ぎ（2段階で渡す）

**1枚にまとめない。**接続前に記事のタグ規則まで読ませても優先順位がぼやけるので、STEP を分けて順に渡す。

### STEP1 → [seo-onboarding-1-connect.md](seo-onboarding-1-connect.md)

いま渡すもの。**ゴールは疎通確認が通ることだけ**（記事は1本も書かせない）。

- クライアントID / シークレットは**本人に Dev Dashboard から取ってもらう**（STEP1 に `claude-seo` の設定ページURLを直接載せてある）。垣谷さんは組織に招待済みなので開ける。宮川が値をコピーして渡す運用にはしない＝**受け渡しの経路に平文が乗らない**
- 認証コード（`load_env` / `get_token` / `gql`）は STEP1 に直接載せてある。`scripts/shopifyql.py` と同じもの

STEP1 に**残した注意は3つだけ**。セットアップの瞬間にしか効かないもの：

1. シークレットの扱い（`.env` / `.gitignore` / チャットに貼らない）— 後から言っても手遅れ
2. 疎通確認は読み取りのみ。繋がった勢いで書き込みを試させない
3. テーマのリポジトリは clone しない（「Shopifyと連携」で `shopify theme pull` に行く動線を先に潰す）

### STEP2 → [seo-onboarding-2-rules.md](seo-onboarding-2-rules.md)

**「疎通確認まで通りました」の連絡を受けてから**渡す。権限の範囲、記事を出す流れ（下書き→確認→公開／更新前の退避／changelog）、記事の書き方ルール、テーマ側の実装済みリスト、やらないでほしいこと。

## 権限を止めたいとき

管理画面 > アプリ > `claude-seo` をアンインストールすれば、そのアプリのトークン発行は即座に無効になる。
`claude-admin` には影響しない（分けてある理由のひとつ）。

ただし**これだけでは遮断にならない**。垣谷さんは Dev Dashboard に招待済みで `claude-admin` の資格情報も見えるため、本当に止めるなら
① `claude-seo` をアンインストール → ② **Dev Dashboard の組織メンバーから外す** → ③ `claude-admin` のシークレットをローテーション（宮川側の `.env` も差し替え）まで必要。
