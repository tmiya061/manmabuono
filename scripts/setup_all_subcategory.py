#!/usr/bin/env python3
"""全商品コレクション（dog-all / cat-all）の小カテゴリ用タグ＋コレクションを整備する。

背景:
  ウェットページ（collection.wet.json）と同じ方式を全商品ページにも広げる。
  表示は c_collection-tag-group が「今開いているコレクションの商品」をタグで
  絞る形なので、全商品ページを小カテゴリに割るには *中立の（犬猫を含まない）
  タイプタグ* が要る。

  既存タグでは足りない理由:
  - ふりかけ2品（かつお削り節・ちりめんじゃこ）に `犬用ドライフード` タグが
    付いているため、既存タグで「主食」を括ると主食にふりかけが混ざる。
  - お試しセットは `犬用お試しセット` / `猫用お試しセット` と犬猫別なので、
    犬猫共通テンプレ1枚では拾えない。

やること (--apply):
  1. 中立タイプタグ6種を該当商品に付与（変更前のタグは backup.json に退避）
  2. 各タグの自動コレクションを作成（sortOrder=MANUAL、handle に dog/cat を
     含めないのでナビ生成には出ない＝soup / okazu / premium と同じ扱い）

グループ順（2026-08-01 オーナー確定・7/31の並び順原則に揃える）:
  主食ドライ → お試しセット → おかず → プレミアム料理 → スープ・だし
  → トッピング → 手作り素材 → おやつ → 季節もの
  ※ おかず / スープ・だし / 犬と猫のプレミアム料理 は付与済み
    （scripts/setup_wet_subcategory.py）

対象外（意図的）:
  - ［追加用］等の UNLISTED 商品にはタグを付けない（既存タグの流儀に合わせる）

使い方:
  python3 scripts/setup_all_subcategory.py            # 現状表示（dry-run）
  python3 scripts/setup_all_subcategory.py --apply    # 本番反映
  python3 scripts/setup_all_subcategory.py --revert   # backup.json から巻き戻し
"""

import json
import os
import sys
import urllib.parse
import urllib.request

API_VERSION = "2026-07"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = os.path.join(ROOT, "scripts", "all_subcategory")
BACKUP = os.path.join(BACKUP_DIR, "backup.json")
TOKEN = None

# タグ → (コレクションhandle, コレクション名, 対象商品handle)
GROUPS = [
    {
        "tag": "主食ドライ",
        "handle": "main-dry",
        "title": "主食（ドライフード）",
        "products": [
            "だし薫る犬のごはん-チキン-150g",
            "だし薫る犬のごはん-チキン",          # 800g
            "だし薫る犬のごはん-フィッシュ-150g",
            "だし薫る犬のごはん-フィッシュ-800g",
            "ダブルだし猫のごはん-チキン-150g",
            "ダブルだし猫のごはん-チキン-800g",
        ],
    },
    {
        "tag": "お試しセット",
        "handle": "trial",
        "title": "お試しセット",
        "products": ["dog-trial-set", "cat-trial-set"],
    },
    {
        "tag": "トッピング",
        "handle": "topping",
        "title": "トッピング・ふりかけ",
        "products": ["無塩-鹿児島枕崎-かつお削り節", "広島呉-ちりめんじゃこのふりかけ"],
    },
    {
        "tag": "手作り素材",
        "handle": "homemade",
        "title": "手作りごはんの素材",
        "products": [
            "旬の無農薬野菜セット-送料込み",
            "チキンボーンブロス2袋-旬の無農薬野菜セット-送料込み",
            "国内産-吉野本葛",
        ],
    },
    {
        "tag": "おやつ",
        "handle": "treats",
        "title": "おやつ",
        "products": [
            "長野信州-熟成黒毛和牛",
            "犬と猫のおやつ-京都笠置-熟成鹿肉",
            "犬と猫のおやつ-京都舞鶴-熟成鰤-30ｇ",
            "犬と猫のおやつ-鳥取大山-熟成がいな鶏-30ｇ",
        ],
    },
    {
        "tag": "季節もの",
        "handle": "seasonal",
        "title": "季節限定",
        "products": ["管理栄養士が作る犬の手作り京おせち", "京都笠置産-鹿肉の年越しそば"],
    },
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


Q_PRODUCT = "query($handle: String!) { productByHandle(handle: $handle) { id handle title status tags } }"

Q_COLLECTION = """
query($handle: String!) {
  collectionByHandle(handle: $handle) {
    id handle title sortOrder productsCount { count }
    ruleSet { rules { column relation condition } }
  }
}
"""

M_TAGS_ADD = "mutation($id: ID!, $tags: [String!]!) { tagsAdd(id: $id, tags: $tags) { userErrors { field message } } }"
M_TAGS_REMOVE = "mutation($id: ID!, $tags: [String!]!) { tagsRemove(id: $id, tags: $tags) { userErrors { field message } } }"

M_COLLECTION_CREATE = """
mutation($input: CollectionInput!) {
  collectionCreate(input: $input) {
    collection { id handle title }
    userErrors { field message }
  }
}
"""

M_COLLECTION_DELETE = """
mutation($input: CollectionDeleteInput!) {
  collectionDelete(input: $input) { deletedCollectionId userErrors { field message } }
}
"""


def fetch(handle):
    p = gql(Q_PRODUCT, {"handle": handle})["productByHandle"]
    if p is None:
        print(f"❌ 商品が見つからない: {handle}")
        sys.exit(1)
    return p


def show_status():
    for g in GROUPS:
        col = gql(Q_COLLECTION, {"handle": g["handle"]})["collectionByHandle"]
        state = f"✅{col['productsCount']['count']}件" if col else "  未作成"
        print(f"■ {g['tag']:<6} → collection {g['handle']:<10} {state}")
        for h in g["products"]:
            p = fetch(h)
            mark = "✅済" if g["tag"] in p["tags"] else "  未"
            print(f"   {mark} {p['status']:<7} {p['title'][:38]}")
        print()


def apply():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup = json.load(open(BACKUP)) if os.path.exists(BACKUP) else {"products": {}, "created_collections": []}

    for g in GROUPS:
        for h in g["products"]:
            p = fetch(h)
            backup["products"].setdefault(h, p["tags"])
            if g["tag"] in p["tags"]:
                print(f"skip（付与済）: {p['title'][:34]}")
                continue
            res = gql(M_TAGS_ADD, {"id": p["id"], "tags": [g["tag"]]})["tagsAdd"]
            if res["userErrors"]:
                print("❌", res["userErrors"])
                sys.exit(1)
            print(f"✅ {g['tag']:<6} → {p['title'][:34]}")
        with open(BACKUP, "w") as f:
            json.dump(backup, f, ensure_ascii=False, indent=2)

    for g in GROUPS:
        if gql(Q_COLLECTION, {"handle": g["handle"]})["collectionByHandle"]:
            print(f"skip（作成済）: {g['handle']}")
            continue
        res = gql(M_COLLECTION_CREATE, {"input": {
            "title": g["title"],
            "handle": g["handle"],
            "sortOrder": "MANUAL",
            "ruleSet": {
                "appliedDisjunctively": False,
                "rules": [{"column": "TAG", "relation": "EQUALS", "condition": g["tag"]}],
            },
        }})["collectionCreate"]
        if res["userErrors"]:
            print("❌", res["userErrors"])
            sys.exit(1)
        col = res["collection"]
        print(f"✅ コレクション作成: {col['handle']} ({col['title']})")
        backup["created_collections"].append(col["id"])
        with open(BACKUP, "w") as f:
            json.dump(backup, f, ensure_ascii=False, indent=2)


def revert():
    if not os.path.exists(BACKUP):
        print("backup.json が無い。巻き戻せない。")
        sys.exit(1)
    backup = json.load(open(BACKUP))
    for handle, tags in backup["products"].items():
        p = fetch(handle)
        remove = [t for t in p["tags"] if t not in tags]
        if not remove:
            continue
        res = gql(M_TAGS_REMOVE, {"id": p["id"], "tags": remove})["tagsRemove"]
        if res["userErrors"]:
            print("❌", res["userErrors"])
            sys.exit(1)
        print(f"↩️ タグ除去 {remove}: {p['title'][:34]}")
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
    elif "--apply" in args:
        apply()
        print()
        show_status()
    else:
        show_status()
        print("（dry-run。反映するには --apply）")


if __name__ == "__main__":
    main()
