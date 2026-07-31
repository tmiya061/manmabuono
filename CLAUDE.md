# マンマボーノ Shopifyテーマ

犬猫用無添加ペットフードEC（https://manmabuono.jp/）のDawnベースカスタムテーマ。
代表：西川さん（犬の管理栄養士ほか3資格）。運用担当：宮川さん。

## 最重要ルール

- **mainへのpush＝本番テーマに即反映**（Shopify GitHub連携）。作業は指示があれば直接mainへpushしてよいが、push・コミット・外部送信は毎回内容を報告する
- テーマエディタ側の変更が `Update from Shopify` コミットとしてリモートに入ることがある → **push前に `git pull --rebase`**
- 会話・コミットメッセージは日本語

## ビルド・規約

- SCSS: `assets/c_*.scss` を編集したら `sass --style=compressed --no-source-map assets/xxx.scss assets/xxx.min.css` でコンパイルし **min.cssもコミット**
- カスタム実装の接頭辞は `c_`（sections/snippets/assets共通）。SCSSは `@import "variables";`（$base-color: #FF7B5E, $text-color: #3C3C3C, mq()ミックスイン）
- ブランド名表記は「マンマボーノ」（カタカナ）

## Shopify Admin API連携

- `.env`（git管理外）に `SHOPIFY_CLIENT_ID` / `SHOPIFY_CLIENT_SECRET` / `SHOPIFY_STORE_DOMAIN`（007a21-4.myshopify.com）
- client credentials方式でトークンを都度発行（scripts/内のスクリプト参照）。GraphQL 2026-07
- スコープ: products/content/metaobjects(+definitions)/files のread+write
- 管理画面の設定作業は基本APIでやる（手順書を書くより速い）。書き込み時は内容を報告、削除は事前確認

## コラム（ブログ）システム

設計の全体像は **docs/blog-column-architecture.md** を必ず参照。要点：

- `/blogs/column` 一覧=c_blogList、記事=c_article。カテゴリ=記事タグ×メタオブジェクト article_category（ハンドル=スラッグ、7種: choose/trouble/feeding/health/storage/basics/homemade）
- 自由タグ: cat/dog/kitten/puppy/senior/dry/wet（日本語名は snippets/c_tag-label.liquid）
- 著者・監修者: メタオブジェクト article_author を記事メタフィールド custom.author / custom.supervisor から参照
- **記事下CTA**: 記事完成後にオーナーから商品指定を受けて `python3 scripts/set_article_cta.py <記事handle> "<商品handle>[::一言]" ...` で反映（一言は任意・基本なし）
- SEO: カテゴリ以外のタグ絞り込みはnoindex、カテゴリ頁はtitle/description差し替え（theme.liquid）

## ドキュメント索引（docs/）

- `blog-column-architecture.md` — コラムの設計全体
- `blog-column-setup.md` — 管理画面セットアップ手順・記事の書き方ルール・ライター用HTMLパーツ
- `products.md` — 全商品カタログ（訴求軸・表現の注意・商品ページ文章不備メモ）
- `recommend-copy-bank.md` — 商品訴求文の文例集（参考資料）

## 表現ルール（記事・訴求文）

- 効能の断定（治る・予防できる）はNG。「〜な子に」「〜をサポート」「〜と言われる」まで
- おかず類=栄養補完食（「総合栄養食と一緒に」）、主食=総合栄養食の区別を正確に
