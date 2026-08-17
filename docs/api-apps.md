# Admin API アプリの2本立て運用

マンマボーノのストア（`007a21-4.myshopify.com`）に対して Admin API を叩くカスタムアプリは **2本**ある。
用途と権限で分けてあり、**混ぜて使わない**。

| アプリ | 使う人 | write | 用途 |
|---|---|---|---|
| `claude-admin` | 宮川 | 商品・在庫・記事・ファイル・メタオブジェクト（定義含む） | 管理画面作業全般 |
| `claude-seo` | SEO担当（外部） | **記事とファイルのみ** | コラム記事の作成・更新 |

`claude-seo` は 2026-08-17 に作成（→ [admin-changelog.md](admin-changelog.md)）。

## なぜ分けたか

Shopify 側に「**何をどう書き換えたか**」の差分ログは残らない。Dev Dashboard の API リクエストログはエンドポイントと回数のレベルまでで、記事にバージョン履歴も無い。
つまり事後に追跡できないので、**事前に権限で閉じる**しかない。

- アプリを分ける → 少なくとも「どちらのアプリの操作か」は切り分けられる
- write を最小化 → 事故の上限が「記事と画像」に閉じる。商品も在庫もメタオブジェクト定義も、そもそも壊せない

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

## SEO担当への引き継ぎ

渡すもの：

1. `claude-seo` の **クライアントID / シークレット**（Dev Dashboard → claude-seo → 設定）
   - **チャット・メール本文に平文で貼らない。** シークレットは無期限なので、漏れたら Dev Dashboard で「ローテーション」
2. `scripts/shopifyql.py` の認証まわり30行（`load_env` / `get_token` / `gql`）
3. `.env` は各自で作る（git 管理外）
   ```
   SHOPIFY_STORE_DOMAIN=007a21-4.myshopify.com
   SHOPIFY_CLIENT_ID=...
   SHOPIFY_CLIENT_SECRET=...
   ```
4. [blog-column-setup.md](blog-column-setup.md) の「記事の書き方ルール」

伝えておくこと：

- **記事は下書きで作る → 管理画面で確認 → 公開。** いきなり公開しない
- **既存記事を更新する前に、現在の本文を JSON で退避する。** 記事にバージョン履歴は無く、上書きしたら戻せない
- 書き込み系をやったら [admin-changelog.md](admin-changelog.md) に1行残す
- テーマ（サイトの見た目・SEOのテンプレ実装）は触らない。必要なら宮川に言う
- 記事の **抜粋（excerpt）は必ず書く**（meta description に使われる）

## 権限を止めたいとき

管理画面 > アプリ > `claude-seo` をアンインストールすれば、そのアプリのトークン発行は即座に無効になる。
`claude-admin` には影響しない（分けてある理由のひとつ）。
