# 管理画面（Shopify Admin）変更ログ

Shopifyの管理画面・ストアデータは Git で追えない。**書き込み系の操作をここに1行ずつ残す**（ルール＝[../CLAUDE.md](../CLAUDE.md) 「管理画面の変更記録」）。

**書式**：`- 日付 | 対象 | 何を | 手段 | 復元手段`
新しいものを上に追記する。読み取り・調査は記録しない。一括操作は1行にまとめる。

> このログは 2026-07-31 開始。それ以前の管理画面変更は記録が無く、`scripts/` のコミット履歴からしか辿れない。

---

- 2026-07-31 | collection `cat-all` | 商品58件を並び替え（犬の原則＋猫向けに2点変更：スープ・だしをプレミアム料理より上位／ウェットは魚を先頭） | `scripts/reorder_collection.py --apply` | 復元: `scripts/collection_order/cat-all.backup.json`
- 2026-07-31 | collection `dog-all` | 商品63件を並び替え（主食ドライを最上位・同一商品は容量小→大でまとめ・おやつ/季節ものを下部へ） | `scripts/reorder_collection.py --apply` | 復元: `scripts/collection_order/dog-all.backup.json`
- 2026-07-31 | blog `column` の記事メタフィールド | 記事下CTA（商品指定）を設定 | `scripts/set_article_cta.py` | 復元手段なし（対象記事の記録も残っていない。ログ運用開始前のため）
