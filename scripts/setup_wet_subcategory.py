#!/usr/bin/env python3
"""ウェットの小カテゴリ（おかず／プレミアム料理）をタグ＋コレクションで整備する。

背景:
  ウェットページ（collection.wet.json）の小カテゴリ表示は
  c_collection-tag-group が「今開いているコレクションの商品」をタグで絞る方式。
  「スープ・だし」はタグ＋自動コレクション（handle: soup）が既にあるが、
  「おかず」はタグ自体が存在せず、プレミアムは商品タグはあるがコレクションが無かった。
  → スープ・だしと同じ形に揃える。

やること (--apply):
  1. おかず8商品に「おかず」タグを付与（変更前のタグは backup.json に退避）
  2. 自動コレクション2本を作成
     - okazu   「おかず」            = TAG EQUALS 'おかず'
     - premium 「犬と猫のプレミアム料理」 = TAG EQUALS '犬と猫のプレミアム料理'
     いずれも sortOrder=MANUAL（後から reorder_collection.py で並べられるように）

対象外（意図的）:
  - ［追加用］等の UNLISTED 商品にはタグを付けない。既存の「スープ・だし」も
    ACTIVE な4商品にしか付いていない＝その流儀に合わせる。
  - 「無農薬野菜の炊いたん」は UNLISTED（未公開）のため今回は対象外。
    公開するときに一緒に「おかず」タグを付ける。

handle について:
  okazu / premium とも handle に dog / cat を含めない。ナビ生成
  （c_collectionCategory / header-drawer / header-mega-menu / footer）は
  handle に 'dog' か 'cat' を含むコレクションだけを拾うので、含めなければ
  勝手にメニューへ出ない（soup と同じ扱い）。

使い方:
  python3 scripts/setup_wet_subcategory.py            # 現状表示（dry-run）
  python3 scripts/setup_wet_subcategory.py --apply    # 本番反映
  python3 scripts/setup_wet_subcategory.py --revert   # backup.json から巻き戻し
"""

import json
import os
import sys
import urllib.parse
import urllib.request

API_VERSION = "2026-07"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = os.path.join(ROOT, "scripts", "wet_subcategory")
BACKUP = os.path.join(BACKUP_DIR, "backup.json")
TOKEN = None

OKAZU_TAG = "おかず"
PREMIUM_TAG = "犬と猫のプレミアム料理"

# 「おかず」を付ける商品（ACTIVE のみ・handle で指定）
OKAZU_HANDLES = [
    "地鶏のそぼろ煮1袋",
    "地鶏のそぼろ煮3袋",
    "京都笠置-鹿肉と無農薬野菜の煮込み",
    "京都笠置-鹿肉と無農薬野菜の煮込み3袋",
    "舞鶴-ぶりのうま煮1袋",
    "舞鶴-ぶりのうま煮3袋",
    "枕崎-かつおのうま煮1袋",
    "枕崎-かつおのうま煮3袋",
]

COLLECTIONS = [
    {"handle": "okazu", "title": "おかず", "tag": OKAZU_TAG},
    {"handle": "premium", "title": "犬と猫のプレミアム料理", "tag": PREMIUM_TAG},
]


def load_env():
    with open(os.path.join(ROOT, ".env")) as f:
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
        return json.load(r)["access_token"]


def gql(query, variables=None):
    global TOKEN
    if TOKEN is None:
        TOKEN = get_token()
    domain = os.environ["SHOPIFY_STORE_DOMAIN"]
    req = urllib.request.Request(
        f"https://{domain}/admin/api/{API_VERSION}/graphql.json",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Content-Type": "application/json", "X-Shopify-Access-Token": TOKEN})
    with urllib.request.urlopen(req) as r:
        out = json.load(r)
    if "errors" in out:
        print("GraphQL error:", json.dumps(out["errors"], ensure_ascii=False, indent=2))
        sys.exit(1)
    return out["data"]


Q_PRODUCT = """
query($handle: String!) {
  productByHandle(handle: $handle) { id handle title status tags }
}
"""

Q_COLLECTION = """
query($handle: String!) {
  collectionByHandle(handle: $handle) {
    id handle title sortOrder productsCount { count }
    ruleSet { appliedDisjunctively rules { column relation condition } }
  }
}
"""

M_TAGS_ADD = """
mutation($id: ID!, $tags: [String!]!) {
  tagsAdd(id: $id, tags: $tags) { userErrors { field message } }
}
"""

M_TAGS_REMOVE = """
mutation($id: ID!, $tags: [String!]!) {
  tagsRemove(id: $id, tags: $tags) { userErrors { field message } }
}
"""

M_COLLECTION_CREATE = """
mutation($input: CollectionInput!) {
  collectionCreate(input: $input) {
    collection { id handle title sortOrder }
    userErrors { field message }
  }
}
"""

M_COLLECTION_DELETE = """
mutation($input: CollectionDeleteInput!) {
  collectionDelete(input: $input) { deletedCollectionId userErrors { field message } }
}
"""


def fetch_products():
    out = []
    for h in OKAZU_HANDLES:
        p = gql(Q_PRODUCT, {"handle": h})["productByHandle"]
        if p is None:
            print(f"❌ 商品が見つからない: {h}")
            sys.exit(1)
        out.append(p)
    return out


def show_status(products):
    print("── おかずタグ対象商品 ──")
    for p in products:
        mark = "✅済" if OKAZU_TAG in p["tags"] else "  未"
        print(f"{mark} {p['status']:<7} {p['title'][:36]:<38} tags={p['tags']}")
    print("\n── コレクション ──")
    for c in COLLECTIONS:
        got = gql(Q_COLLECTION, {"handle": c["handle"]})["collectionByHandle"]
        if got:
            rs = got["ruleSet"]
            rule = " / ".join(f"{r['column']} {r['relation']} '{r['condition']}'" for r in rs["rules"]) if rs else "手動"
            print(f"✅済 {got['handle']:<10} {got['title'][:20]:<22} {got['productsCount']['count']}件 sort={got['sortOrder']} {rule}")
        else:
            print(f"  未 {c['handle']:<10} {c['title'][:20]:<22} → TAG EQUALS '{c['tag']}' で作成予定")


def apply(products):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if os.path.exists(BACKUP):
        backup = json.load(open(BACKUP))
    else:
        backup = {"products": {p["handle"]: p["tags"] for p in products}, "created_collections": []}
        with open(BACKUP, "w") as f:
            json.dump(backup, f, ensure_ascii=False, indent=2)
        print(f"変更前のタグを退避: {os.path.relpath(BACKUP, ROOT)}")

    for p in products:
        if OKAZU_TAG in p["tags"]:
            print(f"skip（付与済）: {p['title'][:36]}")
            continue
        res = gql(M_TAGS_ADD, {"id": p["id"], "tags": [OKAZU_TAG]})["tagsAdd"]
        if res["userErrors"]:
            print("❌", res["userErrors"])
            sys.exit(1)
        print(f"✅ タグ付与: {p['title'][:36]}")

    for c in COLLECTIONS:
        got = gql(Q_COLLECTION, {"handle": c["handle"]})["collectionByHandle"]
        if got:
            print(f"skip（作成済）: {c['handle']}")
            continue
        res = gql(M_COLLECTION_CREATE, {"input": {
            "title": c["title"],
            "handle": c["handle"],
            "sortOrder": "MANUAL",
            "ruleSet": {
                "appliedDisjunctively": False,
                "rules": [{"column": "TAG", "relation": "EQUALS", "condition": c["tag"]}],
            },
        }})["collectionCreate"]
        if res["userErrors"]:
            print("❌", res["userErrors"])
            sys.exit(1)
        col = res["collection"]
        print(f"✅ コレクション作成: {col['handle']} ({col['title']}) {col['id']}")
        backup["created_collections"].append(col["id"])
        with open(BACKUP, "w") as f:
            json.dump(backup, f, ensure_ascii=False, indent=2)


def revert():
    if not os.path.exists(BACKUP):
        print("backup.json が無い。巻き戻せない。")
        sys.exit(1)
    backup = json.load(open(BACKUP))
    for handle, tags in backup["products"].items():
        p = gql(Q_PRODUCT, {"handle": handle})["productByHandle"]
        remove = [t for t in p["tags"] if t not in tags]
        if not remove:
            continue
        res = gql(M_TAGS_REMOVE, {"id": p["id"], "tags": remove})["tagsRemove"]
        if res["userErrors"]:
            print("❌", res["userErrors"])
            sys.exit(1)
        print(f"↩️ タグ除去 {remove}: {p['title'][:36]}")
    for cid in backup.get("created_collections", []):
        res = gql(M_COLLECTION_DELETE, {"input": {"id": cid}})["collectionDelete"]
        if res["userErrors"]:
            print("❌", res["userErrors"])
            sys.exit(1)
        print(f"↩️ コレクション削除: {cid}")
    backup["created_collections"] = []
    with open(BACKUP, "w") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2)


def main():
    load_env()
    args = sys.argv[1:]
    if "--revert" in args:
        revert()
        return
    products = fetch_products()
    if "--apply" in args:
        apply(products)
        print()
        show_status(fetch_products())
    else:
        show_status(products)
        print("\n（dry-run。反映するには --apply）")


if __name__ == "__main__":
    main()
