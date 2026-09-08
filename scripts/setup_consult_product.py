#!/usr/bin/env python3
"""「管理栄養士に犬と猫のフードに関するご相談」（¥500）の商品を作成する（Shopify Admin API）

設計（.company/projects/clients/manmabuono/consult_product.md）:
  - 商品1件・バリアント1件（¥500）。配送不要（requiresShipping=false）・在庫追跡なし
  - タグ無し・コレクション所属なし（犬用/猫用の一覧に混ざらない）
  - 導線（グローバルメニュー・トップ）が公開されるまでは seo.hidden=1 で検索・サイトマップ非表示
  - 購入後の日程案内は西川さんがメールで送る（当面）。増えたら Spir 等の日程調整URLに切り替え

使い方:
  python3 scripts/setup_consult_product.py            # dry-run（何を作るか表示のみ）
  python3 scripts/setup_consult_product.py --apply    # 作成
  python3 scripts/setup_consult_product.py --revert   # created.json のIDを削除して元に戻す
  python3 scripts/setup_consult_product.py --unhide   # 導線公開時：seo.hidden を外す

復元手段:
  scripts/consult/created.json に作成した商品IDを保存する。--revert で削除する。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shopifyql as s  # load_env / gql（client credentials）

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "scripts", "consult")
CREATED_PATH = os.path.join(OUT_DIR, "created.json")

PRODUCT_TITLE = "管理栄養士に犬と猫のフードに関するご相談"
PRODUCT_HANDLE = "food-consultation"
PRODUCT_TYPE = "サービス"
PRICE = "500"

DESCRIPTION_HTML = """
<p>マンマボーノのごはんを設計している「ペットの管理栄養士」西川に、犬・猫のフードのことを直接ご相談いただけるサービスです。ご相談の内容をお伺いし、その子に合わせて回答いたします。</p>

<h2>こんなご相談に</h2>
<ul>
<li>うちの子に合うフードの選び方（年齢・体格・体質に合わせて）</li>
<li>今のフードからの切り替え方、量の目安</li>
<li>食べムラ・食いつき、水分をもっととらせたいとき</li>
<li>体重管理、シニア期のごはん</li>
<li>手作りごはんやトッピングの取り入れ方</li>
</ul>

<h2>ご相談の流れ</h2>
<ol>
<li>このページからお申し込みください（500円）。</li>
<li>ご購入後、西川からご登録のメールアドレスへ、ご相談の日時のご案内をお送りします。</li>
<li>ご案内のメールに返信する形で、ご相談の内容とご希望の日時をお知らせください。</li>
<li>日時が決まりましたら、メールまたはオンラインでご相談をお受けし、回答いたします。</li>
</ol>

<h2>ご注意</h2>
<ul>
<li>ご相談は食事・栄養に関するアドバイスです。病気の診断や治療は行いません。体調にご不安がある場合は、かかりつけの獣医師にご相談ください。</li>
<li>お届けする商品はありません。ご購入後のご案内はメールでお送りしますので、受信設定をご確認ください。</li>
<li>ご購入後のキャンセル・返金はお受けしておりません。</li>
</ul>
""".strip()


def apply():
    d = s.gql('query($h: String!) { productByHandle(handle: $h) { id } }', {"h": PRODUCT_HANDLE})
    if d["productByHandle"]:
        print(f"!! 商品 {PRODUCT_HANDLE} は既に存在します: {d['productByHandle']['id']}")
        sys.exit(1)

    d = s.gql("""
      mutation($input: ProductCreateInput!) {
        productCreate(product: $input) {
          product { id handle status variants(first: 5) { nodes { id title } } }
          userErrors { field message }
        }
      }""", {"input": {
        "title": PRODUCT_TITLE,
        "handle": PRODUCT_HANDLE,
        "status": "ACTIVE",
        "productType": PRODUCT_TYPE,
        "descriptionHtml": DESCRIPTION_HTML,
    }})
    errs = d["productCreate"]["userErrors"]
    if errs:
        print("!! productCreate userErrors:", json.dumps(errs, ensure_ascii=False, indent=2))
        sys.exit(1)
    product = d["productCreate"]["product"]
    print(f"商品作成: {product['id']} ({PRODUCT_HANDLE}) status={product['status']}")

    variants = product["variants"]["nodes"]
    d = s.gql("""
      mutation($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
        productVariantsBulkUpdate(productId: $productId, variants: $variants) {
          productVariants { id title price inventoryItem { id tracked requiresShipping } }
          userErrors { field message }
        }
      }""", {"productId": product["id"], "variants": [
        {"id": v["id"], "price": PRICE,
         "inventoryItem": {"tracked": False, "requiresShipping": False}}
        for v in variants
    ]})
    errs = d["productVariantsBulkUpdate"]["userErrors"]
    if errs:
        print("!! productVariantsBulkUpdate userErrors:", json.dumps(errs, ensure_ascii=False, indent=2))
        sys.exit(1)
    for v in d["productVariantsBulkUpdate"]["productVariants"]:
        ii = v["inventoryItem"]
        print(f"  バリアント: {v['title']} ¥{v['price']} tracked={ii['tracked']} requiresShipping={ii['requiresShipping']}")

    set_hidden(product["id"], "1")

    d = s.gql('query($id: ID!) { product(id: $id) { publishedAt onlineStoreUrl } }', {"id": product["id"]})
    p = d["product"]
    if p["publishedAt"]:
        print(f"Online Store 公開済み: {p['onlineStoreUrl']}")
    else:
        print("⚠️ Online Store チャネル未公開（publications スコープ無し）。REST で published=true を試みます")
        publish_rest(product["id"])

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(CREATED_PATH, "w") as f:
        json.dump({"product_id": product["id"], "handle": PRODUCT_HANDLE}, f, ensure_ascii=False, indent=2)
    print(f"作成IDを保存: {CREATED_PATH}")


def set_hidden(product_id, value):
    d = s.gql("""
      mutation($metafields: [MetafieldsSetInput!]!) {
        metafieldsSet(metafields: $metafields) { metafields { id } userErrors { field message } }
      }""", {"metafields": [{
        "ownerId": product_id, "namespace": "seo", "key": "hidden",
        "type": "number_integer", "value": value,
    }]})
    errs = d["metafieldsSet"]["userErrors"]
    if errs:
        print("!! metafieldsSet userErrors:", json.dumps(errs, ensure_ascii=False, indent=2))
        sys.exit(1)
    print(f"seo.hidden={value}")


def publish_rest(product_gid):
    import urllib.request
    numeric = product_gid.rsplit("/", 1)[-1]
    domain = os.environ["SHOPIFY_STORE_DOMAIN"]
    if s.TOKEN is None:
        s.TOKEN = s.get_token()
    body = json.dumps({"product": {"id": int(numeric), "published": True}}).encode()
    req = urllib.request.Request(
        f"https://{domain}/admin/api/2024-01/products/{numeric}.json", data=body, method="PUT",
        headers={"Content-Type": "application/json", "X-Shopify-Access-Token": s.TOKEN})
    with urllib.request.urlopen(req) as r:
        out = json.load(r)
    print(f"REST published={out['product'].get('published_at')}")
    d = s.gql('query($id: ID!) { product(id: $id) { publishedAt onlineStoreUrl } }', {"id": product_gid})
    print(f"再確認: publishedAt={d['product']['publishedAt']} url={d['product']['onlineStoreUrl']}")


def revert():
    with open(CREATED_PATH) as f:
        created = json.load(f)
    d = s.gql("""
      mutation($input: ProductDeleteInput!) { productDelete(input: $input) { deletedProductId userErrors { message } } }
    """, {"input": {"id": created["product_id"]}})
    errs = d["productDelete"]["userErrors"]
    if errs:
        print("!! productDelete userErrors:", json.dumps(errs, ensure_ascii=False, indent=2))
        sys.exit(1)
    print(f"商品削除: {created['product_id']}")


def unhide():
    with open(CREATED_PATH) as f:
        created = json.load(f)
    d = s.gql("""
      query($id: ID!) { product(id: $id) { metafield(namespace: "seo", key: "hidden") { id } } }
    """, {"id": created["product_id"]})
    mf = d["product"]["metafield"]
    if not mf:
        print("seo.hidden は未設定（何もしない）")
        return
    d = s.gql("""
      mutation($metafields: [MetafieldIdentifierInput!]!) {
        metafieldsDelete(metafields: $metafields) { deletedMetafields { key } userErrors { message } }
      }""", {"metafields": [{"ownerId": created["product_id"], "namespace": "seo", "key": "hidden"}]})
    errs = d["metafieldsDelete"]["userErrors"]
    if errs:
        print("!! metafieldsDelete userErrors:", json.dumps(errs, ensure_ascii=False, indent=2))
        sys.exit(1)
    print("seo.hidden を削除（検索・サイトマップに出る）")


def main():
    s.load_env()
    if "--apply" in sys.argv:
        apply()
    elif "--revert" in sys.argv:
        revert()
    elif "--unhide" in sys.argv:
        unhide()
    else:
        print("dry-run（--apply で作成 / --revert で削除 / --unhide で検索非表示を解除）")
        print(f"商品: {PRODUCT_TITLE} ({PRODUCT_HANDLE}) ¥{PRICE} ACTIVE・配送不要・在庫追跡なし・タグ無し・seo.hidden=1")


if __name__ == "__main__":
    main()
