# コラム（ブログ）システム設計ドキュメント

マンマボーノのコラム（`/blogs/column`）の全体設計。2026-07時点。
セットアップ手順は [blog-column-setup.md](blog-column-setup.md)、商品情報は [products.md](products.md) を参照。

---

## 1. 全体像

```
/blogs/column                     一覧ページ（blog.column.json → c_blogList）
/blogs/column/tagged/<category>   カテゴリページ（同上・見出しと説明文が切替）
/blogs/column/<記事handle>        記事詳細（article.column.json → c_article）

お知らせ(/blogs/news)は従来のまま。コラム専用テンプレートとは独立。
```

- **カテゴリ** = Shopifyの記事タグ ＋ メタオブジェクト `article_category` の組み合わせで実現
- **著者・監修者** = メタオブジェクト `article_author` を記事メタフィールドから参照
- **記事下の商品CTA** = メタオブジェクト `product_recommendation` を記事ごとに生成して参照（API運用）

## 2. テーマファイル構成

| 種別 | ファイル | 役割 |
|---|---|---|
| テンプレート | `templates/article.column.json` | 記事詳細（main = c_article） |
| テンプレート | `templates/blog.column.json` | 一覧（fv = c_underFv、main = c_blogList） |
| セクション | `sections/c_article.liquid` | 記事詳細本体（下記§5参照） |
| セクション | `sections/c_blogList.liquid` | 一覧・カテゴリページ兼用 |
| スニペット | `snippets/c_prod-card.liquid` | CTA用商品カード（縦型） |
| スニペット | `snippets/c_article-author-card.liquid` | 著者・監修者カード |
| スニペット | `snippets/c_tag-label.liquid` | 自由タグ→日本語表示名の変換 |
| スニペット | `snippets/c_bredcrumb.liquid` | パンくず（column分岐でカテゴリ階層を挿入） |
| CSS | `assets/c_article.scss` → `.min.css` | 記事詳細＋本文装飾＋記事内HTMLパーツ |
| CSS | `assets/c_blogList.scss` → `.min.css` | 一覧・カード・カテゴリチップ |
| レイアウト | `layout/theme.liquid` | コラム用の title/description/noindex 分岐（§7） |

JSは `c_article.liquid` 内にインライン（目次生成・スクロール追従・プログレスバー・リンクコピー）。

## 3. データモデル

### メタオブジェクト（3種・すべてストアフロントアクセスON）

| タイプ | フィールド | 用途 |
|---|---|---|
| `article_author` | name / role_title / photo / qualification / bio | 著者・監修者。エントリー例: `editorial-team`（マンマボーノ編集部）、西川さん（3資格持ち） |
| `article_category` | name / description | カテゴリ。**エントリーのハンドル＝カテゴリスラッグ＝記事に付けるタグ** |
| `product_recommendation` | product（商品参照）/ copy（1行・任意） | 記事下CTA。**記事ごとにAPIで自動生成**（手動登録しない） |

### 記事メタフィールド（namespace: custom）

| キー | タイプ | 用途 |
|---|---|---|
| `author` | article_author参照 | 執筆者（未設定時はセクション設定のデフォルト名「マンマボーノ編集部」…基本は西川さんを設定） |
| `supervisor` | article_author参照 | 監修者（任意。設定時のみ表示＋JSON-LDのreviewedBy） |
| `recommendations` | product_recommendation参照リスト | 記事下CTA商品（**最優先**。set_article_cta.pyが書き込む） |
| `related_products` | 商品参照リスト | CTAの簡易版（recommendations未設定時のフォールバック） |
| `related_collection` | コレクション参照 | 商品未設定時のフォールバック（コレクションカード表示） |

### タグ設計（2系統）

| 系統 | 値 | ルール |
|---|---|---|
| カテゴリ | `choose` `trouble` `feeding` `health` `storage` `basics` `homemade` | **1記事に必ず1つだけ**。article_categoryのハンドルと一致するタグ＝カテゴリと判定 |
| 自由タグ | `cat` `dog` `kitten` `puppy` `senior` `dry` `wet` | 複数可。日本語名は c_tag-label.liquid のcase文で管理（追加時はここに追記） |

- カテゴリ判定ロジック：記事タグを順に `shop.metaobjects.article_category[tag]` に当て、最初に一致したものをカテゴリとする
- タグは必ず半角英字（日本語タグはURLが文字化けするため禁止）

## 4. カテゴリの表示制御

- **記事0件のカテゴリは自動非表示**：`blog.all_tags`（公開記事のタグ一覧）にハンドルが含まれないカテゴリはチップ・カテゴリ一覧に出さない。記事を公開すれば自動で出現
- カテゴリ一覧の並びは表示名のアルファベット/五十音順（`shop.metaobjects.article_category.values` の仕様）

## 5. 記事詳細ページ（c_article）の構成要素

上から順に：

1. 読了プログレスバー（画面最上部固定・スクロール連動）
2. ヘッダー：カテゴリバッジ（tagged頁へのリンク）／タイトル／公開日・更新日（公開から1日超の更新のみ表示）／執筆・監修名／自由タグチップ
3. アイキャッチ（article.image、16:9トリミング）
4. 目次：本文のh2/h3から**JSで自動生成**（見出し2個未満なら非表示）。SP=折りたたみ`<details>`、PC=右カラム280pxで追従（sticky）＋現在地ハイライト
5. 本文 `article.content`：h2/h3/h4・表・リスト等のスタイルは `.c_article__content` スコープで自動適用。ライター用HTMLパーツ（`.ca-box` `.ca-balloon` `.ca-btn`）も同スコープ（コピペ用HTMLは setup ドキュメント参照）
6. シェア（X・LINE・URLコピー）
7. 著者・監修者カード
8. **商品CTA**「この記事を読んだ方におすすめ」（§6）
9. 関連記事：同カテゴリタグの記事を最大3件（`blog.articles` 最新50件から抽出）
10. カテゴリ一覧チップ
11. JSON-LD：Article（author/reviewedBy/articleSection）＋BreadcrumbList

## 6. 商品CTA（記事下）の設計

**表示優先順位**：
```
custom.recommendations（商品×一言のセット）
  → custom.related_products（商品のみ）
    → custom.related_collection（コレクションカード）
      → 何も表示しない
```

- カードは縦型（画像フル幅正方形→商品名→一言→価格）。SP2列/PC3列・中央寄せ。最大3件
- **一言（copy）は任意。基本は付けない**。付けた記事のみグレーの補足文が出る

**運用（都度指定方式）**：記事完成後にClaudeへ依頼 → `scripts/set_article_cta.py` が実行される：

```
python3 scripts/set_article_cta.py <記事handle> "<商品handle>" "<商品handle>::<一言>" ...
```

- エントリーは `art<記事ID>-<連番>` のハンドルで記事専用に自動生成。再実行で丸ごと置換、`--clear` で解除
- 事前登録の「訴求文バンク」方式は廃止済み（文例は [recommend-copy-bank.md](recommend-copy-bank.md) に参考として保存）

## 7. SEO設計

| 項目 | 実装 |
|---|---|
| カテゴリページのtitle | 「カテゴリ名｜コラム – ストア名」に差し替え（theme.liquid） |
| カテゴリページのdescription | article_categoryのdescriptionに差し替え |
| **noindex** | コラムの**カテゴリ以外のタグ絞り込み**（自由タグ・複数タグ）は `noindex, follow`（重複コンテンツ対策。columnブログ限定） |
| 構造化データ | 記事：Article＋BreadcrumbList。著者に資格（description）、監修者はreviewedBy |
| パンくず | TOP > コラム > カテゴリ > 記事（縦書き・c_bredcrumb。columnのみカテゴリ階層あり） |
| 記事のmeta description | Shopify標準（記事の抜粋≒excerptが使われる）→ **抜粋は必ず書く** |

## 8. API連携（Shopify Admin API）

- カスタムアプリ `claude-admin`（Devダッシュボード作成）。認証は**client credentials方式**：
  `.env`（git管理外）の `SHOPIFY_CLIENT_ID` / `SHOPIFY_CLIENT_SECRET` / `SHOPIFY_STORE_DOMAIN` から、
  スクリプトが24時間有効のアクセストークンを毎回自動発行
- スコープ：products / content / metaobjects(+definitions) / files の read+write
- スクリプト：`scripts/set_article_cta.py`（記事CTA設定）。GraphQL 2026-07
- トークン漏洩時はDevダッシュボードからシークレットをローテーション

## 9. 運用フロー（記事1本の流れ)

1. 記事を書く（管理画面）。テンプレート **column** を選択、カテゴリタグ1つ＋自由タグ、アイキャッチ、抜粋、著者（＋監修者）メタフィールド設定
2. 公開（またはプレビュー確認）
3. Claudeに記事下CTAを依頼（商品2〜3個＋必要なら一言）
4. 必要に応じて内部リンク・関連コレクションを設定

詳細チェックリストは [blog-column-setup.md](blog-column-setup.md) の「記事の書き方ルール」。

## 10. 変更時の注意

- SCSSを編集したら `sass --style=compressed --no-source-map assets/xxx.scss assets/xxx.min.css` でコンパイルして**min.cssもコミット**（VSCodeのLive Sass Compileでも可）
- **mainへのpush＝Shopify本番テーマに即反映**（GitHub連携）。テーマエディタでの変更は逆にShopifyからgitへコミットされる（`Update from Shopify` コミット）ので、push前に `git pull --rebase` が安全
- カテゴリを増やす場合：article_categoryにエントリー追加（ハンドル=スラッグ）→記事にタグを付けるだけ。テーマ改修不要
- 自由タグを増やす場合：c_tag-label.liquid に日本語名を追記
