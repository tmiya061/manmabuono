# 管理画面（Shopify Admin）変更ログ

Shopifyの管理画面・ストアデータは Git で追えない。**書き込み系の操作をここに1行ずつ残す**（ルール＝[../CLAUDE.md](../CLAUDE.md) 「管理画面の変更記録」）。

**書式**：`- 日付 | 対象 | 何を | 手段 | 復元手段`
新しいものを上に追記する。読み取り・調査は記録しない。一括操作は1行にまとめる。

> このログは 2026-07-31 開始。それ以前の管理画面変更は記録が無く、`scripts/` のコミット履歴からしか辿れない。

---

- 2026-08-18 | コレクション26件（全28件のうち `senmon`・`c-osechi` を除く） | **SEOタイトル / メタディスクリプションを新規設定**。全28件で `seo.title`・`seo.description`・本文説明のすべてが空だったため、`layout/theme.liquid` の `page_description` が空になり `<meta name="description">` タグが1件も出力されていなかった。原稿＝`scripts/seo_meta/collection_seo.json`（設計方針は商品側 2026-08-02 と同じ／ブランド名は入れない・カテゴリ語を先頭・desc全角90〜125字）。除外理由：`senmon`＝既存顧客の専用購入ページで検索に出す性質でない（noindex は別途検討）、`c-osechi`＝商品0件。**ページ上の見た目は変わらない**（変わるのは検索結果のタイトルとスニペット） | `scripts/set_collection_seo.py --apply` | 復元: `scripts/seo_meta/collection_seo.backup.json`（26件すべて title/description とも null＝未設定に戻す）
- 2026-08-17 | メタオブジェクト定義 `article_author`（記事著者） | 著者プロフィールページ対応で **capability を2つ有効化**：`onlineStore`（urlHandle=`author` / createRedirects=true → 各エントリーが `/pages/author/{ハンドル}` で公開される）と `renderable`（metaTitleKey=`name` / metaDescriptionKey=`bio` → `<title>` と meta description に供給）。**フィールド7件・エントリー2件には変更なし**。テーマ側は `templates/metaobject/article_author.json` ＋ `sections/c_author.liquid` で描画 | `scripts/author_page/enable_online_store.py`（metaobjectDefinitionUpdate） | 復元: 同スクリプトの `enabled` を false にして再実行（変更前の定義＝`scripts/metaobject_defs/article_author.backup_20260817_pre_onlinestore.json`）
- 2026-08-17 | メタオブジェクト定義 `article_author`（記事著者） | E-E-A-T対応で**フィールドを2つ追加**：`profile_url`（url・著者紹介ページ）/ `same_as`（list.url・SNS/外部プロフィール）。既存5フィールドと既存2エントリーには変更なし（追加のみ）。テーマ側で `Person.url` / `Person.sameAs` として出力 | metaobjectDefinitionUpdate（GraphQL） | 復元: 追加した2フィールドを削除（変更前の定義＝`scripts/metaobject_defs/article_author.backup.json`）
- 2026-08-17 | article `test-article` の `custom.supervisor` ／ metaobject `nishikawa` の `profile_url`・`same_as` | 上記実装の**動作検証のため一時的に値を投入し、検証後に元へ戻した**（supervisor は metafieldsDelete で削除＝元々未設定、nishikawa は `profile_url`=null / `same_as`=`[]` に復帰）。検証は unpublished テーマ `【検証】jsonld-author-20260817`（#141067681853）で実施し、本番テーマは触っていない | GraphQL（metafieldsSet / metafieldsDelete / metaobjectUpdate） | 復元: 実施済み。投入前の状態は `scripts/metaobject_defs/jsonld_test.backup.json`
- 2026-08-17 | Shopifyアプリ `claude-seo`（Dev Dashboard → 007a21-4 にインストール） | SEO担当（外部フリー）用に2本目のカスタムアプリを作成。バージョン `claude-seo-2` をリリースしてインストール。**write は `write_content` / `write_files` の2つだけ**、残りは read（`read_content` `read_files` `read_products` `read_inventory` `read_reports` `read_metaobjects` `read_metaobject_definitions`）。テーマ・商品・メタオブジェクト定義の書き込みは意図的に付与しない。詳細は [api-apps.md](api-apps.md) | Dev Dashboard（バージョン作成→リリース→インストール） | 復元: 管理画面 > アプリ > claude-seo をアンインストール（＋Dev Dashboard でアプリ削除）
- 2026-08-10 | product 30件のメタフィールド `custom.product_table6`（栄養成分） | 商品詳細の仕様テーブル「栄養成分」に**読点を付与**（項目の切れ目がスペースだけで、どこまでが1項目か読めなかった）。あわせて項目内の空白を正規化（`0.1％ 以下`→`0.1％以下` / `kcal/ 100g`→`kcal/100g` / ラベルと値の間は半角スペース1つ）し、**単位の全角k `ｋcal`→`kcal` を統一**（7商品で混在）。数値・項目名（脂質/脂肪）は一切変更なし。オーナー指示 | `scripts/set_nutrition_punctuation.py --apply` | 復元: `scripts/set_nutrition_punctuation.py --revert`（`scripts/nutrition/backup.json`）
  - ⚠️ **読点を入れて可視化された値そのものの破綻は未対応（西川さん確認待ち）**：①`京の一番だし5袋` は脂質の値が抜けて以降が1つずつズレ（単品版が正なら 脂質0.1/粗繊維0.4/灰分0.5）②`地鶏のそぼろ煮3袋` は1袋と数値が食い違い（15.4→14.6・6.0→5.8）＋以上/以下が逆＋末尾に「以下」が流れている ③`枕崎-かつおのうま煮` の1袋/3袋が「脂質 vs 脂肪」「水分 79.7 vs 79.4」で不一致 ④`ダブルだし猫のごはん` だけ数値が全角（３１．８％）
- 2026-08-10 | ページ set-teiki | **非公開 → 公開**に変更（西川さんに骨組みを見てもらうため。中身はプレースホルダのまま） | pageUpdate（GraphQL） | 復元: `isPublished: false` に戻す。変更前の状態は /tmp/page_set_teiki_before.json ＝ `{isPublished:false, publishedAt:null}`。**テーマ側で noindex を付けてあるので検索には載らない**が、URLを知っていれば誰でも見られる状態
- 2026-08-09 | ページ set-teiki（ドライ×ウェット セット定期便 LP・準備中） | **非公開**で新規作成。テンプレート `page.lp-set-teiki` を割り当て（広告用LPの器。中身は西川さん確認待ちのプレースホルダ） | pageCreate（GraphQL） | 復元: ページを削除（gid://shopify/Page/107051450429）。非公開なので店頭には出ていない
- 2026-08-09 | 商品メタフィールド定義 custom.card_label | 「商品カードのラベル」を新規作成（商品・単一行テキスト・16文字上限・ピン留め） | metafieldDefinitionCreate（GraphQL） | 復元: 定義を削除（gid://shopify/MetafieldDefinition/130898526269）。削除すると下記35件の値も消える
- 2026-08-09 | 商品35件 | custom.card_label に効能ラベルの文言を投入（コード内の暫定マップから移行。以後は管理画面で編集する） | scripts/set_card_labels.py --apply | 復元: scripts/card_label/card_label.backup.json（投入前は全件 null＝未設定）
- 2026-08-08 | 商品 online-cooking-class | タグ「一覧非表示」を追加（テーマ側で商品一覧グリッドから除外するため） | tagsAdd（GraphQL） | 復元: タグを外す
- 2026-08-08 | コレクション | handle「all」のスマートコレクションを作成→自動allの上書きが効かず同日削除（現存しない） | REST smart_collections | 復元手段なし（不要）
- 2026-08-08 | 商品24件 | 本文から「こんな子におすすめ」ブロック（c_prodStory__fit）を削除 | scripts/remove_prodstory_fit.py --apply | 復元: scripts/product_story/fit_removal_backup.json

- 2026-08-02 | 商品6件（ドライ主食）| 仕様テーブル「与え方」の行中●の前に改行を挿入（●箇条書きが1段落に潰れて表示されていた） | インラインスクリプト（productUpdate） | 復元: scripts/product_table/linebreaks.backup.json

- 2026-08-02 | 商品24件 | 本文を「型」（見出し/こんな子におすすめ/無添加ブロック）で再構成。効能断定表現は表現ルールに沿い言い換え | scripts/set_product_story.py --apply | 復元: scripts/product_story/backup.json（--revert）。前後全文: docs/product-copy-history.md

- 2026-08-02 | 商品24件 | 本文から仕様情報（原材料/賞味期限/与え方/保存方法/ご注意/栄養成分）を metafield custom.product_table1〜6 へ移し、本文を読み物部分だけに整理（チキン150gの内容量800g誤記も150gに修正） | scripts/set_product_table.py --apply | 復元: scripts/product_table/backup.json（--revert）

- 2026-08-02 | product ACTIVE 36件 | `seo.title` / `seo.description` を新規設定（全71商品で未設定＝Shopifyが本文冒頭を機械的に切り出してスニペットにしていた状態を解消）。原稿は `scripts/seo_meta/product_seo.json`、設計方針は `.company/projects/clients/manmabuono/seo_product_meta.md`。オーナー指示で反映（**西川さん確認は未取得**）。※`yamashita-sama` は非公開化提案中のため対象外。※`［追加用］`（UNLISTED 22件）はサイトマップ非掲載のため対象外 | `scripts/set_product_seo.py --apply` | 復元: `scripts/seo_meta/product_seo.backup.json`（全件 `{}` ＝未設定に戻す）
- 2026-08-02 | product `無塩-鹿児島枕崎-おつお削り節`（ACTIVE）＋ `-追加用`（UNLISTED）の2件 | 商品名の誤字を修正「お**つ**お削り節」→「か**つ**お削り節」。ACTIVE側は `<title>` と `<h1>` に露出しており検索結果にそのまま出ていた。オーナー指示。※handle は `おつお` のまま（URL変更はインデックス張り替えのリスクに対して利得が無いため据え置き）。※商品名の「無塩」表記 vs 本文「減塩・塩分0.1%」の不整合は**未対応**（西川さん確認待ち） | Admin GraphQL `productUpdate`（単発・スクリプト未作成） | 復元: `scripts/seo_meta/product_title_typo.backup.json`
- 2026-08-02 | product `online-cooking-class` のバリアント3件 | 在庫設定を「定員＝在庫」に統一（8/16・8/23 は **在庫追跡OFF＝無制限購入可**のまま放置されていたので `tracked=true` にし、8/9 と同じ **available=5** をセット）。オーナー指示のテスト目的。※作業前は「数量0＝売り切れ」に見えたが実際は追跡OFFで購入可だった＝**数量だけ見て売り切れと判断しないこと** | `scripts/set_cooking_class_inventory.py --apply` | 復元: `scripts/set_cooking_class_inventory.py --revert`（`scripts/cooking_class/inventory.backup.json`）
  - 実装メモ：`inventorySetQuantities` は 2026-07 で **`changeFromQuantity` 必須**（現在値との照合）＋ **`@idempotent(key:)` ディレクティブ必須**。`ignoreCompareQuantity` は存在しない。`location { name }` は `read_locations` が要る（IDだけなら不要）
- 2026-08-02 | product `online-cooking-class` ＋ page `cooking-class` | お料理教室の商品（¥500・バリアント3件＝開催日［仮日程・西川さん確認前］・配送不要・在庫追跡なし・`seo.hidden=1` で検索/サイトマップ非表示・コレクション所属なし）とページ（`/pages/cooking-class`・template=cooking-class・ナビからのリンクなし）を新規作成。Online Store公開はスコープ不足のため REST 2024-01 の `published=true` で実施 | `scripts/setup_cooking_class.py --apply` | 復元: `scripts/setup_cooking_class.py --revert`（`scripts/cooking_class/created.json` のIDを削除）
- 2026-08-02 | theme（非公開） | 確認用テーマ「【確認用】fv-banner（FV内バナー＋犬猫タブ＋お悩み）」#140800557117 を作成（feature/fv-banner を push。西川さん確認用プレビュー。※page.json の shop_tokyo アプリブロック1件だけ push 不可＝既存問題・トップには無関係） | `shopify theme push --unpublished` | 復元: 管理画面でテーマ削除
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
