#!/usr/bin/env python3
"""商品カードの効能ラベルを、スニペットの暫定マップから商品メタフィールドへ移す

背景:
  ラベルの文言は snippets/c_prod-label.liquid のハンドル別マップに直書きしていた。
  コードなので西川さんが編集できない。スニペットは最初から
  「引数 → custom.card_label → 暫定マップ」の順で読むので、
  メタフィールドに値が入れば、コードを変えずにそちらが優先される。

やること:
  1. custom.card_label（商品・単一行テキスト）の定義を作成（無ければ）
  2. スニペットのマップを読み、対応する商品にその文言を投入
  3. 投入前の値を scripts/card_label/card_label.backup.json に退避

使い方:
  python3 scripts/set_card_labels.py           # 点検のみ（書き込みなし）
  python3 scripts/set_card_labels.py --apply   # 定義作成＋値の投入

注意:
  ラベルは white-space:nowrap で溢れると…で切れるため、定義に最大16文字の検証を付ける。
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request

API_VERSION = "2026-07"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNIPPET = os.path.join(ROOT, "snippets", "c_prod-label.liquid")
BACKUP = os.path.join(ROOT, "scripts", "card_label", "card_label.backup.json")
NAMESPACE, KEY = "custom", "card_label"
MAX_LEN = 16
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


def parse_map():
    """スニペットの case/when から handle→文言 を取り出す（転記ミスを避けるため機械的に読む）"""
    pairs, pending = [], []
    for line in open(SNIPPET):
        s = line.strip()
        m = re.match(r"^when\s+(.+)$", s)
        if m:
            pending = re.findall(r"'([^']+)'", m.group(1))
            continue
        m = re.match(r"^assign prod_label = '([^']*)'$", s)
        if m and pending:
            for h in pending:
                pairs.append((h, m.group(1)))
            pending = []
    return pairs


FETCH = """
query($cursor: String) {
  products(first: 100, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes { id handle title metafield(namespace: "%s", key: "%s") { value } }
  }
}
""" % (NAMESPACE, KEY)

DEF_LOOKUP = """
query { metafieldDefinitions(first: 50, ownerType: PRODUCT, namespace: "%s") { nodes { id key name } } }
""" % NAMESPACE

DEF_CREATE = """
mutation($def: MetafieldDefinitionInput!) {
  metafieldDefinitionCreate(definition: $def) {
    createdDefinition { id name namespace key }
    userErrors { field message code }
  }
}
"""

SET = """
mutation($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    metafields { key value owner { ... on Product { handle } } }
    userErrors { field message code }
  }
}
"""


def fetch_all():
    items, cursor = [], None
    while True:
        p = gql(FETCH, {"cursor": cursor})["products"]
        items += p["nodes"]
        if not p["pageInfo"]["hasNextPage"]:
            return items
        cursor = p["pageInfo"]["endCursor"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    load_env()

    pairs = parse_map()
    by_handle = {p["handle"]: p for p in fetch_all()}

    hit, miss, toolong = [], [], []
    for h, label in pairs:
        if h not in by_handle:
            miss.append((h, label))
        elif len(label) > MAX_LEN:
            toolong.append((h, label))
        else:
            hit.append((h, label))

    print(f"マップ {len(pairs)}件 / 商品と一致 {len(hit)}件 / 商品なし {len(miss)}件 / 長すぎ {len(toolong)}件\n")
    for h, l in hit:
        cur = by_handle[h]["metafield"]
        state = "既に同じ" if cur and cur["value"] == l else ("上書き:" + cur["value"] if cur else "新規")
        print(f"  [{state}] {l}  ← {h}")
    if miss:
        print("\n  商品が見つからない（マップから消してよい候補）:")
        for h, l in miss:
            print(f"    {h}  ({l})")
    if toolong:
        print(f"\n  ⚠️ {MAX_LEN}文字超（定義の検証に引っかかる）:")
        for h, l in toolong:
            print(f"    {h}  ({l}) {len(l)}文字")

    if not args.apply:
        print("\n点検のみ。書き込むには --apply")
        return

    if toolong:
        print("\n長すぎる文言があるので中断。先に文言を直すこと。")
        sys.exit(1)

    # 1) 定義
    existing = {d["key"]: d for d in gql(DEF_LOOKUP)["metafieldDefinitions"]["nodes"]}
    if KEY in existing:
        print(f"\n定義は既にある: {existing[KEY]['id']}")
    else:
        r = gql(DEF_CREATE, {"def": {
            "name": "商品カードのラベル",
            "namespace": NAMESPACE,
            "key": KEY,
            "description": (
                "商品一覧・トップの写真の上に出る一言。"
                "「誰向けか」ではなく「この商品が何をしてくれるか」を書く（例：DHA・EPAで毛づやケア）。"
                "効能の断定（治る・予防できる・効く）は書かない。ケア／補う／サポート までで止める。"
                f"横1行で表示するため{MAX_LEN}文字以内。空にすればラベルは出ない。"),
            "type": "single_line_text_field",
            "ownerType": "PRODUCT",
            "pin": True,
            "validations": [{"name": "max", "value": str(MAX_LEN)}],
        }})["metafieldDefinitionCreate"]
        if r["userErrors"]:
            print("定義作成エラー:", json.dumps(r["userErrors"], ensure_ascii=False))
            sys.exit(1)
        print("\n定義を作成:", r["createdDefinition"]["id"])

    # 2) バックアップ（投入前の値）
    os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
    snap = {h: (by_handle[h]["metafield"]["value"] if by_handle[h]["metafield"] else None)
            for h, _ in hit}
    with open(BACKUP, "w") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)
    print(f"投入前の値を退避: {BACKUP}")

    # 3) 投入（25件ずつ）
    payload = [{"ownerId": by_handle[h]["id"], "namespace": NAMESPACE, "key": KEY,
                "type": "single_line_text_field", "value": l} for h, l in hit]
    done = 0
    for i in range(0, len(payload), 25):
        r = gql(SET, {"metafields": payload[i:i + 25]})["metafieldsSet"]
        if r["userErrors"]:
            print("投入エラー:", json.dumps(r["userErrors"], ensure_ascii=False))
            sys.exit(1)
        done += len(r["metafields"])
    print(f"投入完了: {done}件")

    # 4) 読み直して検証
    after = {p["handle"]: (p["metafield"]["value"] if p["metafield"] else None) for p in fetch_all()}
    bad = [(h, l, after.get(h)) for h, l in hit if after.get(h) != l]
    print("検証:", "全件一致" if not bad else f"不一致 {len(bad)}件 {bad}")
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
