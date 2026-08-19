#!/usr/bin/env python3
"""かつお削り節の商品名表記を「塩無添加」に統一し、誤った塩分表記を直す

背景:
  2026-08-19、主力商品を「無塩 鹿児島枕崎 かつお削り節」→「塩無添加 …」に改名した。
  製造工程で塩を使っていないという事実に即しており「無塩」より正確、という判断（SEO担当・垣谷さん確認済み）。
  ところが改名が本体商品にしか及んでおらず、周辺に旧表記が残っていた。

    - dog-trial-set  内容量の記載が「無塩鹿児島枕崎かつお削り節」
    - cat-trial-set  内容量の記載が「減塩鹿児島枕崎かつお削り節」  ← 犬と猫で表記まで割れていた
    - ［追加用］     商品名・本文とも旧表記のまま（本文は型リライト前の原文が残存）

  あわせて、同じ日に判明した数値の誤りも直す。
  検査証明書の 0.10% は **ナトリウム** の値であって食塩相当量ではない。
  食品表示基準では 食塩相当量 = ナトリウム量 × 2.54 と換算が決まっており、
  塩分として書くなら約0.25%になる。「塩分0.1%」は表示上の誤りで景表法のリスクもある。
  本体商品は修正済みだが、［追加用］の本文に「塩分量が０．１％と減塩です」が残っていた。

  「減塩」という語自体も、塩を使っていない以上ミスリードなので落とす。

対象と方針:
  - 本文（descriptionHtml）と seo.description は置換する
  - ［追加用］は商品名（title）も直す
  - 🔴 ［追加用］の handle は変えない。
    三河屋サブスクの「マイページ追加購入設定」がアプリ側のデータで、
    一覧API `/apps/floor-s/api/v1/my-page-target-product-variants` が handle を返す＝
    アプリが handle を保持している可能性がある。UNLISTED でURLは客に見えないため、
    handle を変える利得はゼロ・壊すリスクだけがある。→ docs/subscription-mikawaya.md

使い方:
  python3 scripts/fix_katsuo_naming.py            # 点検のみ（書き込みなし・差分を表示）
  python3 scripts/fix_katsuo_naming.py --apply    # 本番に反映する
  python3 scripts/fix_katsuo_naming.py --revert    # 退避した変更前の状態に戻す

注意:
  --apply は本番の商品ページ本文と検索結果スニペットを書き換える。実行前にオーナー確認を取ること。
  実行すると変更前の title / descriptionHtml / seo を
  scripts/seo_meta/katsuo_naming.backup.json に退避する。
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
BACKUP = os.path.join(ROOT, "scripts", "seo_meta", "katsuo_naming.backup.json")
TOKEN = None

# handle -> {フィールド: [(旧, 新, 出現回数), ...]}
# 出現回数を明示して、想定とズレたら止める（本文は手で編集されうるため）
PLAN = {
    "dog-trial-set": {
        "descriptionHtml": [("無塩鹿児島枕崎かつお削り節", "塩無添加鹿児島枕崎かつお削り節", 1)],
        "seo.description": [("無塩かつお削り節", "塩無添加かつお削り節", 1)],
    },
    "cat-trial-set": {
        "descriptionHtml": [("減塩鹿児島枕崎かつお削り節", "塩無添加鹿児島枕崎かつお削り節", 1)],
        "seo.description": [("減塩かつお削り節", "塩無添加かつお削り節", 1)],
    },
    "無塩-鹿児島枕崎-かつお削り節-追加用": {
        "title": [("無塩 鹿児島枕崎 かつお削り節 20g", "塩無添加 鹿児島枕崎 かつお削り節 20g", 1)],
        "descriptionHtml": [
            ("減塩鹿児島枕崎産かつお削り節", "塩無添加鹿児島枕崎産かつお削り節", 1),
            # 数値の誤り：検査値はナトリウム。食塩相当量なら×2.54で約0.25%になる
            ("塩分量が０．１％と減塩です", "ナトリウム量が０．１％です", 1),
            ("この減塩での削り節が完成しました", "この塩無添加の削り節が完成しました", 1),
        ],
    },
}

DESC_MAX = 125  # 全角換算の目安（日本語スニペットは全角120字前後で切られる）


def width(s):
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


BY_HANDLE = """
query($h: String!) {
  productByHandle(handle: $h) {
    id handle title status descriptionHtml seo { title description }
  }
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


def snapshot(p):
    return {
        "handle": p["handle"],
        "title": p["title"],
        "descriptionHtml": p["descriptionHtml"],
        "seo": p["seo"],
    }


def build_edits(p, spec):
    """置換を適用した結果を返す。すでに適用済み／想定と違う場合は理由を添えて返す"""
    edits, notes = {}, []
    for field, rules in spec.items():
        cur = p["seo"]["description"] if field == "seo.description" else p[field]
        if cur is None:
            notes.append(f"{field}: 値が空 → スキップ")
            continue
        new = cur
        for old, rep, times in rules:
            n = new.count(old)
            if n == 0:
                if rep in new:
                    notes.append(f"{field}: 「{old}」は既に適用済み → スキップ")
                    continue
                sys.exit(f"[{p['handle']}] {field} に「{old}」が見つかりません。"
                         "本文が変わっている可能性があります。PLAN を確認してください。")
            if n != times:
                sys.exit(f"[{p['handle']}] {field} の「{old}」が {n} 箇所（想定 {times}）。"
                         "意図しない箇所まで置換する恐れがあるため中止します。")
            new = new.replace(old, rep)
        if new != cur:
            edits[field] = new
    return edits, notes


def to_input(pid, edits):
    inp = {"id": pid}
    if "title" in edits:
        inp["title"] = edits["title"]
    if "descriptionHtml" in edits:
        inp["descriptionHtml"] = edits["descriptionHtml"]
    if "seo.description" in edits:
        inp["seo"] = {"description": edits["seo.description"]}
    return inp


def do_revert():
    if not os.path.exists(BACKUP):
        sys.exit(f"退避ファイルがありません: {BACKUP}")
    saved = json.load(open(BACKUP))
    for pid, s in saved.items():
        inp = {"id": pid, "title": s["title"], "descriptionHtml": s["descriptionHtml"]}
        if s["seo"] and s["seo"].get("description") is not None:
            inp["seo"] = {"description": s["seo"]["description"]}
        d = gql(UPDATE, {"input": inp})["productUpdate"]
        print(f"{'NG' if d['userErrors'] else 'OK'} 復元 {s['handle']} {d['userErrors'] or ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="本番に書き込む（未指定なら点検のみ）")
    ap.add_argument("--revert", action="store_true", help="退避した変更前の状態に戻す")
    args = ap.parse_args()

    load_env()

    if args.revert:
        do_revert()
        return

    targets = []
    for handle, spec in PLAN.items():
        p = gql(BY_HANDLE, {"h": handle})["productByHandle"]
        if p is None:
            sys.exit(f"商品が見つかりません: {handle}")
        edits, notes = build_edits(p, spec)
        targets.append((p, edits, notes))

    for p, edits, notes in targets:
        print(f"■ {p['handle']}  「{p['title']}」 [{p['status']}]")
        for n in notes:
            print(f"    - {n}")
        if not edits:
            print("    変更なし\n")
            continue
        for field, new in edits.items():
            if field == "descriptionHtml":
                # 差分のある行だけ出す
                for a, b in zip(p[field].split("<br>"), new.split("<br>")):
                    if a != b:
                        print(f"    {field}:\n      旧 {a.strip()[:110]}\n      新 {b.strip()[:110]}")
            else:
                cur = p["seo"]["description"] if field == "seo.description" else p[field]
                print(f"    {field}:\n      旧 {cur}\n      新 {new}")
                if field == "seo.description":
                    w = width(new) / 2
                    flag = "  ⚠ 目安超過" if w > DESC_MAX else ""
                    print(f"      （全角 {w:.0f}字 / 目安 {DESC_MAX}字{flag}）")
        print()

    todo = [(p, e) for p, e, _ in targets if e]
    if not todo:
        print("反映対象なし（すべて適用済み）")
        return
    print(f"反映対象 {len(todo)} 商品")

    if not args.apply:
        print("\n点検のみ（--apply で本番反映）")
        return

    os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
    saved = json.load(open(BACKUP)) if os.path.exists(BACKUP) else {}
    added = 0
    for p, _ in todo:
        # 退避は「最初に触ったときの状態」を正とする（再実行で上書きしない）
        if p["id"] not in saved:
            saved[p["id"]] = snapshot(p)
            added += 1
    with open(BACKUP, "w") as f:
        json.dump(saved, f, ensure_ascii=False, indent=2)
    print(f"\n変更前を退避: {BACKUP}（今回 {added} 件追加 / 累計 {len(saved)} 件）")

    for p, edits in todo:
        d = gql(UPDATE, {"input": to_input(p["id"], edits)})["productUpdate"]
        if d["userErrors"]:
            print(f"NG {p['handle']}: {d['userErrors']}")
        else:
            print(f"OK {p['handle']} → 「{d['product']['title']}」")


if __name__ == "__main__":
    main()
