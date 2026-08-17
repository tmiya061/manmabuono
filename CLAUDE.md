# マンマボーノ Shopifyテーマ

犬猫用無添加ペットフードEC（https://manmabuono.jp/）のDawnベースカスタムテーマ。
代表：西川さん（犬の管理栄養士ほか3資格）。運用担当：宮川さん。

## 最重要ルール

- 🔴 **mainへのpush＝本番テーマに即反映**（Shopify GitHub連携）。**main直コミット・直pushは可。ただし push 前に必ず宮川さんに確認を取る**（2026-07-31 確定）。ブランチ→PR を必須にしない代わりに、確認をガードとして残す運用。無確認pushはしない
  - 確認時は「何を・どこに・なぜ」を一行で。push後は SHA と内容を報告する
  - 大きい修正・見た目に影響する変更は `feature/...` を切る判断もしてよい（迷ったら確認時に相談）
  - **サイトの見た目に関わる本番反映は、加えて西川さん（クライアント）の確認が必要**。`scripts/` 等の非表示ファイルは表示に影響しないので宮川さん確認のみでよい
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

### 管理画面の変更記録（必須）

管理画面のデータは Git で追えない。**書き込み系の操作は必ず記録を残す。**

1. **戻せるようにする（先）**: 一括・破壊的な書き込みの前に、変更前の状態を JSON で保存する（例: `scripts/collection_order/dog-all.backup.json`）。取れない種類の変更は「復元手段なし」とログに明記する
2. **記録する（後）**: 作業のひと区切りごとに **docs/admin-changelog.md** の先頭へ1行追記。書き込み系のみ（読み取り・調査は記録しない）
   `- 2026-07-31 | collection dog-all | 商品63件を並び替え（主食ドライを最上位） | scripts/reorder_collection.py | 復元: scripts/collection_order/dog-all.backup.json`
3. **粒度**: 一括操作は1行にまとめる。日付 / 対象 / 何を / 手段 / 復元手段 の5つが揃っていればよい。迷ったら短くていいので残す方を選ぶ
4. **コミット**: changelog はスクリプト・バックアップと同じコミットに入れる。表示に影響しないので西川さん確認は不要（push前のオーナー確認は従来どおり必要）

## コラム（ブログ）システム

設計の全体像は **docs/blog-column-architecture.md** を必ず参照。要点：

- `/blogs/column` 一覧=c_blogList、記事=c_article。カテゴリ=記事タグ×メタオブジェクト article_category（ハンドル=スラッグ、7種: choose/trouble/feeding/health/storage/basics/homemade）
- 自由タグ: cat/dog/kitten/puppy/senior/dry/wet（日本語名は snippets/c_tag-label.liquid）
- 著者・監修者: メタオブジェクト article_author を記事メタフィールド custom.author / custom.supervisor から参照
  - **著者ページ**: article_author に `onlineStore` capability を付けてあるので、エントリーを1件足すと `/pages/author/{ハンドル}` が自動で生える（`templates/metaobject/article_author.json` ＋ `sections/c_author.liquid`）。**固定ページは作らない**。`bio` が空のあいだは theme.liquid が noindex を付ける
  - 未設定記事のフォールバック「マンマボーノ編集部」は **c_article のセクション設定 `default_author` の文字列**であって editorial-team エントリーではない（名前だけ出る。写真・資格・bio は出ない）
- **記事下CTA**: 記事完成後にオーナーから商品指定を受けて `python3 scripts/set_article_cta.py <記事handle> "<商品handle>[::一言]" ...` で反映（一言は任意・基本なし）
- SEO: カテゴリ以外のタグ絞り込みはnoindex、カテゴリ頁はtitle/description差し替え（theme.liquid）

## ドキュメント索引（docs/）

- `admin-changelog.md` — 管理画面（Admin API）の変更ログ（追記必須・上記ルール参照）
- `lp-system.md` — 🔴 **広告用LPの土台**（`page.lp-◯◯` テンプレート／LPモードでヘッダー・フッターを消す仕組み／CTAの計測／UTM規約）。**広告を出す前に §4「出稿前に必要なもの」を必ず読む**（GA4権限・Google広告コンバージョン・Meta Pixel が全部未導入）
- `cooking-class-zoom-email.md` — お料理教室：注文確認メールへのZoom案内差し込み（スニペット＋設定手順。Zoomは定期ミーティング＝同一URL運用）。ページ設計の全体は `.company/projects/clients/manmabuono/cooking_class_page.md`
- `subscription-mikawaya.md` — 🔴 **サブスク（三河屋）と `［追加用］` 商品の仕組み・要修正リスト。商品価格を変える前／新商品を出す前に必読**（追加用の価格追随を忘れると会員が定価を払う）
- `blog-column-architecture.md` — コラムの設計全体
- `blog-column-setup.md` — 管理画面セットアップ手順・記事の書き方ルール・ライター用HTMLパーツ
- `products.md` — 全商品カタログ（訴求軸・表現の注意・商品ページ文章不備メモ）
- `recommend-copy-bank.md` — 商品訴求文の文例集（参考資料）

## 表現ルール（記事・訴求文）

- 効能の断定（治る・予防できる）はNG。「〜な子に」「〜をサポート」「〜と言われる」まで
- おかず類=栄養補完食（「総合栄養食と一緒に」）、主食=総合栄養食の区別を正確に
