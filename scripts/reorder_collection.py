#!/usr/bin/env python3
"""コレクションの商品並び順を一括変更する（Shopify Admin API）

並び順はテーマではなくデータ側。テーマの main-collection-product-grid は
collection.products をそのまま回すので、ここでの変更がそのまま店頭の並びになる。

使い方:
  python3 scripts/reorder_collection.py dog-all              # dry-run（表示のみ）
  python3 scripts/reorder_collection.py dog-all --apply      # 本番反映
  python3 scripts/reorder_collection.py dog-all --revert     # 直前のバックアップに戻す
  python3 scripts/reorder_collection.py dog-all --dump       # 現在の並びをJSON雛形で出力

並び順の定義:
  scripts/collection_order/<handle>.json の blocks[].handles に商品handleを列挙する。
  そこに書かれていない商品（［追加用］等の非公開品）は、現在の相対順のまま最後尾へ回す。

並べ方の原則（オーナー確定 2026-07-31・全コレクション共通）:
  1. 主食（ドライ）を最上位。おやつ・季節ものは下部へ
  2. 同一商品はまとめ、容量は小→大（150g→800g／単品→3袋／2袋→5袋）
  3. ブロック順＝主食ドライ→お試し→ウェット→プレミアム→スープだし
     →トッピング→手作り素材→おやつ→季節もの→非公開

注意（実際に踏んだ落とし穴）:
  - 反映確認を curl 既定（HTTP/2）でやらないこと。Shopifyのページキャッシュが
    プロトコル別に分かれ、HTTP/2 だけ古いHTMLを長時間返し続ける。
    確認は /collections/<handle>/products.json か curl --http1.1 か実ブラウザで。
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

API_VERSION = "2026-07"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORDER_DIR = os.path.join(ROOT, "scripts", "collection_order")
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


Q_LIST = """
query($handle: String!, $cursor: String) {
  collectionByHandle(handle: $handle) {
    id handle title sortOrder
    products(first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes { id handle title status }
    }
  }
}
"""


def fetch(handle):
    items, cursor, meta = [], None, None
    while True:
        c = gql(Q_LIST, {"handle": handle, "cursor": cursor})["collectionByHandle"]
        if c is None:
            print(f"!! コレクションが見つかりません: {handle}")
            sys.exit(1)
        meta = {"id": c["id"], "title": c["title"], "sortOrder": c["sortOrder"]}
        items += c["products"]["nodes"]
        if not c["products"]["pageInfo"]["hasNextPage"]:
            break
        cursor = c["products"]["pageInfo"]["endCursor"]
    return meta, items


def backup_path(handle):
    return os.path.join(ORDER_DIR, f"{handle}.backup.json")


def build_target(handle, items):
    with open(os.path.join(ORDER_DIR, f"{handle}.json")) as f:
        spec = json.load(f)
    by_handle = {p["handle"]: p for p in items}
    ordered, used, missing = [], set(), []
    for b in spec["blocks"]:
        for h in b["handles"]:
            p = by_handle.get(h)
            if p is None:
                missing.append(h)
                continue
            ordered.append((b["label"], p))
            used.add(h)
    if missing:
        print("!! 定義にあるがコレクションに無いhandle:", missing)
        sys.exit(1)
    for p in items:  # 未指定（非公開の［追加用］等）は現在の相対順で最後尾へ
        if p["handle"] not in used:
            ordered.append(("⑩ 非公開（追加用/コピー）", p))
    assert len(ordered) == len(items), (len(ordered), len(items))
    return ordered


def reorder(cid, product_ids):
    moves = [{"id": pid, "newPosition": str(i)} for i, pid in enumerate(product_ids)]
    m = """
    mutation($id: ID!, $moves: [MoveInput!]!) {
      collectionReorderProducts(id: $id, moves: $moves) {
        job { id done }
        userErrors { field message }
      }
    }
    """
    d = gql(m, {"id": cid, "moves": moves})["collectionReorderProducts"]
    if d["userErrors"]:
        print("!! userErrors:", json.dumps(d["userErrors"], ensure_ascii=False, indent=2))
        sys.exit(1)
    job = d["job"]
    print(f"ジョブ投入: {job['id']}")
    jq = "query($id: ID!) { job(id: $id) { id done } }"
    for _ in range(60):
        if gql(jq, {"id": job["id"]})["job"]["done"]:
            print("ジョブ完了")
            return
        time.sleep(2)
    print("!! ジョブが時間内に完了しませんでした")


def main():
    load_env()
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    handle = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "--dry-run"
    meta, items = fetch(handle)
    print(f'{meta["title"]}（{handle}）sortOrder={meta["sortOrder"]} / {len(items)}件\n')

    if meta["sortOrder"] != "MANUAL":
        print(f'!! sortOrder が MANUAL ではありません（{meta["sortOrder"]}）。'
              '管理画面で「手動」にしないと並び替えは反映されません。')
        sys.exit(1)

    if mode == "--dump":
        for i, p in enumerate(items, 1):
            print(f'{i:>3}. {p["handle"]}  # {p["title"]} ({p["status"]})')
        return

    if mode == "--revert":
        with open(backup_path(handle)) as f:
            ids = [p["id"] for p in json.load(f)["order"]]
        print(f"バックアップの並び（{len(ids)}件）に戻します")
        reorder(meta["id"], ids)
        return

    ordered = build_target(handle, items)
    last = None
    for i, (label, p) in enumerate(ordered, 1):
        if label != last:
            print(f"\n--- {label} ---")
            last = label
        flag = "" if p["status"] == "ACTIVE" else f'  ({p["status"]})'
        print(f'{i:>3}. {p["title"]}{flag}')

    if mode != "--apply":
        print("\n[dry-run] 書き込みなし。--apply で本番反映します。")
        return

    with open(backup_path(handle), "w") as f:  # 反映前に現状を退避
        json.dump({"handle": handle,
                   "order": [{"id": p["id"], "handle": p["handle"], "title": p["title"]}
                             for p in items]}, f, ensure_ascii=False, indent=2)
    print(f'\nバックアップ: {backup_path(handle)}')

    print(f"本番反映します（{len(ordered)}件）…")
    reorder(meta["id"], [p["id"] for _, p in ordered])

    _, after = fetch(handle)
    expect = [p["handle"] for _, p in ordered]
    actual = [p["handle"] for p in after]
    if expect == actual:
        print("✅ 検証OK：狙いどおりの並びになりました")
        print(f"   店頭確認は https://manmabuono.jp/collections/{handle}/products.json で"
              "（素のHTMLはHTTP/2キャッシュで古いままのことがある）")
    else:
        print("⚠️ 検証NG：期待と異なります")
        for i, (e, a) in enumerate(zip(expect, actual), 1):
            if e != a:
                print(f'{i:>3}. 期待={e}  実際={a}')


main()
