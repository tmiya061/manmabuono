#!/usr/bin/env python3
"""ShopifyQL を叩くだけの小道具（読み取り専用）

使い方:
  python3 shopifyql.py "FROM sales SHOW net_sales SINCE -30d UNTIL today"
  echo "クエリ" | python3 shopifyql.py -
"""
import json
import os
import sys
import urllib.parse
import urllib.request

API_VERSION = "2026-07"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


Q = """
query($q: String!) {
  shopifyqlQuery(query: $q) {
    tableData { columns { name displayName dataType } rows }
    parseErrors
  }
}
"""


def run(q):
    d = gql(Q, {"q": q})["shopifyqlQuery"]
    if not d:
        print("(no response)")
        return
    pe = d.get("parseErrors")
    if pe:
        print("PARSE ERROR:", json.dumps(pe, ensure_ascii=False))
        return
    td = d.get("tableData") or {}
    cols = [c["name"] for c in td.get("columns", [])]
    print("\t".join(cols))
    for row in td.get("rows", []):
        if isinstance(row, dict):
            print("\t".join(str(row.get(c, "")) for c in cols))
        else:
            print("\t".join(str(v) for v in row))


if __name__ == "__main__":
    load_env()
    arg = sys.argv[1] if len(sys.argv) > 1 else "-"
    q = sys.stdin.read() if arg == "-" else arg
    for part in q.split("\n---\n"):
        part = part.strip()
        if not part:
            continue
        print(f"### {part}")
        run(part)
        print()
