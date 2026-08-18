#!/usr/bin/env python3
"""コレクションの SEOタイトル / メタディスクリプション を設定する

背景:
  2026-08-18 時点、全28コレクションで seo.title / seo.description が未設定だった。
  さらに collection.description（本文説明）も全件空で、コレクションページの
  banner セクションは templates/collection*.json で disabled になっている。
  結果、layout/theme.liquid の page_description が空になり
  <meta name="description"> タグ自体が1件も出力されていなかった。
  → 原稿は scripts/seo_meta/collection_seo.json

  商品側（scripts/set_product_seo.py・2026-08-02 実施）のコレクション版。設計方針は同じ。

使い方:
  python3 scripts/set_collection_seo.py            # 点検のみ（書き込みなし・文字数と差分を表示）
  python3 scripts/set_collection_seo.py --apply    # 本番のコレクションSEOフィールドを更新する
  python3 scripts/set_collection_seo.py --apply --only dog-dry   # handle指定で部分適用

注意:
  --apply は本番の検索結果表示（title/スニペット）を書き換える。ページ上の見た目は変わらない。
  実行すると変更前の seo フィールドを scripts/seo_meta/collection_seo.backup.json に退避する。

原稿から除外しているコレクション:
  senmon    … 既存のお客様専用の購入ページ。検索に出す性質のものではない（noindex検討）
  c-osechi  … 商品0件
"""
import argparse
import json
import os
import sys
import unicodedata
import urllib.parse
import urllib.request

API_VERSION = "2026-07"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "scripts", "seo_meta", "collection_seo.json")
BACKUP = os.path.join(ROOT, "scripts", "seo_meta", "collection_seo.backup.json")
TITLE_SUFFIX = "｜MANMABUONO KYOTO JAPAN"
TITLE_BUDGET = 58  # 全角=2 / 半角=1。ブランド接尾辞（24単位）は末尾で省略される前提
DESC_MIN, DESC_MAX = 90, 125  # 全角換算の字数
TOKEN = None


def width(s):
    """全角=2 / 半角=1 の単位で文字列幅を返す"""
    return sum(2 if unicodedata.east_asian_width(c) in "WFA" else 1 for c in s)


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


FETCH = """
query($cursor: String) {
  collections(first: 100, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes { id handle title productsCount { count } seo { title description } }
  }
}
"""

UPDATE = """
mutation($input: CollectionInput!) {
  collectionUpdate(input: $input) {
    collection { id handle seo { title description } }
    userErrors { field message }
  }
}
"""


def fetch_all():
    items, cursor = [], None
    while True:
        p = gql(FETCH, {"cursor": cursor})["collections"]
        items += p["nodes"]
        if not p["pageInfo"]["hasNextPage"]:
            break
        cursor = p["pageInfo"]["endCursor"]
    return {x["handle"]: x for x in items}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="本番に書き込む（未指定なら点検のみ）")
    ap.add_argument("--only", help="handle を指定して部分適用")
    args = ap.parse_args()

    plan = json.load(open(SRC))["collections"]
    if args.only:
        if args.only not in plan:
            sys.exit(f"handle が原稿に見つかりません: {args.only}")
        plan = {args.only: plan[args.only]}

    load_env()
    live = fetch_all()

    missing = [h for h in plan if h not in live]
    if missing:
        sys.exit("Shopifyに存在しない handle: " + ", ".join(missing))

    targets, warn = [], 0
    for h, v in plan.items():
        c = live[h]
        tw = width(v["title"])
        dw = width(v["description"]) / 2  # 全角換算の字数
        flags = []
        if tw > TITLE_BUDGET:
            flags.append(f"title超過 {tw}/{TITLE_BUDGET}単位（末尾まで表示されない恐れ）")
        if not (DESC_MIN <= dw <= DESC_MAX):
            flags.append(f"desc {dw:.0f}字（目安{DESC_MIN}-{DESC_MAX}）")
        if c["productsCount"]["count"] == 0:
            flags.append("商品0件")
        warn += len(flags)
        cur = c["seo"] or {}
        targets.append((h, v, flags, bool(cur.get("title") or cur.get("description"))))

    unplanned = [h for h in live if h not in plan] if not args.only else []

    print(f"原稿 {len(plan)} 件 / Shopify照合OK（全 {len(live)} コレクション）")
    print(f"※ 末尾の『{TITLE_SUFFIX}』はテーマが自動付与。SERPでは省略される前提で設計している\n")
    for h, v, flags, had in targets:
        mark = "!" if flags else " "
        print(f"{mark} {h}  「{live[h]['title']}」 商品{live[h]['productsCount']['count']}件")
        print(f"    T({width(v['title'])}) {v['title']}{TITLE_SUFFIX}")
        print(f"    D({width(v['description'])//2}) {v['description']}")
        if had:
            print("    ※ 既存のSEO設定を上書きします")
        for f in flags:
            print(f"    ⚠ {f}")
        print()
    if unplanned:
        print("原稿に無いコレクション（意図的に除外）: " + ", ".join(unplanned) + "\n")
    print(f"警告 {warn} 件")

    if not args.apply:
        print("\n点検のみ（--apply で本番反映）")
        return

    # 退避は「最初に触ったときの状態」を正とする。--only で部分適用しても
    # 既存の退避内容を消さない（上書きすると全件復元できなくなる）。
    os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
    saved = json.load(open(BACKUP)) if os.path.exists(BACKUP) else {}
    added = [h for h in plan if h not in saved]
    for h in added:
        saved[h] = live[h]["seo"] or {}
    with open(BACKUP, "w") as f:
        json.dump(saved, f, ensure_ascii=False, indent=2)
    print(f"\n変更前を退避: {BACKUP}（今回 {len(added)} 件追加 / 累計 {len(saved)} 件）")

    ok = 0
    for h, v, _, _ in targets:
        d = gql(UPDATE, {"input": {
            "id": live[h]["id"],
            "seo": {"title": v["title"], "description": v["description"]},
        }})["collectionUpdate"]
        if d["userErrors"]:
            print(f"NG {h}: {d['userErrors']}")
        else:
            ok += 1
            print(f"OK {h}")
    print(f"\n{ok}/{len(targets)} 件を更新しました")


if __name__ == "__main__":
    main()
