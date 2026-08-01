# 管理画面（Shopify Admin）変更ログ

Shopifyの管理画面・ストアデータは Git で追えない。**書き込み系の操作をここに1行ずつ残す**（ルール＝[../CLAUDE.md](../CLAUDE.md) 「管理画面の変更記録」）。

**書式**：`- 日付 | 対象 | 何を | 手段 | 復元手段`
新しいものを上に追記する。読み取り・調査は記録しない。一括操作は1行にまとめる。

> このログは 2026-07-31 開始。それ以前の管理画面変更は記録が無く、`scripts/` のコミット履歴からしか辿れない。

---

- 2026-08-02 | product `online-cooking-class` ＋ page `cooking-class` | お料理教室の商品（¥500・バリアント3件＝開催日［仮日程・西川さん確認前］・配送不要・在庫追跡なし・`seo.hidden=1` で検索/サイトマップ非表示・コレクション所属なし）とページ（`/pages/cooking-class`・template=cooking-class・ナビからのリンクなし）を新規作成。Online Store公開はスコープ不足のため REST 2024-01 の `published=true` で実施 | `scripts/setup_cooking_class.py --apply` | 復元: `scripts/setup_cooking_class.py --revert`（`scripts/cooking_class/created.json` のIDを削除）
- 2026-08-01 | collection `cat-wet` → テンプレート `wet` ／ `dog-all` `cat-all` → テンプレート `all` | 代替テーマテンプレートを割り当て＝**店頭の見た目が変わった**（ウェット2ページが3グループ、全商品2ページが9グループの小カテゴリ表示に）。`dog-wet` は元から `wet` 割当済みで変更なし。反映確認＝4ページとも表示商品数が公開商品数と一致（15/15/31/28） | `scripts/set_collection_template.py --apply` | 復元: `scripts/set_collection_template.py --revert`（`scripts/collection_template/backup.json`）
- 2026-08-01 | product 19件 ＋ collection 6本 `main-dry` `trial` `topping` `homemade` `treats` `seasonal` | 全商品ページ（dog-all / cat-all）の小カテゴリ用に中立タイプタグ6種を付与（`主食ドライ`6 / `お試しセット`2 / `トッピング`2 / `手作り素材`3 / `おやつ`4 / `季節もの`2）し、各タグの自動コレクションを作成（MANUAL・handleに dog/cat を含めないのでナビには出ない）。既存の `犬用ドライフード` タグだけだとふりかけが主食に混ざる／お試しが犬猫別タグで共通テンプレから拾えないため中立タグが必要だった | `scripts/setup_all_subcategory.py --apply` | 復元: `scripts/setup_all_subcategory.py --revert`（`scripts/all_subcategory/backup.json`）
  - ⚠️ 作成した6コレクションも**オンラインストア未公開**（`write_publications` スコープ無し）。表示には影響しない
- 2026-08-01 | product 8件（そぼろ煮・鹿肉煮込み・ぶりのうま煮・かつおのうま煮 の 単品/×3袋）＋ collection 2本 `okazu` `premium` | 「おかず」タグを8商品に付与し、自動コレクション2本を新規作成（`okazu`＝TAG EQUALS 'おかず' 8件 / `premium`＝TAG EQUALS '犬と猫のプレミアム料理' 3件、いずれも MANUAL・handleに dog/cat を含めないのでナビには出ない）。ウェットページの小カテゴリ表示をスープ・だしと同じ「タグ→コレクション」の形に揃えるため | `scripts/setup_wet_subcategory.py --apply` | 復元: `scripts/setup_wet_subcategory.py --revert`（`scripts/wet_subcategory/backup.json`）
  - ⚠️ 作成した2コレクションは**オンラインストアに未公開**（`/collections/okazu` は404）。APIアプリに `write_publications` スコープが無いため管理画面での公開が必要。ウェットページの表示には影響しない
- 2026-08-01 | product `［追加用］` 3件（プレミアム料理 親子丼の素 / 鹿肉煮込みハンバーグ / 鰤と大根の炊いたん） | 価格を通常版×0.9 に修正（¥1,210→¥1,089 / ¥1,430→¥1,287 / ¥1,320→¥1,188）。2026-05-11 に複製したまま価格未変更で放置されていた分 | `scripts/check_addon_prices.py --fix` | 復元: `scripts/collection_order/addon_prices.backup.json`
- 2026-07-31 | collection `dog-dry` / `cat-dry` / `dog-wet` / `cat-wet` / `dog-make-6` / `cat-make` / `dog-easy-cook-5` （下位7コレクション） | 商品を並び替え（dog-all/cat-all と同じ原則を適用。犬ウェットは プレミアム料理→中段 に降格、猫はスープ・だしを上位＋魚を先頭） | `scripts/reorder_collection.py --apply` | 復元: `scripts/collection_order/<handle>.backup.json`
- 2026-07-31 | collection `cat-all` | 商品58件を並び替え（犬の原則＋猫向けに2点変更：スープ・だしをプレミアム料理より上位／ウェットは魚を先頭） | `scripts/reorder_collection.py --apply` | 復元: `scripts/collection_order/cat-all.backup.json`
- 2026-07-31 | collection `dog-all` | 商品63件を並び替え（主食ドライを最上位・同一商品は容量小→大でまとめ・おやつ/季節ものを下部へ） | `scripts/reorder_collection.py --apply` | 復元: `scripts/collection_order/dog-all.backup.json`
- 2026-07-31 | blog `column` の記事メタフィールド | 記事下CTA（商品指定）を設定 | `scripts/set_article_cta.py` | 復元手段なし（対象記事の記録も残っていない。ログ運用開始前のため）

---

> 📄 **サブスク・`［追加用］` 商品の仕組みと要修正リストは [subscription-mikawaya.md](./subscription-mikawaya.md) に分離した**（2026-07-31）。商品価格を変える前・新商品を出す前に必ずそちらを読むこと。以下は調査時のメモの残り。

## 参考：商品構成の実態（2026-07-31 調査／**書き込みなし**）

### `［追加用］` 商品＝サブスク追加用の低価格版

- サブスクアプリ＝**三河屋サブスクリプション**。Shopifyネイティブの selling plan を使う作りで、テーマ側は Dawn 標準の `selling_plan` 実装（`snippets/buy-buttons.liquid` 等）で動いている。**アプリ固有のコードはテーマに無い**。
- 販売プラングループ `定期購入` … **10% OFF・配送頻度1種**。公開商品31件に紐付く。
- **`［追加用］` は、通常版のちょうど10%引きを価格として直接設定した非公開（UNLISTED）商品**。定期購入プランは付いていない（＝既存サブスクに単品を後から足すための受け皿）。**29件がきっちり10.0%OFFで一致**しており、この設計で確定。

> 以降の詳細（サポート回答・運用チェックリスト・登録先・要修正リスト・マイページの仕組み）は
> **[subscription-mikawaya.md](./subscription-mikawaya.md)** に移設した。重複を避けるためここには置かない。
