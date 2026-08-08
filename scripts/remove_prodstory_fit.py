#!/usr/bin/env python3
"""商品説明文から「こんな子におすすめ」ブロック（c_prodStory__fit）を削除するスクリプト

対象: descriptionHtml に <div class="c_prodStory__fit"> を含む全商品。

使い方:
  python3 scripts/remove_prodstory_fit.py            # dry-run（変更内容の確認のみ）
  python3 scripts/remove_prodstory_fit.py --apply    # バックアップを保存してから本番反映

バックアップ: scripts/product_story/fit_removal_backup.json（変更前の descriptionHtml 全文）
復元: このバックアップの descriptionHtml を productUpdate で書き戻す
"""
import json
import os
import re
import sys
import urllib.request
import urllib.parse

API_VERSION = "2026-07"
TOKEN = None
BACKUP_PATH = os.path.join(os.path.dirname(__file__), "product_story", "fit_removal_backup.json")


def load_env():
    path = os.path.join(os.path.dirname(__file__), "..", ".env")
    with open(path) as f:
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
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        f"https://{domain}/admin/api/{API_VERSION}/graphql.json", data=body,
        headers={"Content-Type": "application/json", "X-Shopify-Access-Token": TOKEN})
    with urllib.request.urlopen(req) as r:
        res = json.load(r)
    if res.get("errors"):
        raise RuntimeError(json.dumps(res["errors"], ensure_ascii=False))
    return res["data"]


def remove_fit_block(html):
    """c_prodStory__fit の div を1個取り除く。入れ子divがあれば安全のため中断。"""
    marker = '<div class="c_prodStory__fit">'
    start = html.find(marker)
    if start < 0:
        return None
    end = html.find("</div>", start)
    inner = html[start + len(marker):end]
    if "<div" in inner:
        raise RuntimeError("fitブロック内に入れ子のdivがあり、単純削除できません")
    removed = html[:start] + html[end + len("</div>"):]
    # 削除跡の連続空行を1つに詰める
    removed = re.sub(r"\n\s*\n", "\n", removed, count=1)
    return removed


def main():
    apply = "--apply" in sys.argv
    load_env()

    products = []
    cursor = None
    while True:
        data = gql("""query($cursor: String) {
            products(first: 100, after: $cursor) {
              nodes { id handle title descriptionHtml }
              pageInfo { hasNextPage endCursor }
            } }""", {"cursor": cursor})["products"]
        products.extend(data["nodes"])
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]

    targets = [p for p in products if '<div class="c_prodStory__fit">' in (p["descriptionHtml"] or "")]
    print(f"全{len(products)}商品中、対象 {len(targets)} 商品\n")

    changes = []
    for p in targets:
        new_html = remove_fit_block(p["descriptionHtml"])
        count_after = new_html.count('c_prodStory__fit')
        if count_after:
            raise RuntimeError(f"{p['handle']}: fitブロックが複数あります（要個別確認）")
        changes.append((p, new_html))
        delta = len(p["descriptionHtml"]) - len(new_html)
        print(f"  {p['title']}（{p['handle']}） -{delta}文字")

    if not apply:
        print("\n[dry-run] 反映するには --apply を付けて実行してください")
        return

    os.makedirs(os.path.dirname(BACKUP_PATH), exist_ok=True)
    with open(BACKUP_PATH, "w") as f:
        json.dump([{"id": p["id"], "handle": p["handle"], "title": p["title"],
                    "descriptionHtml": p["descriptionHtml"]} for p, _ in changes],
                  f, ensure_ascii=False, indent=2)
    print(f"\nバックアップ保存: {BACKUP_PATH}")

    for p, new_html in changes:
        res = gql("""mutation($product: ProductUpdateInput!) {
            productUpdate(product: $product) {
              product { id }
              userErrors { field message }
            } }""", {"product": {"id": p["id"], "descriptionHtml": new_html}})
        errs = res["productUpdate"]["userErrors"]
        if errs:
            raise RuntimeError(f"{p['handle']}: {errs}")
        print(f"  更新済み: {p['handle']}")

    print(f"\n完了: {len(changes)} 商品から削除しました")


if __name__ == "__main__":
    main()
