#!/usr/bin/env python3
"""お料理教室の商品（B案：1商品＋開催日バリアント）とページを作成する（Shopify Admin API）

商品設計（.company/projects/clients/manmabuono/cooking_class_page.md）:
  - 商品「オンライン料理教室」1件。開催日をバリアント（オプション名: 開催日）で持つ
  - 配送不要（requiresShipping=false）・在庫追跡ON（在庫数=定員、0=満席）
  - 検索に出さない（seo.hidden=1）。コレクションには入れない（ページからのみ購入）
  - ページ /pages/cooking-class に template_suffix=cooking-class を割り当て

使い方:
  python3 scripts/setup_cooking_class.py           # dry-run（何を作るか表示のみ）
  python3 scripts/setup_cooking_class.py --apply   # 作成
  python3 scripts/setup_cooking_class.py --revert  # created.json のIDを削除して元に戻す

復元手段:
  scripts/cooking_class/created.json に作成したID（商品・ページ）を保存する。
  --revert でそれらを削除する（作成前の状態＝何も無い状態に戻る）。
"""
import json
import os
import sys
import urllib.parse
import urllib.request

API_VERSION = "2026-07"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "scripts", "cooking_class")
CREATED_PATH = os.path.join(OUT_DIR, "created.json")
TOKEN = None

PRODUCT_TITLE = "オンライン料理教室"
PRODUCT_HANDLE = "online-cooking-class"
PRICE = "500"
# 開催日バリアント（仮の日程・西川さん確認後に差し替え）
SESSIONS = [
    {"name": "8月9日（日）10:00〜11:30", "qty": 8},
    {"name": "8月16日（日）10:00〜11:30", "qty": 8},
    {"name": "8月23日（日）10:00〜11:30", "qty": 0},  # 満席表示の確認用
]
PAGE_TITLE = "お料理教室"
PAGE_HANDLE = "cooking-class"
TEMPLATE_SUFFIX = "cooking-class"


def load_env():
    env_path = os.path.join(ROOT, ".env")
    if not os.path.exists(env_path):
        env_path = os.path.expanduser(
            "~/Documents/company/manmabuono/.env")
    with open(env_path) as f:
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


def user_errors(payload, key):
    errs = payload.get(key, {}).get("userErrors") or []
    if errs:
        print(f"!! {key} userErrors:", json.dumps(errs, ensure_ascii=False, indent=2))
        sys.exit(1)


def apply():
    created = {}

    # 既存チェック（二重作成防止）
    d = gql('query($h: String!) { productByHandle(handle: $h) { id } }', {"h": PRODUCT_HANDLE})
    if d["productByHandle"]:
        print(f"!! 商品 {PRODUCT_HANDLE} は既に存在します: {d['productByHandle']['id']}")
        sys.exit(1)

    # 1. 商品作成（オプション: 開催日）
    d = gql("""
      mutation($input: ProductCreateInput!) {
        productCreate(product: $input) {
          product { id handle options { id name optionValues { id name } } variants(first: 5) { nodes { id title } } }
          userErrors { field message }
        }
      }""", {"input": {
        "title": PRODUCT_TITLE,
        "handle": PRODUCT_HANDLE,
        "status": "ACTIVE",
        "descriptionHtml": "<p>わんちゃん・猫ちゃんの手作りごはんを学ぶオンライン料理教室です。お申し込みは専用ページからお願いします。</p>",
        "productOptions": [{
            "name": "開催日",
            "values": [{"name": s["name"]} for s in SESSIONS],
        }],
    }})
    user_errors(d, "productCreate")
    product = d["productCreate"]["product"]
    created["product_id"] = product["id"]
    print(f"商品作成: {product['id']} ({PRODUCT_HANDLE})")

    # 2. バリアント整備（価格・配送不要）
    #    ※在庫数（=定員）はスコープ（write_inventory/locations）が無いため設定不可。
    #      在庫追跡なし＝常に受付中で作る。定員を設ける時は管理画面かスコープ追加後に。
    d = gql("""
      query($id: ID!) {
        product(id: $id) { variants(first: 20) { nodes { id title } } }
      }""", {"id": product["id"]})
    variants = d["product"]["variants"]["nodes"]
    d = gql("""
      mutation($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
        productVariantsBulkUpdate(productId: $productId, variants: $variants) {
          productVariants { id title price inventoryItem { id requiresShipping } }
          userErrors { field message }
        }
      }""", {"productId": product["id"], "variants": [
        {
            "id": v["id"],
            "price": PRICE,
            "inventoryItem": {"tracked": False, "requiresShipping": False},
        } for v in variants
    ]})
    user_errors(d, "productVariantsBulkUpdate")
    updated = d["productVariantsBulkUpdate"]["productVariants"]
    for v in updated:
        print(f"  バリアント: {v['title']} ¥{v['price']} requiresShipping={v['inventoryItem']['requiresShipping']}")

    # 3. 検索非表示（seo.hidden=1）
    d = gql("""
      mutation($metafields: [MetafieldsSetInput!]!) {
        metafieldsSet(metafields: $metafields) {
          metafields { id }
          userErrors { field message }
        }
      }""", {"metafields": [{
        "ownerId": product["id"],
        "namespace": "seo",
        "key": "hidden",
        "type": "number_integer",
        "value": "1",
    }]})
    user_errors(d, "metafieldsSet")
    print("seo.hidden=1（検索・サイトマップ非表示）")

    # 4. Online Store チャネルへの公開状態を確認（publications スコープが無いため確認のみ）
    d = gql("""
      query($id: ID!) { product(id: $id) { publishedAt onlineStoreUrl } }
    """, {"id": product["id"]})
    p = d["product"]
    if p["publishedAt"]:
        print(f"Online Store 公開済み: publishedAt={p['publishedAt']} url={p['onlineStoreUrl']}")
    else:
        print("⚠️ Online Store チャネル未公開。管理画面の商品ページ「販売チャネル」で Online Store を追加してください")

    # 5. ページ作成
    d = gql("""
      mutation($page: PageCreateInput!) {
        pageCreate(page: $page) {
          page { id handle }
          userErrors { code field message }
        }
      }""", {"page": {
        "title": PAGE_TITLE,
        "handle": PAGE_HANDLE,
        "templateSuffix": TEMPLATE_SUFFIX,
        "isPublished": True,
    }})
    user_errors(d, "pageCreate")
    page = d["pageCreate"]["page"]
    created["page_id"] = page["id"]
    print(f"ページ作成: {page['id']} (/pages/{page['handle']} template={TEMPLATE_SUFFIX})")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(CREATED_PATH, "w") as f:
        json.dump(created, f, ensure_ascii=False, indent=2)
    print(f"作成IDを保存: {CREATED_PATH}")


def revert():
    with open(CREATED_PATH) as f:
        created = json.load(f)
    if created.get("page_id"):
        d = gql("""
          mutation($id: ID!) { pageDelete(id: $id) { deletedPageId userErrors { message } } }
        """, {"id": created["page_id"]})
        user_errors(d, "pageDelete")
        print(f"ページ削除: {created['page_id']}")
    if created.get("product_id"):
        d = gql("""
          mutation($input: ProductDeleteInput!) { productDelete(input: $input) { deletedProductId userErrors { message } } }
        """, {"input": {"id": created["product_id"]}})
        user_errors(d, "productDelete")
        print(f"商品削除: {created['product_id']}")


def main():
    load_env()
    if "--apply" in sys.argv:
        apply()
    elif "--revert" in sys.argv:
        revert()
    else:
        print("dry-run（--apply で作成 / --revert で削除）")
        print(f"商品: {PRODUCT_TITLE} ({PRODUCT_HANDLE}) ¥{PRICE} ACTIVE・検索非表示・コレクション無し")
        for s in SESSIONS:
            print(f"  バリアント: {s['name']} 在庫{s['qty']}")
        print(f"ページ: {PAGE_TITLE} (/pages/{PAGE_HANDLE}) template={TEMPLATE_SUFFIX} 公開（ナビからのリンク無し）")


if __name__ == "__main__":
    main()
