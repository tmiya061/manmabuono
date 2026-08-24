#!/usr/bin/env python3
"""複数袋版の栄養成分（custom.product_table6）を単品／少ない袋数版に揃える

背景:
  同じ中身なのに袋数違いで栄養成分が食い違っている商品が3組ある。
  2026-08-24 にオーナー判断で「少ない袋数のほうを正」として複数袋版を書き換える。
  食い違いの出所は翻訳表示のままのコピペ（span汚れと同じ）で、Shopify内に正しい原文は無い。
  → したがって本作業は「サイト内の食い違いを消す」ものであって、
    パッケージ表示と一致する保証にはならない。パッケージ照合は西川さんに別途依頼中。

やること / やらないこと:
  ○ 下記 PAIRS の dst（複数袋版）の product_table6 を src（少ない袋数版）と同じ文字列にする
    - 「脂肪」→「脂質」の項目名もこれで揃う（かつおのうま煮3袋）
  × src 側は一切触らない
  × table6 以外（原材料名・与え方・保存方法など）は触らない
    → 与え方の回数・保存方法の冷凍案内は西川さん確認待ち（確認文書を別途作成）

使い方:
  python3 scripts/sync_pack_nutrition.py           # 点検のみ（プレビュー生成・書き込みなし）
  python3 scripts/sync_pack_nutrition.py --apply   # 本番のメタフィールドを更新
  python3 scripts/sync_pack_nutrition.py --revert  # バックアップから復元

出力:
  scripts/nutrition/pack_sync_preview.md   # 変更前後（適用前に必ず目視する）
  scripts/nutrition/pack_sync.backup.json  # 変更前の値（--apply 時に自動退避・追記式）
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from set_product_seo import load_env, gql  # 認証・GraphQLヘルパを流用

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "scripts", "nutrition")
PREVIEW = os.path.join(OUTDIR, "pack_sync_preview.md")
BACKUP = os.path.join(OUTDIR, "pack_sync.backup.json")

KEY = "product_table6"

# (正とする側の handle, 書き換える側の handle)
PAIRS = [
    ("地鶏のそぼろ煮1袋", "地鶏のそぼろ煮3袋"),
    ("枕崎-かつおのうま煮1袋", "枕崎-かつおのうま煮3袋"),
    ("京の一番だし", "京の一番だし5袋"),
]

Q = """
query($handle:String!){
  productByHandle(handle:$handle){
    id handle title status
    metafield(namespace:"custom", key:"product_table6"){ value }
  }
}
"""

SET = """
mutation($metafields:[MetafieldsSetInput!]!){
  metafieldsSet(metafields:$metafields){ userErrors { field message } }
}
"""


def fetch(handle):
    n = gql(Q, {"handle": handle})["productByHandle"]
    if not n:
        print(f"商品が見つからない: {handle}")
        sys.exit(1)
    n["t6"] = (n.get("metafield") or {}).get("value") or ""
    return n


def plan():
    """変更が要るものだけ (src, dst) で返す"""
    changes = []
    for src_h, dst_h in PAIRS:
        src, dst = fetch(src_h), fetch(dst_h)
        if not src["t6"].strip():
            print(f"正とする側が空なのでスキップ: {src_h}")
            continue
        if src["t6"] == dst["t6"]:
            print(f"既に一致: {dst_h}")
            continue
        changes.append((src, dst))
    return changes


def build_preview(changes):
    lines = ["# 複数袋版の栄養成分を少ない袋数版に揃える（プレビュー）", ""]
    if not changes:
        lines.append("変更対象なし")
    for src, dst in changes:
        lines += [
            f"## {dst['title']}  [{dst['status']}]",
            f"- 正とする側: {src['title']}",
            "",
            "変更前",
            "```",
            dst["t6"],
            "```",
            "変更後",
            "```",
            src["t6"],
            "```",
            "",
        ]
    os.makedirs(OUTDIR, exist_ok=True)
    with open(PREVIEW, "w") as f:
        f.write("\n".join(lines))
    print(f"プレビュー: {PREVIEW}")


def apply(changes):
    if not changes:
        print("変更対象なし")
        return
    # 既存バックアップに「追記」する（上書きしない）。2回目以降の --apply で、
    # 1回目に退避した本当の変更前の値を失わないため
    backup = {}
    if os.path.exists(BACKUP):
        with open(BACKUP) as f:
            backup = json.load(f)
    for src, dst in changes:
        backup.setdefault(dst["handle"], {"id": dst["id"], "fields": {}})["fields"].setdefault(KEY, dst["t6"])
    os.makedirs(OUTDIR, exist_ok=True)
    with open(BACKUP, "w") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2)
    print(f"バックアップ: {BACKUP}（{len(backup)}商品）")

    payload = [{"ownerId": dst["id"], "namespace": "custom", "key": KEY,
                "type": "multi_line_text_field", "value": src["t6"]} for src, dst in changes]
    res = gql(SET, {"metafields": payload})["metafieldsSet"]
    if res["userErrors"]:
        print("エラー:", json.dumps(res["userErrors"], ensure_ascii=False, indent=2))
        sys.exit(1)
    for _, dst in changes:
        print("  更新:", dst["handle"])
    print(f"完了: {len(changes)}フィールド")


def revert():
    if not os.path.exists(BACKUP):
        print(f"バックアップが無い: {BACKUP}")
        sys.exit(1)
    with open(BACKUP) as f:
        backup = json.load(f)
    payload = [{"ownerId": v["id"], "namespace": "custom", "key": KEY,
                "type": "multi_line_text_field", "value": v["fields"][KEY]}
               for v in backup.values()]
    res = gql(SET, {"metafields": payload})["metafieldsSet"]
    if res["userErrors"]:
        print("エラー:", json.dumps(res["userErrors"], ensure_ascii=False, indent=2))
        sys.exit(1)
    print(f"復元: {len(payload)}フィールド")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    load_env()
    if a.revert:
        revert()
        return
    changes = plan()
    build_preview(changes)
    if a.apply:
        apply(changes)
    else:
        print("※ 書き込みはしていない。適用は --apply")


if __name__ == "__main__":
    main()
