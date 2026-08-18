#!/usr/bin/env python3
"""商品handleの誤字「おつお削り節」→「かつお削り節」を修正する（301リダイレクト付き）

背景:
  商品名の誤字は 2026-08-02 に修正済みだが、handle（URL）は
  `無塩-鹿児島枕崎-おつお削り節` のまま据え置いていた
  （当時の判断＝URL変更はインデックス張り替えのリスクに対して利得が無い）。
  2026-08-18、SEO担当（垣谷さん）のレポートで改めて指摘されたためオーナー判断で修正する。
  302個売れている主力トッピングで、コラム1本目（犬 煮干し）の受け皿になる商品でもある。

  ProductInput.redirectNewHandle = true を渡すと、Shopifyが旧URL→新URLの
  301リダイレクトを自動生成する。これで評価を引き継ぐ。

事前に確認済み（2026-08-18）:
  - テーマのliquid・ナビゲーション・記事本文に旧handleの直リンクは無い
    （公開HTMLに出る旧handleはShopifyの計測JSがproduct.handleを自動出力しているだけ）
  - sections/c_product-recommend.liquid:135 が `item.handle contains '追加用'` で
    追加用商品を除外している → 新handleでも `-追加用` の接尾辞を必ず維持する
  - 記事下CTA（set_article_cta.py）は商品をGIDで保存するのでhandle変更の影響を受けない

使い方:
  python3 scripts/fix_product_handle_typo.py            # 点検のみ（書き込みなし）
  python3 scripts/fix_product_handle_typo.py --apply    # 本番のhandleを変更する

注意:
  --apply は本番の商品URLを変える。実行前にオーナー確認を取ること。
  実行すると変更前のhandleを scripts/seo_meta/product_handle_typo.backup.json に退避する。
  戻す場合は同じ手順で逆向きに変更する（そのとき再度 redirectNewHandle=true を付けること）。
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

API_VERSION = "2026-07"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP = os.path.join(ROOT, "scripts", "seo_meta", "product_handle_typo.backup.json")
TOKEN = None

# 旧handle -> 新handle
RENAMES = {
    "無塩-鹿児島枕崎-おつお削り節": "無塩-鹿児島枕崎-かつお削り節",
    "無塩-鹿児島枕崎-おつお削り節-追加用": "無塩-鹿児島枕崎-かつお削り節-追加用",
}


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


BY_HANDLE = """
query($h: String!) {
  productByHandle(handle: $h) { id handle title status }
}
"""

UPDATE = """
mutation($input: ProductInput!) {
  productUpdate(input: $input) {
    product { id handle title }
    userErrors { field message }
  }
}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="本番に書き込む（未指定なら点検のみ）")
    args = ap.parse_args()

    load_env()

    targets = []
    for old, new in RENAMES.items():
        p = gql(BY_HANDLE, {"h": old})["productByHandle"]
        if p is None:
            # すでに変更済みかどうかを確かめる
            q = gql(BY_HANDLE, {"h": new})["productByHandle"]
            if q:
                print(f"スキップ {old} → すでに {new} になっています")
                continue
            sys.exit(f"商品が見つかりません: {old}")
        if "追加用" in old and "追加用" not in new:
            sys.exit(f"新handleから『追加用』が落ちています（c_product-recommend の除外が壊れます）: {new}")
        targets.append((p, new))

    if not targets:
        print("変更対象なし")
        return

    print("変更内容:")
    for p, new in targets:
        print(f"  「{p['title']}」 [{p['status']}]")
        print(f"    旧 /products/{p['handle']}")
        print(f"    新 /products/{new}")
        print(f"    旧URLからの301リダイレクトをShopifyが自動生成します（redirectNewHandle=true）")
        print()

    if not args.apply:
        print("点検のみ（--apply で本番反映）")
        return

    os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
    saved = json.load(open(BACKUP)) if os.path.exists(BACKUP) else {}
    for p, new in targets:
        saved[new] = {"id": p["id"], "old_handle": p["handle"], "title": p["title"]}
    with open(BACKUP, "w") as f:
        json.dump(saved, f, ensure_ascii=False, indent=2)
    print(f"変更前を退避: {BACKUP}\n")

    for p, new in targets:
        d = gql(UPDATE, {"input": {
            "id": p["id"],
            "handle": new,
            "redirectNewHandle": True,
        }})["productUpdate"]
        if d["userErrors"]:
            print(f"NG {p['handle']}: {d['userErrors']}")
        else:
            print(f"OK {p['handle']} → {d['product']['handle']}")


if __name__ == "__main__":
    main()
