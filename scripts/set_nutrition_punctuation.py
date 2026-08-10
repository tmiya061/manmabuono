#!/usr/bin/env python3
"""商品の栄養成分（custom.product_table6）に読点を入れて読みやすくする

背景:
  商品詳細の仕様テーブル「栄養成分」は
  「たんぱく質 31.8％以上 脂質 12.3％以上 粗繊維 2.0％以下 …」のように
  項目がスペース区切りでベタ書きされており、どこまでが1項目か読み取りにくい。
  → 項目の切れ目に読点（、）を入れる。あわせて項目内の余分な空白だけ整える。

やること / やらないこと:
  ○ 項目の区切りに「、」を入れる（全角スペース区切りも「、」に統一）
  ○ 項目内の空白の正規化（ラベルと値の間は半角スペース1つ、「％」「以上/以下」「/」の前後の空白を除去）
  ○ 単位「ｋcal」（全角k）→「kcal」の統一（2026-08-10 オーナー承認。7商品で混在していた）
  × 数値・項目名（脂質/脂肪 等）の変更は一切しない
    → 値そのものの誤り・表記ゆれは西川さん確認が要るので、点検時に「要確認」として列挙するだけ

使い方:
  python3 scripts/set_nutrition_punctuation.py           # 点検のみ（プレビュー生成・書き込みなし）
  python3 scripts/set_nutrition_punctuation.py --apply   # 本番のメタフィールドを更新
  python3 scripts/set_nutrition_punctuation.py --apply --only <handle>
  python3 scripts/set_nutrition_punctuation.py --revert  # バックアップから復元

出力:
  scripts/nutrition/preview.md   # 変更前後の一覧（適用前に必ず目視する）
  scripts/nutrition/backup.json  # 変更前の値（--apply 時に自動退避）

注意:
  --apply は本番の商品ページの表示を書き換える。実行前にオーナー＋西川さん確認を取ること。
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from set_product_seo import load_env, gql  # 認証・GraphQLヘルパを流用

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "scripts", "nutrition")
PREVIEW = os.path.join(OUTDIR, "preview.md")
BACKUP = os.path.join(OUTDIR, "backup.json")

KEY = "product_table6"

# 栄養成分の項目名。長いものを先に並べる（「代謝エネルギー」が「エネルギー」に食われないように）
LABELS = [
    r"代謝エネルギー（ＭＥ）", r"代謝エネルギー\(ME\)", r"代謝エネルギー（ME）", r"代謝エネルギー",
    r"エネルギー",
    r"粗たんぱく質", r"たんぱく質", r"粗蛋白質", r"蛋白質",
    r"粗脂肪", r"脂肪", r"脂質",
    r"粗繊維", r"繊維",
    r"粗灰分", r"灰分",
    r"水分",
    r"カルシウム", r"リン", r"ナトリウム", r"マグネシウム", r"カリウム", r"タウリン",
    r"オメガ３脂肪酸", r"オメガ6脂肪酸", r"オメガ3脂肪酸", r"オメガ６脂肪酸",
]
LABEL_RE = re.compile("(" + "|".join(LABELS) + ")")


def normalize_value(v):
    """項目の値部分の空白を整える（文字そのものは変えない）"""
    v = v.replace("　", " ")          # 全角スペース → 半角
    v = re.sub(r"[ｋＫ](?=cal)", "k", v)   # 「28.5ｋcal」→「28.5kcal」（全角kの混在を統一）
    v = re.sub(r"\s*/\s*", "/", v)        # 「kcal/ 100g」→「kcal/100g」
    v = re.sub(r"\s+(?=[％%])", "", v)    # 「2.0 ％」→「2.0％」
    v = re.sub(r"\s+(?=以[上下])", "", v)  # 「0.1％ 以下」→「0.1％以下」
    v = re.sub(r"\s+", " ", v)
    return v.strip(" 、,")


def convert(text):
    """栄養成分テキストを項目単位に分解し、「、」で連結して返す

    戻り値: (整形後テキスト, 項目リスト[(ラベル, 値)], 先頭の未分類テキスト)
    """
    # 行ごとに処理する（改行はテーマ側で <br> になるので構造として維持する）
    out_lines, all_items, all_lead = [], [], []
    for line in text.replace("\r\n", "\n").split("\n"):
        if not line.strip():
            out_lines.append("")
            continue
        matches = list(LABEL_RE.finditer(line))
        if not matches:
            out_lines.append(line.strip())
            all_lead.append(line.strip())
            continue
        lead = line[: matches[0].start()].strip(" 　、,")
        if lead:
            all_lead.append(lead)
        items = []
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(line)
            label = m.group(1)
            value = normalize_value(line[m.end() : end])
            items.append((label, value))
        all_items.extend(items)
        parts = [f"{lb} {v}".strip() for lb, v in items]
        out_lines.append(("、".join([lead] + parts) if lead else "、".join(parts)))
    return "\n".join(out_lines), all_items, all_lead


FETCH = """
query($cursor: String) {
  products(first: 100, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id handle title status
      metafield(namespace: "custom", key: "%s") { id value type }
    }
  }
}
""" % KEY

SET = """
mutation($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    metafields { id }
    userErrors { field message }
  }
}
"""


def fetch_all():
    rows, cursor = [], None
    while True:
        data = gql(FETCH, {"cursor": cursor})["products"]
        for n in data["nodes"]:
            mf = n.get("metafield")
            if mf and mf["value"].strip():
                rows.append({
                    "id": n["id"], "handle": n["handle"], "title": n["title"],
                    "status": n["status"], "type": mf["type"], "value": mf["value"],
                })
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]
    return rows


def build_preview(rows):
    lines = [f"# 栄養成分 読点付与プレビュー（{len(rows)}商品）", "",
             "> `python3 scripts/set_nutrition_punctuation.py` により生成。--apply 前に目視確認する。", ""]
    warn = []
    changed = 0
    for r in rows:
        new, items, lead = convert(r["value"])
        if new != r["value"]:
            changed += 1
        lines += [f"## {r['title']}", f"`{r['handle']}` [{r['status']}]", "",
                  "**変更前**", "```", r["value"], "```",
                  "**変更後**", "```", new, "```", ""]
        empty = [lb for lb, v in items if not v]
        nodigit = [f"{lb} {v}" for lb, v in items if v and not re.search(r"\d", v)]
        if empty:
            warn.append(f"- `{r['handle']}` … 値が空の項目: {', '.join(empty)}")
        if nodigit:
            warn.append(f"- `{r['handle']}` … 数値が無い項目: {', '.join(nodigit)}")
        if lead:
            warn.append(f"- `{r['handle']}` … 項目名として解釈できない文字列: {' / '.join(lead)}")
    head = [f"変更あり: {changed} / {len(rows)} 商品", ""]
    if warn:
        head += ["## ⚠️ 要確認（このスクリプトでは直さない・西川さん確認が必要）", ""] + warn + [""]
    lines[3:3] = head
    os.makedirs(OUTDIR, exist_ok=True)
    with open(PREVIEW, "w") as f:
        f.write("\n".join(lines))
    return changed, warn


def apply(rows, only=None):
    targets = []
    for r in rows:
        if only and r["handle"] != only:
            continue
        new, _, _ = convert(r["value"])
        if new != r["value"]:
            targets.append((r, new))
    if not targets:
        print("変更対象なし")
        return
    os.makedirs(OUTDIR, exist_ok=True)
    with open(BACKUP, "w") as f:
        json.dump({r["handle"]: {"id": r["id"], "type": r["type"], "value": r["value"]}
                   for r, _ in targets}, f, ensure_ascii=False, indent=2)
    print(f"バックアップ: {BACKUP}（{len(targets)}件）")
    for i in range(0, len(targets), 25):
        chunk = targets[i : i + 25]
        payload = [{"ownerId": r["id"], "namespace": "custom", "key": KEY,
                    "type": r["type"], "value": new} for r, new in chunk]
        res = gql(SET, {"metafields": payload})["metafieldsSet"]
        if res["userErrors"]:
            print("エラー:", json.dumps(res["userErrors"], ensure_ascii=False, indent=2))
            sys.exit(1)
        for r, _ in chunk:
            print("  更新:", r["handle"])
    print(f"完了: {len(targets)}件")


def revert():
    with open(BACKUP) as f:
        data = json.load(f)
    items = list(data.items())
    for i in range(0, len(items), 25):
        chunk = items[i : i + 25]
        payload = [{"ownerId": v["id"], "namespace": "custom", "key": KEY,
                    "type": v["type"], "value": v["value"]} for _, v in chunk]
        res = gql(SET, {"metafields": payload})["metafieldsSet"]
        if res["userErrors"]:
            print("エラー:", json.dumps(res["userErrors"], ensure_ascii=False, indent=2))
            sys.exit(1)
        for h, _ in chunk:
            print("  復元:", h)
    print(f"完了: {len(items)}件を復元")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--only")
    args = ap.parse_args()
    load_env()
    if args.revert:
        revert()
        return
    rows = fetch_all()
    changed, warn = build_preview(rows)
    print(f"栄養成分あり: {len(rows)}商品 / 変更あり: {changed}商品 / 要確認: {len(warn)}件")
    print(f"プレビュー: {PREVIEW}")
    if args.apply:
        apply(rows, args.only)
    else:
        print("（--apply で本番反映）")


if __name__ == "__main__":
    main()
