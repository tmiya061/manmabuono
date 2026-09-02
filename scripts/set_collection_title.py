#!/usr/bin/env python3
"""主要コレクション10本の名前（title）を「犬用 - ドライフード」型から「犬用のドライフード」型へ改名する

背景:
  コレクションページの h1 は sections/c_collectionCategory.liquid で
  `collection.title | split: '-' | last` としており、「犬用 - ドライフード」の後半だけを出していた。
  2026-09-02 西川さんから「文言を揃えた」形で h1 の指定が届いた（下記 PLAN の新名称）。
  「'-' で切る処理をやめる／コレクション名そのものを変える、どちらでも可」との回答だったので、
  名前そのものを指定の文言にして h1 はそのまま出す方式を採った（テーマ側の分岐を増やさない）。
  ナビ（ヘッダー／フッター／一覧チップ）は犬用・猫用の見出しの下に並ぶため、
  snippets/c_category-links.liquid で接頭辞「犬用の／猫用の」を落として短い語を出す。

  SEO タイトルは seo.title に別途設定済み（scripts/set_collection_seo.py）で、
  <title> には collection.title を使っていないため、検索結果の見え方は変わらない。

使い方:
  python3 scripts/set_collection_title.py            # 点検のみ（書き込みなし・現在値と新名称を表示）
  python3 scripts/set_collection_title.py --apply    # 本番のコレクション名を更新する
  python3 scripts/set_collection_title.py --revert   # 退避した変更前の名前に戻す

注意:
  --apply は店頭の h1・パンくず・検索候補に出るコレクション名を書き換える（見た目が変わる）。
  実行すると変更前の title を scripts/seo_meta/collection_title.backup.json に退避する。
  handle は変えない（URL 不変・リダイレクト不要）。
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

API_VERSION = "2026-07"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP = os.path.join(ROOT, "scripts", "seo_meta", "collection_title.backup.json")
TOKEN = None

# handle -> (想定している現在の名前, 新しい名前)  ※現在値が想定と違えば止める
PLAN = {
    "dog-all":    ("犬用ごはん - 全ての商品",      "犬用の全ての商品"),
    "cat-all":    ("猫用ごはん - 全ての商品",      "猫用の全ての商品"),
    "dog-dry":    ("犬用 - ドライフード",          "犬用のドライフード"),
    "cat-dry":    ("猫用 - ドライフード",          "猫用のドライフード"),
    "dog-wet":    ("犬用 - ウェットフード",        "犬用のウェットフード"),
    "cat-wet":    ("猫用 - ウェットフード",        "猫用のウェットフード"),
    "dog-make-6": ("犬用 - 自分で作る手作りごはん", "犬用 自分で作る手作りごはん"),
    "cat-make":   ("猫用 - 自分で作る手作りごはん", "猫用 自分で作る手作りごはん"),
    "dog-easy-cook-5": ("犬用 - おやつ",          "犬用のおやつ"),
    "cat-easy-cook":   ("猫用 - おやつ",          "猫用のおやつ"),
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
  collectionByHandle(handle: $h) { id handle title seo { title } }
}
"""

UPDATE = """
mutation($input: CollectionInput!) {
  collectionUpdate(input: $input) {
    collection { id handle title }
    userErrors { field message }
  }
}
"""


def update_title(cid, title):
    d = gql(UPDATE, {"input": {"id": cid, "title": title}})["collectionUpdate"]
    return d["userErrors"]


def do_revert():
    if not os.path.exists(BACKUP):
        sys.exit(f"退避ファイルがありません: {BACKUP}")
    saved = json.load(open(BACKUP))
    for cid, s in saved.items():
        err = update_title(cid, s["title"])
        print(f"{'NG' if err else 'OK'} 復元 {s['handle']} 「{s['title']}」 {err or ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="本番に書き込む（未指定なら点検のみ）")
    ap.add_argument("--revert", action="store_true", help="退避した変更前の名前に戻す")
    args = ap.parse_args()

    load_env()
    if args.revert:
        do_revert()
        return

    targets, skipped = [], []
    for handle, (expect, new) in PLAN.items():
        c = gql(BY_HANDLE, {"h": handle})["collectionByHandle"]
        if c is None:
            sys.exit(f"コレクションが見つかりません: {handle}")
        if c["title"] == new:
            skipped.append(handle)
            print(f"  {handle:16} 適用済み 「{new}」")
            continue
        if c["title"] != expect:
            sys.exit(f"[{handle}] 現在の名前「{c['title']}」が想定「{expect}」と違います。"
                     "誰かが先に変えた可能性があるので PLAN を確認してください。")
        seo_title = (c["seo"] or {}).get("title")
        flag = "" if seo_title else "  ⚠ seo.title 未設定＝<title> が新名称になる"
        print(f"  {handle:16} 「{c['title']}」 → 「{new}」{flag}")
        targets.append((c, new))

    print(f"\n対象 {len(targets)} 件 / 適用済み {len(skipped)} 件")
    if not args.apply:
        print("点検のみ（--apply で本番反映）")
        return
    if not targets:
        return

    saved = json.load(open(BACKUP)) if os.path.exists(BACKUP) else {}
    added = 0
    for c, _ in targets:
        if c["id"] not in saved:
            saved[c["id"]] = {"handle": c["handle"], "title": c["title"]}
            added += 1
    with open(BACKUP, "w") as f:
        json.dump(saved, f, ensure_ascii=False, indent=2)
    print(f"変更前を退避: {BACKUP}（今回 {added} 件追加 / 累計 {len(saved)} 件）\n")

    ok = 0
    for c, new in targets:
        err = update_title(c["id"], new)
        if err:
            print(f"NG {c['handle']}: {err}")
        else:
            ok += 1
            print(f"OK {c['handle']} 「{new}」")
    print(f"\n{ok}/{len(targets)} 件を更新しました")


if __name__ == "__main__":
    main()
