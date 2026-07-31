#!/usr/bin/env python3
"""記事下CTA（おすすめ商品）を記事単位で設定するスクリプト

運用フロー:
  記事が完成したら、その記事に載せる商品（と任意の一言）を指定して実行する。
  メタオブジェクト（product_recommendation）のエントリーを記事専用に作り、
  記事メタフィールド custom.recommendations に紐付けるところまで自動で行う。

使い方:
  python3 scripts/set_article_cta.py <記事handle> "<商品handle>" "<商品handle>::<訴求文>" ...

例（訴求文なし2つ＋ありを1つ）:
  python3 scripts/set_article_cta.py neko-wetfood-tabenai \
    "無塩-鹿児島枕崎-おつお削り節" \
    "cat-trial-set::偏食の猫ちゃんの「食べるもの探し」がまとめてできます"

仕様:
  - 訴求文は「::」区切りで任意指定。なければ商品名と価格だけのカードになる
  - エントリーhandleは art<記事ID>-<連番>（記事専用。再実行で上書き）
  - 再実行すると丸ごと置き換わる（商品を減らした場合も余りは削除）
  - 商品を0個にしたい場合: python3 scripts/set_article_cta.py <記事handle> --clear
"""
import json
import os
import sys
import urllib.request
import urllib.parse

API_VERSION = "2026-07"
TOKEN = None


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


def find_article(handle):
    data = gql(
        """query($q: String!) { articles(first: 10, query: $q) {
             nodes { id title handle blog { title } } } }""",
        {"q": f"handle:{handle}"})
    nodes = [n for n in data["articles"]["nodes"] if n["handle"] == handle]
    if not nodes:
        # 見つからないときは最近の記事を出して終了
        recent = gql("""query { articles(first: 15, sortKey: UPDATED_AT, reverse: true) {
                          nodes { handle title blog { title } } } }""")["articles"]["nodes"]
        print(f"記事 handle '{handle}' が見つかりません。最近の記事:")
        for n in recent:
            print(f"  {n['handle']}\t{n['title']}（{n['blog']['title']}）")
        sys.exit(1)
    return nodes[0]


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    load_env()
    article_handle = sys.argv[1]
    article = find_article(article_handle)
    art_num = article["id"].rsplit("/", 1)[-1]
    prefix = f"art{art_num}-"
    print(f"記事: {article['title']}（{article['blog']['title']} / {article['handle']}）")

    clear = sys.argv[2] == "--clear"
    specs = [] if clear else sys.argv[2:]

    # 商品を解決してエントリーをupsert
    gids = []
    for i, spec in enumerate(specs, 1):
        if "::" in spec:
            product_handle, copy = spec.split("::", 1)
        else:
            product_handle, copy = spec, ""
        p = gql("""query($h: String!) { productByHandle(handle: $h) { id title } }""",
                {"h": product_handle})["productByHandle"]
        if not p:
            print(f"[エラー] 商品 handle '{product_handle}' が見つかりません。中断します（何も変更していません）")
            sys.exit(1)
        res = gql("""mutation($handle: MetaobjectHandleInput!, $metaobject: MetaobjectUpsertInput!) {
            metaobjectUpsert(handle: $handle, metaobject: $metaobject) {
              metaobject { id }
              userErrors { field message }
            } }""", {
            "handle": {"type": "product_recommendation", "handle": f"{prefix}{i}"},
            "metaobject": {"fields": [
                {"key": "product", "value": p["id"]},
                {"key": "copy", "value": copy},
            ]},
        })["metaobjectUpsert"]
        if res["userErrors"]:
            raise RuntimeError(res["userErrors"])
        gids.append(res["metaobject"]["id"])
        label = f" / 一言: {copy}" if copy else "（一言なし）"
        print(f"  [{i}] {p['title']}{label}")

    # 記事メタフィールドを更新
    res = gql("""mutation($metafields: [MetafieldsSetInput!]!) {
        metafieldsSet(metafields: $metafields) {
          metafields { id }
          userErrors { field message }
        } }""", {"metafields": [{
        "ownerId": article["id"], "namespace": "custom", "key": "recommendations",
        "type": "list.metaobject_reference", "value": json.dumps(gids),
    }]})["metafieldsSet"]
    if res["userErrors"]:
        raise RuntimeError(res["userErrors"])

    # この記事の余った旧エントリーを削除（商品数を減らした場合）
    stale = [n for n in gql("""query { metaobjects(type: "product_recommendation", first: 100) {
                 nodes { id handle } } }""")["metaobjects"]["nodes"]
             if n["handle"].startswith(prefix) and n["id"] not in gids]
    for n in stale:
        gql("""mutation($id: ID!) { metaobjectDelete(id: $id) { deletedId userErrors { message } } }""",
            {"id": n["id"]})
    if stale:
        print(f"  旧エントリー {len(stale)}件を削除")

    print(f"\n完了: 記事に商品{len(gids)}件を設定しました。")


if __name__ == "__main__":
    main()
