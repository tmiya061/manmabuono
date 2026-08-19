#!/usr/bin/env python3
"""多段になったURLリダイレクトを1ホップに詰める

背景（2026-08-19）:
  かつお削り節のURLを2回・別の日に変えたため、301が2本つながっていた。

    ①/products/無塩-鹿児島枕崎-おつお削り節      301 ↓  (2026-08-18 誤字修正 おつお→かつお)
    ②/products/無塩-鹿児島枕崎-かつお削り節      301 ↓  (2026-08-19 改名 無塩→塩無添加)
    ③/products/塩無添加-鹿児島枕崎-かつお削り節   200

  Shopifyは handle を変えるたび「その時点のURL → 新URL」の301を自動生成する。
  ①の転送先が改名前の②を指したまま取り残された、というだけの状態。
  Googleは多段でも辿るが、段数が増えるほど評価の引き継ぎは不確実になる
  （SEO担当・垣谷さんの指摘）。①の転送先を最終URLに向け直せば全経路が1ホップになる。

  ※①は2026-08-18まで存在した誤字URLで、外部リンクも評価もほぼ載っていない。
    評価が載っているのは②（302個の販売実績）で、そこは既に1ホップ。
    つまりこれは実害の是正ではなく掃除。

🔴 ②→③のリダイレクトは絶対に消さないこと。
   評価が付いているのは②のURLなので、消すと引き継ぎが切れる。
   このスクリプトも「転送先の書き換え」しかせず、削除は一切しない。

使い方:
  python3 scripts/fix_redirect_chain.py            # 点検のみ（現在のチェーンを表示）
  python3 scripts/fix_redirect_chain.py --apply    # 転送先を最終URLに向け直す
  python3 scripts/fix_redirect_chain.py --revert   # 退避した変更前の転送先に戻す

注意:
  urlRedirects は GraphQL Admin API ではスコープ不足で読めない（read_online_store_navigation が要る）。
  REST 2024-01 の /redirects.json なら現在のスコープで読み書きできるのでそちらを使う。
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

REST_VERSION = "2024-01"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP = os.path.join(ROOT, "scripts", "seo_meta", "redirect_chain.backup.json")
TOKEN = None

# 最終的な着地先（ここに向けて1ホップに詰める）
FINAL = "/products/塩無添加-鹿児島枕崎-かつお削り節"


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


def rest(method, path, body=None):
    global TOKEN
    if TOKEN is None:
        TOKEN = get_token()
    domain = os.environ["SHOPIFY_STORE_DOMAIN"]
    req = urllib.request.Request(
        f"https://{domain}/admin/api/{REST_VERSION}/{path}",
        data=json.dumps(body).encode() if body else None,
        headers={"Content-Type": "application/json", "X-Shopify-Access-Token": TOKEN},
        method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()[:400]}")


def dec(s):
    return urllib.parse.unquote(s)


def enc(s):
    """Shopifyの保存形式に合わせてパス部分だけをパーセントエンコードする"""
    return urllib.parse.quote(s, safe="/-_.~")


def fetch_all():
    return rest("GET", "redirects.json?limit=250")["redirects"]


def resolve(rows, path, seen=None):
    """path から辿れる最終地点と、経由したリダイレクトの列を返す"""
    seen = seen or []
    by_path = {dec(r["path"]): r for r in rows}
    cur, chain = path, []
    while cur in by_path:
        r = by_path[cur]
        if r["id"] in [x["id"] for x in chain]:
            sys.exit(f"リダイレクトが循環しています: {cur}")
        chain.append(r)
        cur = dec(r["target"])
    return cur, chain


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="本番に書き込む（未指定なら点検のみ）")
    ap.add_argument("--revert", action="store_true", help="退避した変更前の転送先に戻す")
    args = ap.parse_args()

    load_env()

    if args.revert:
        if not os.path.exists(BACKUP):
            sys.exit(f"退避ファイルがありません: {BACKUP}")
        for rid, s in json.load(open(BACKUP)).items():
            rest("PUT", f"redirects/{rid}.json",
                 {"redirect": {"id": int(rid), "target": s["target"]}})
            print(f"OK 復元 {dec(s['path'])} -> {dec(s['target'])}")
        return

    rows = fetch_all()

    # FINAL に辿り着く経路のうち、2ホップ以上のものを探す
    targets = []
    for r in rows:
        start = dec(r["path"])
        end, chain = resolve(rows, start)
        if end != FINAL or len(chain) < 2:
            continue
        # 詰めるのは経路の1本目だけ。途中のリダイレクトは評価が載っている可能性があるので残す
        targets.append((chain[0], [dec(x["target"]) for x in chain]))

    if not targets:
        print(f"{FINAL} へ向かう多段リダイレクトはありません（すべて1ホップ）")
        return

    print(f"最終URL: {FINAL}\n")
    seen = set()
    todo = []
    for first, hops in targets:
        if first["id"] in seen:
            continue
        seen.add(first["id"])
        print(f"■ {dec(first['path'])}")
        print(f"    現在: {' -> '.join(hops)}  （{len(hops)}ホップ）")
        print(f"    修正: {FINAL}  （1ホップ）")
        print(f"    ※ 経由していた {dec(first['target'])} のリダイレクトはそのまま残す（評価の受け皿）")
        print()
        todo.append(first)

    if not args.apply:
        print("点検のみ（--apply で本番反映）")
        return

    os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
    saved = json.load(open(BACKUP)) if os.path.exists(BACKUP) else {}
    for r in todo:
        saved.setdefault(str(r["id"]), {"path": r["path"], "target": r["target"]})
    with open(BACKUP, "w") as f:
        json.dump(saved, f, ensure_ascii=False, indent=2)
    print(f"変更前を退避: {BACKUP}\n")

    for r in todo:
        rest("PUT", f"redirects/{r['id']}.json",
             {"redirect": {"id": r["id"], "target": enc(FINAL)}})
        print(f"OK {dec(r['path'])} -> {FINAL}")


if __name__ == "__main__":
    main()
