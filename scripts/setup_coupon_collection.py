#!/usr/bin/env python3
"""20%OFFクーポンの「適用対象」コレクションを作る。

  python3 scripts/setup_coupon_collection.py           # dry-run（何が入って何が外れるか出すだけ）
  python3 scripts/setup_coupon_collection.py --apply   # 実際に作る
  python3 scripts/setup_coupon_collection.py --delete  # 作ったものを消す（戻す手段）

なぜコレクションが要るのか
--------------------------
🔴 **Shopifyのディスカウントに「この商品だけ除外」という設定は無い。**
   選べるのは「すべての商品」「特定のコレクション」「特定の商品」の3つだけで、
   除外リストという概念が存在しない。
   したがって「お試しセット以外の全部」を表現するには、
   **対象になる商品だけが入ったコレクションを作って、そこにクーポンを紐づける**しかない。

   71商品を手で選ぶ方式にしないこと。新商品を出すたびにクーポンの対象から漏れる。
   ここでは**自動コレクション（タグ条件）**にしているので、
   新商品は何もしなくても自動で対象に入り、`お試しセット` タグを付けた商品だけが外れる。

除外の判定に使うもの
--------------------
商品タグ `お試しセット`。現在これが付いているのは2件だけ：
  ・初回限定犬用お試しセット（dog-trial-set / ¥3,300）
  ・初回限定猫用お試しセット（cat-trial-set / ¥3,300）
今後お試し系を増やすときは**このタグを付ければ自動で対象外**になる。

⚠️ `【食事代行サービス】オリジナルフード お試しセット`（¥11,000）はタグが空なので**対象に含まれる**。
   これも外すなら同じタグを付ける（→ オーナー判断）。

このスクリプトでやらないこと
----------------------------
**ディスカウント（1122）自体の書き換えはやらない・できない。**
このアプリに discounts のスコープが無いため。コレクションを作るところまでが範囲で、
「クーポンの適用対象をこのコレクションにする」操作は管理画面（またはスコープ追加後）。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shopifyql  # noqa: E402

HANDLE = "coupon-eligible"
TITLE = "クーポン対象商品"
EXCLUDE_TAG = "お試しセット"


def q_products(query):
    d = shopifyql.gql(
        'query($q:String!){ products(first:250, query:$q){ nodes{ id title handle tags } } }',
        {"q": query},
    )
    return d["products"]["nodes"]


def find_collection():
    d = shopifyql.gql(
        'query($q:String!){ collections(first:5, query:$q){ nodes{ id handle title productsCount{count} } } }',
        {"q": f"handle:{HANDLE}"},
    )
    for c in d["collections"]["nodes"]:
        if c["handle"] == HANDLE:
            return c
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="実際に作る")
    p.add_argument("--delete", action="store_true", help="作ったコレクションを削除する")
    a = p.parse_args()

    shopifyql.load_env()

    excluded = q_products(f"tag:'{EXCLUDE_TAG}'")
    included = q_products(f"-tag:'{EXCLUDE_TAG}'")

    print(f"■ 除外される商品（タグ「{EXCLUDE_TAG}」）… {len(excluded)}件")
    for x in excluded:
        print(f"   - {x['title']}  ({x['handle']})")
    print(f"\n■ クーポン対象になる商品 … {len(included)}件")

    tagless = [x for x in included if not x["tags"]]
    if tagless:
        print(f"\n⚠️ タグが1つも付いていない商品が {len(tagless)}件あり、対象に含まれる:")
        for x in tagless:
            print(f"   - {x['title']}  ({x['handle']})")

    existing = find_collection()
    print(f"\n■ コレクション `{HANDLE}` … " + (f"既にある（{existing['productsCount']['count']}件）" if existing else "まだ無い"))

    if a.delete:
        if not existing:
            print("削除するものが無い。")
            return
        shopifyql.gql(
            'mutation($id:ID!){ collectionDelete(input:{id:$id}){ deletedCollectionId userErrors{field message} } }',
            {"id": existing["id"]},
        )
        print(f"削除した: {existing['id']}")
        return

    if not a.apply:
        print("\n（dry-run。実行するなら --apply）")
        return

    if existing:
        print("既にあるので作成しない。条件を変えたい場合は --delete してから。")
        return

    # 自動コレクション：タグが「お試しセット」ではない、という1条件だけ
    res = shopifyql.gql(
        """mutation($in: CollectionInput!) {
             collectionCreate(input:$in){
               collection{ id handle title productsCount{count} }
               userErrors{ field message } } }""",
        {"in": {
            "title": TITLE,
            "handle": HANDLE,
            "descriptionHtml": "<p>初回20%OFFクーポンの適用対象。お試しセットを除く全商品（自動更新）。</p>",
            "ruleSet": {
                "appliedDisjunctively": False,
                "rules": [{"column": "TAG", "relation": "NOT_EQUALS", "condition": EXCLUDE_TAG}],
            },
            "metafields": [{
                # 検索に出さない（既存の set_collection_noindex.py と同じ仕組み）
                "namespace": "seo", "key": "hidden", "type": "number_integer", "value": "1",
            }],
        }},
    )["collectionCreate"]

    if res["userErrors"]:
        print("🔴 エラー:", json.dumps(res["userErrors"], ensure_ascii=False, indent=1))
        sys.exit(1)

    c = res["collection"]
    print(f"\n作成した: {c['handle']}  id={c['id']}")
    print(f"  → 反映まで少し時間がかかる。あとで件数が {len(included)} になっているか確認すること")
    print(f"  → 次は管理画面でクーポン 1122 の適用対象をこのコレクションにする（このスクリプトの範囲外）")
    print(f"  → 戻すには: python3 scripts/setup_coupon_collection.py --delete")


if __name__ == "__main__":
    main()
