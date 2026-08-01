#!/usr/bin/env python3
"""［追加用］商品の価格が「通常版 × 0.9」になっているか点検する（必要なら修正する）

背景:
  三河屋サブスクは「追加」操作で割引が引き継がれない仕様のため、
  マイページ追加購入用に「10%引きの価格を直接設定した非公開商品」を用意している。
  通常版の価格を変えたら追加用も手で変える必要があり、忘れると会員が定価を払う。
  → 詳細は docs/subscription-mikawaya.md

使い方:
  python3 scripts/check_addon_prices.py           # 点検のみ（書き込みなし）
  python3 scripts/check_addon_prices.py --fix     # 逸脱を 通常版×0.9 に修正する
  python3 scripts/check_addon_prices.py --fix --only "プレミアム料理"   # 部分一致で対象を絞る

判定:
  ［追加用］商品のタイトルから「［追加用］」を除いた文字列で通常版と対応付け、
  追加用価格 == round(通常版価格 * 0.9) かを見る。1円でもズレたら逸脱として報告。

注意:
  --fix は本番の商品価格を書き換える。実行前に必ずオーナー確認を取ること。
  実行すると変更前の価格を scripts/collection_order/addon_prices.backup.json に退避する。
"""
import json
import os
import sys
import urllib.parse
import urllib.request

API_VERSION = "2026-07"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP = os.path.join(ROOT, "scripts", "collection_order", "addon_prices.backup.json")
RATE = 0.9  # 定期購入グループの割引率 10% OFF に対応
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


def strip_addon(title):
    return title.replace("［追加用］", "").replace("[追加用]", "").strip()


def fetch_all():
    q = """
    query($cursor: String) {
      products(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id handle title status
          variants(first: 1) { nodes { id price } }
        }
      }
    }
    """
    items, cursor = [], None
    while True:
        p = gql(q, {"cursor": cursor})["products"]
        items += p["nodes"]
        if not p["pageInfo"]["hasNextPage"]:
            break
        cursor = p["pageInfo"]["endCursor"]
    return items


def main():
    load_env()
    fix = "--fix" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]

    items = fetch_all()
    base = {strip_addon(p["title"]): p for p in items if "追加用" not in p["title"]}

    rows, orphans = [], []
    for p in items:
        if "追加用" not in p["title"]:
            continue
        if only and only not in p["title"]:
            continue
        key = strip_addon(p["title"])
        b = base.get(key)
        if b is None:
            orphans.append(p)
            continue
        v, bv = p["variants"]["nodes"][0], b["variants"]["nodes"][0]
        cur = float(v["price"])
        want = round(float(bv["price"]) * RATE)
        rows.append({"key": key, "variant_id": v["id"], "handle": p["handle"],
                     "base": float(bv["price"]), "current": cur, "want": float(want),
                     "ok": abs(cur - want) < 0.5})

    ok = [r for r in rows if r["ok"]]
    bad = [r for r in rows if not r["ok"]]
    print(f"［追加用］{len(rows)}件を点検（基準＝通常版 × {RATE}）\n")
    print(f"  ✅ 正しい: {len(ok)}件")
    print(f"  🔴 逸脱  : {len(bad)}件")
    if orphans:
        print(f"  ⚠️ 通常版が見つからない追加用: {len(orphans)}件")
        for p in orphans:
            print(f'      {p["title"]}')
    print()
    if not bad:
        print("逸脱はありません。")
        return
    print(f'{"商品":<38}{"通常版":>8}{"現在":>8}{"あるべき":>9}{"差":>8}')
    print("-" * 72)
    for r in bad:
        print(f'{r["key"][:36]:<38}{r["base"]:>8.0f}{r["current"]:>8.0f}{r["want"]:>9.0f}{r["want"]-r["current"]:>+8.0f}')

    if not fix:
        print("\n[点検のみ] 書き込みはしていません。--fix で修正します。")
        return

    with open(BACKUP, "w") as f:  # 変更前を退避
        json.dump({"note": "check_addon_prices.py --fix の実行前価格",
                   "items": [{"variant_id": r["variant_id"], "title": r["key"],
                              "price_before": r["current"]} for r in bad]},
                  f, ensure_ascii=False, indent=2)
    print(f"\n変更前の価格を退避: {BACKUP}")

    m = """
    mutation($id: ID!, $price: Money!) {
      productVariantsBulkUpdate(productId: $id, variants: [{id: $id2, price: $price}]) {
        userErrors { field message }
      }
    }
    """
    # productVariantsBulkUpdate は productId が要るので、variant から product を引き直す
    print(f"本番の価格を修正します（{len(bad)}件）…")
    for r in bad:
        pid = gql('query($id: ID!) { productVariant(id: $id) { product { id } } }',
                  {"id": r["variant_id"]})["productVariant"]["product"]["id"]
        res = gql("""
        mutation($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
          productVariantsBulkUpdate(productId: $productId, variants: $variants) {
            productVariants { id price }
            userErrors { field message }
          }
        }""", {"productId": pid,
               "variants": [{"id": r["variant_id"], "price": f'{r["want"]:.0f}'}]})
        d = res["productVariantsBulkUpdate"]
        if d["userErrors"]:
            print(f'  ❌ {r["key"]}: {d["userErrors"]}')
        else:
            got = d["productVariants"][0]["price"]
            print(f'  ✅ {r["key"][:36]:<38} ¥{r["current"]:.0f} → ¥{got}')

    print("\n検証のため再点検します…")
    TOKEN_KEEP = None
    items = fetch_all()
    base = {strip_addon(p["title"]): p for p in items if "追加用" not in p["title"]}
    still = []
    for r in bad:
        p = next((x for x in items if x["variants"]["nodes"][0]["id"] == r["variant_id"]), None)
        b = base.get(r["key"])
        if p and b:
            cur = float(p["variants"]["nodes"][0]["price"])
            want = round(float(b["variants"]["nodes"][0]["price"]) * RATE)
            if abs(cur - want) >= 0.5:
                still.append((r["key"], cur, want))
    if still:
        print("⚠️ まだ逸脱が残っています:")
        for k, c, w in still:
            print(f"   {k}: ¥{c:.0f}（あるべき ¥{w:.0f}）")
    else:
        print("✅ 検証OK：全件が 通常版 × 0.9 に揃いました")
        print("   → docs/admin-changelog.md への追記を忘れずに")


main()
