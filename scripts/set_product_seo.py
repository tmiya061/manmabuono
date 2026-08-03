#!/usr/bin/env python3
"""商品の SEOタイトル / メタディスクリプション を設定する

背景:
  2026-08-02 時点、全71商品で seo.title / seo.description が未設定だった。
  未設定だと Shopify が商品説明の冒頭を機械的に切り出して <meta name="description"> に流し込むため、
  検索結果のスニペットが原材料の羅列や本文の誤字のまま出ていた。
  → 原稿は scripts/seo_meta/product_seo.json

使い方:
  python3 scripts/set_product_seo.py            # 点検のみ（書き込みなし・文字数と差分を表示）
  python3 scripts/set_product_seo.py --apply    # 本番の商品SEOフィールドを更新する
  python3 scripts/set_product_seo.py --apply --only dog-trial-set   # handle指定で部分適用

注意:
  --apply は本番の商品ページの検索結果表示を書き換える。実行前に必ず西川さん確認を取ること。
  実行すると変更前の seo フィールドを scripts/seo_meta/product_seo.backup.json に退避する。

タイトルの前提:
  layout/theme.liquid が `｜{{ shop.name }}`（＝｜MANMABUONO KYOTO JAPAN）を自動で付けるため、
  JSON の title にブランド名は含めない。SERP幅の見積もりはこの接尾辞込みで計算する。
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
SRC = os.path.join(ROOT, "scripts", "seo_meta", "product_seo.json")
BACKUP = os.path.join(ROOT, "scripts", "seo_meta", "product_seo.backup.json")
TITLE_SUFFIX = "｜MANMABUONO KYOTO JAPAN"
# GoogleのSERPタイトルは概ね600px。全角=2単位/半角=1単位として約62単位が表示上限の目安。
# ブランド接尾辞（24単位）は必ず末尾で省略される前提とし、商品を識別する部分だけで枠に収める。
TITLE_BUDGET = 58
DESC_MIN, DESC_MAX = 90, 125  # 全角換算の目安（日本語スニペットは全角120字前後で切られる）
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
  products(first: 100, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes { id handle title status seo { title description } }
  }
}
"""

UPDATE = """
mutation($input: ProductInput!) {
  productUpdate(input: $input) {
    product { id handle seo { title description } }
    userErrors { field message }
  }
}
"""


def fetch_all():
    items, cursor = [], None
    while True:
        p = gql(FETCH, {"cursor": cursor})["products"]
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

    plan = json.load(open(SRC))["products"]
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
        p = live[h]
        tw = width(v["title"])
        dw = width(v["description"]) / 2  # 全角換算の字数
        flags = []
        if tw > TITLE_BUDGET:
            flags.append(f"title超過 {tw}/{TITLE_BUDGET}単位（商品名の末尾まで表示されない恐れ）")
        if not (DESC_MIN <= dw <= DESC_MAX):
            flags.append(f"desc {dw:.0f}字（目安{DESC_MIN}-{DESC_MAX}）")
        if p["status"] != "ACTIVE":
            flags.append(f"status={p['status']}")
        warn += len(flags)
        cur = p["seo"] or {}
        targets.append((h, v, flags, bool(cur.get("title") or cur.get("description"))))

    print(f"原稿 {len(plan)} 件 / Shopify照合OK")
    print(f"※ 末尾の『{TITLE_SUFFIX}』はテーマが自動付与。SERPでは省略される前提で設計している\n")
    for h, v, flags, had in targets:
        mark = "!" if flags else " "
        print(f"{mark} {h}")
        print(f"    T({width(v['title'])}) {v['title']}{TITLE_SUFFIX}")
        print(f"    D({width(v['description'])//2}) {v['description']}")
        if had:
            print("    ※ 既存のSEO設定を上書きします")
        for f in flags:
            print(f"    ⚠ {f}")
        print()
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
        }})["productUpdate"]
        if d["userErrors"]:
            print(f"NG {h}: {d['userErrors']}")
        else:
            ok += 1
            print(f"OK {h}")
    print(f"\n{ok}/{len(targets)} 件を更新しました")


if __name__ == "__main__":
    main()
