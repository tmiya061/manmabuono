#!/usr/bin/env python3
"""コレクションに代替テーマテンプレートを割り当てる（Shopify Admin API）。

「どのコレクションがどのテンプレートを使うか」はテーマではなく Shopify 側の
データ（collection.templateSuffix）。テーマをmainにマージしただけでは
店頭の見た目は変わらず、ここを設定して初めて切り替わる。

割り当て（2026-08-01 オーナー確定）:
  dog-wet / cat-wet → wet （プレミアム / おかず / スープ・だし の3グループ）
  dog-all / cat-all → all （主食ドライ〜季節限定の9グループ）

🛑 これは店頭の見た目が即変わる操作。実行前にオーナー確認のこと。

使い方:
  python3 scripts/set_collection_template.py            # 現状表示（dry-run）
  python3 scripts/set_collection_template.py --apply    # 本番反映
  python3 scripts/set_collection_template.py --revert   # 変更前の割り当てに戻す
"""

import json
import os
import sys
import urllib.parse
import urllib.request

API_VERSION = "2026-07"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = os.path.join(ROOT, "scripts", "collection_template")
BACKUP = os.path.join(BACKUP_DIR, "backup.json")
TOKEN = None

ASSIGN = {
    "dog-wet": "wet",
    "cat-wet": "wet",
    "dog-all": "all",
    "cat-all": "all",
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


Q = "query($handle: String!) { collectionByHandle(handle: $handle) { id handle title templateSuffix } }"
M = """
mutation($input: CollectionInput!) {
  collectionUpdate(input: $input) {
    collection { handle templateSuffix }
    userErrors { field message }
  }
}
"""


def fetch(handle):
    c = gql(Q, {"handle": handle})["collectionByHandle"]
    if c is None:
        print(f"❌ コレクションが見つからない: {handle}")
        sys.exit(1)
    return c


def show():
    for h, want in ASSIGN.items():
        c = fetch(h)
        now = c["templateSuffix"] or "（既定 collection.json）"
        mark = "✅済" if c["templateSuffix"] == want else "  未"
        print(f"{mark} {h:<9} 現在: {now:<24} → {want}")


def apply():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup = json.load(open(BACKUP)) if os.path.exists(BACKUP) else {}
    for h, want in ASSIGN.items():
        c = fetch(h)
        backup.setdefault(h, c["templateSuffix"])
        if c["templateSuffix"] == want:
            print(f"skip（設定済）: {h} → {want}")
            continue
        res = gql(M, {"input": {"id": c["id"], "templateSuffix": want}})["collectionUpdate"]
        if res["userErrors"]:
            print("❌", res["userErrors"])
            sys.exit(1)
        print(f"✅ {h} → テンプレート '{res['collection']['templateSuffix']}'")
    with open(BACKUP, "w") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2)


def revert():
    if not os.path.exists(BACKUP):
        print("backup.json が無い。巻き戻せない。")
        sys.exit(1)
    for h, prev in json.load(open(BACKUP)).items():
        c = fetch(h)
        if c["templateSuffix"] == prev:
            continue
        res = gql(M, {"input": {"id": c["id"], "templateSuffix": prev}})["collectionUpdate"]
        if res["userErrors"]:
            print("❌", res["userErrors"])
            sys.exit(1)
        print(f"↩️ {h} → {prev or '（既定）'}")


def main():
    load_env()
    args = sys.argv[1:]
    if "--revert" in args:
        revert()
    elif "--apply" in args:
        apply()
        print()
        show()
    else:
        show()
        print("\n（dry-run。反映するには --apply）")


if __name__ == "__main__":
    main()
