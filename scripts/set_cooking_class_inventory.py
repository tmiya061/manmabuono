#!/usr/bin/env python3
"""お料理教室（オンライン料理教室）の開催日バリアントに定員＝在庫を設定する

設計上「定員＝在庫」で持つ（→ .company/projects/clients/manmabuono/cooking_class_page.md）。
新しい開催日バリアントを追加すると在庫管理が OFF（tracked=false）のまま＝無制限購入可に
なることがあるため、このスクリプトで「在庫管理ON＋定員セット」をまとめて行う。

使い方:
  python3 scripts/set_cooking_class_inventory.py              # dry-run（現状表示のみ）
  python3 scripts/set_cooking_class_inventory.py --apply      # 全バリアントを DEFAULT_CAPACITY に
  python3 scripts/set_cooking_class_inventory.py --apply --capacity 20
  python3 scripts/set_cooking_class_inventory.py --revert     # backup.json の状態に戻す

必要スコープ: read_products / read_inventory / write_inventory
"""
import json
import os
import sys
import urllib.parse
import urllib.request
import uuid

API_VERSION = "2026-07"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCT_ID = "gid://shopify/Product/7947787436093"  # オンライン料理教室
BACKUP = os.path.join(ROOT, "scripts", "cooking_class", "inventory.backup.json")
DEFAULT_CAPACITY = 5
TOKEN = None


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


Q_FETCH = """
query($id: ID!) {
  product(id: $id) {
    id title
    variants(first: 50) {
      nodes {
        id title price inventoryQuantity inventoryPolicy
        inventoryItem {
          id tracked
          inventoryLevels(first: 5) {
            nodes { id location { id } quantities(names: ["available"]) { name quantity } }
          }
        }
      }
    }
  }
}
"""

M_TRACK = """
mutation($id: ID!, $tracked: Boolean!) {
  inventoryItemUpdate(id: $id, input: {tracked: $tracked}) {
    inventoryItem { id tracked }
    userErrors { field message }
  }
}
"""

M_SET = """
mutation($input: InventorySetQuantitiesInput!, $key: String!) {
  inventorySetQuantities(input: $input) @idempotent(key: $key) {
    inventoryAdjustmentGroup { reason changes { name delta quantityAfterChange } }
    userErrors { field message }
  }
}
"""


def fetch():
    return gql(Q_FETCH, {"id": PRODUCT_ID})["product"]


def show(p):
    print(f"商品: {p['title']}")
    for v in p["variants"]["nodes"]:
        ii = v["inventoryItem"]
        lv = ii["inventoryLevels"]["nodes"]
        avail = lv[0]["quantities"][0]["quantity"] if lv else "-"
        mark = "  " if ii["tracked"] else "⚠️"
        print(f"  {mark} {v['title']:28} ¥{v['price']:>6}  在庫管理={'ON ' if ii['tracked'] else 'OFF'}  available={avail}")


def _avail(v):
    """バリアントの現在の available 数量と location id を返す"""
    lv = v["inventoryItem"]["inventoryLevels"]["nodes"]
    if not lv:
        return None, None
    qty = next((q["quantity"] for q in lv[0]["quantities"] if q["name"] == "available"), 0)
    return qty, lv[0]["location"]["id"]


def apply(p, capacity):
    # 1) 在庫管理がOFFのものをONにする（ON化で現在値が変わり得るので数量設定は後段でまとめて行う）
    for v in p["variants"]["nodes"]:
        ii = v["inventoryItem"]
        if ii["tracked"]:
            continue
        r = gql(M_TRACK, {"id": ii["id"], "tracked": True})["inventoryItemUpdate"]
        if r["userErrors"]:
            print("  !! tracked更新エラー:", r["userErrors"])
            continue
        print(f"  ✓ 在庫管理をONに: {v['title']}")

    # 2) 最新の在庫数を取り直し、changeFromQuantity（照合値）を添えて数量をセットする
    for v in fetch()["variants"]["nodes"]:
        ii = v["inventoryItem"]
        cur, loc = _avail(v)
        if loc is None:
            print(f"  !! 在庫ロケーションが無い: {v['title']}")
            continue
        if cur == capacity:
            print(f"  - 変更不要（すでに{capacity}）: {v['title']}")
            continue
        r = gql(M_SET, {"input": {
            "name": "available",
            "reason": "correction",
            "quantities": [{
                "inventoryItemId": ii["id"], "locationId": loc,
                "quantity": capacity, "changeFromQuantity": cur,
            }],
        }, "key": str(uuid.uuid4())})["inventorySetQuantities"]
        if r["userErrors"]:
            print("  !! 数量更新エラー:", r["userErrors"])
            continue
        print(f"  ✓ 定員{capacity}に設定（{cur}→{capacity}）: {v['title']}")


def revert():
    with open(BACKUP) as f:
        b = json.load(f)
    cur_by_id = {v["inventoryItem"]["id"]: v for v in fetch()["variants"]["nodes"]}
    for v in b["variants"]["nodes"]:
        ii = v["inventoryItem"]
        want, loc = _avail(v)
        if loc is None:
            continue
        cur, _ = _avail(cur_by_id[ii["id"]])
        if cur != want:
            gql(M_SET, {"input": {
                "name": "available", "reason": "correction",
                "quantities": [{
                    "inventoryItemId": ii["id"], "locationId": loc,
                    "quantity": want, "changeFromQuantity": cur,
                }],
            }, "key": str(uuid.uuid4())})
        gql(M_TRACK, {"id": ii["id"], "tracked": ii["tracked"]})
        print(f"  ↩ 復元: {v['title']} → 在庫管理={'ON' if ii['tracked'] else 'OFF'} / available={want}")


if __name__ == "__main__":
    load_env()
    cap = DEFAULT_CAPACITY
    if "--capacity" in sys.argv:
        cap = int(sys.argv[sys.argv.index("--capacity") + 1])

    if "--revert" in sys.argv:
        print("=== 復元前 ===")
        show(fetch())
        print("\n=== backup.json へ復元 ===")
        revert()
        print("\n=== 復元後 ===")
        show(fetch())
        sys.exit(0)

    p = fetch()
    print("=== 現在の状態 ===")
    show(p)

    if "--apply" not in sys.argv:
        print(f"\n(dry-run) --apply を付けると全バリアントを「在庫管理ON・定員{cap}」に揃えます")
        sys.exit(0)

    print(f"\n=== 定員{cap}に統一 ===")
    apply(p, cap)
    print("\n=== 反映後 ===")
    show(fetch())
