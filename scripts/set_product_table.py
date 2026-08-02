#!/usr/bin/env python3
"""商品説明文（body_html）から仕様情報を抽出し、仕様テーブル metafield へ移す

背景:
  テーマの商品ページには custom.product_table1〜6（原材料名/賞味期限/与え方/保存方法/ご注意/栄養成分）
  の仕様テーブルが実装済みだが、2026-08-02 時点で埋まっているのは 37商品中4商品のみ。
  一方で本文テキストには同じ情報が「文字の壁」として書かれている。
  → 本文から抽出して metafield に移し、本文は読み物部分だけに整える。

使い方:
  python3 scripts/set_product_table.py             # 点検のみ（抽出結果プレビューを生成・書き込みなし）
  python3 scripts/set_product_table.py --apply     # 本番へ反映（metafield設定＋本文書き換え）
  python3 scripts/set_product_table.py --apply --only <handle>   # handle指定で部分適用
  python3 scripts/set_product_table.py --revert    # バックアップから復元

出力:
  scripts/product_table/preview.md          # 抽出プレビュー（適用前に必ず目視すること）
  scripts/product_table/backup.json         # 変更前の body_html / metafields（--apply 時に自動退避）

注意:
  --apply は本番の商品ページ本文を書き換える。実行前にオーナー確認を取ること。
  対象は「テーブルが全て空 かつ 本文に抽出マーカーがある」商品のみ。
  既にテーブルが埋まっている4商品・特殊ページ（食事代行/料理教室等）には触れない。
"""
import argparse
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from set_product_seo import load_env, gql  # 認証・GraphQLヘルパを流用

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "scripts", "product_table")
PREVIEW = os.path.join(OUTDIR, "preview.md")
BACKUP = os.path.join(OUTDIR, "backup.json")

# metafield キー → (テーマ側の見出し, 行頭マーカーの正規表現)
FIELDS = [
    ("product_table1", "原材料名", r"原材料名|原材料(?=[ 　：:])"),
    ("product_table2", "賞味期限", r"賞味期限"),
    ("product_table3", "与え方",   r"給与方法|与える方法|与え方"),
    ("product_table4", "保存方法", r"保存方法"),
    ("product_table5", "ご注意",   r"ご注意(?!ください)|注意事項"),
    ("product_table6", "栄養成分", r"栄養成分"),
]
# 本文に残すが、行としては独立させたいマーカー（テーブルに枠が無い / ブランド文）
KEEP_MARKERS = r"内容量|【"
ALL_MARKERS = "|".join(m for _, _, m in FIELDS) + "|" + KEEP_MARKERS

# 個別の事実誤り修正（本文に残す行に適用）
# チキン150g の内容量が 800g 表記のままコピーされていた誤記（2026-08-02 分析で発見）
FIX_BODY = {
    "だし薫る犬のごはん-チキン-150g": [("内容量 ８００ｇ", "内容量 １５０ｇ")],
}
# 個別のフィールド整形（抽出後の値に適用）：ダブルだし猫は原文に給与方法の
# 段落が2回（片方は翻訳崩れ）入っているため、崩れている方を落とす
FIX_FIELD_DROP = [
    ("ダブルだし猫のごはん-チキン-150g", "product_table3",
     "<成猫期から中高齢期まで>下記１日あたりの給与量の目安を参考に、体質や体重、量、便の状態などを観察しながら量を加減し、1日２～４回に分けて与えてください。"),
    ("ダブルだし猫のごはん-チキン-800g", "product_table3",
     "<成猫期から中高齢期まで>下記１日あたりの給与量の目安を参考に、体質や体重、量、便の状態などを観察しながら量を加減し、1日２～４回に分けて与えてください。"),
]

FETCH = """
query($cursor: String) {
  products(first: 100, after: $cursor, query: "status:active") {
    pageInfo { hasNextPage endCursor }
    nodes {
      id handle title descriptionHtml
      metafields(first: 10, namespace: "custom") { nodes { id key value } }
    }
  }
}
"""

UPDATE = """
mutation($product: ProductUpdateInput!) {
  productUpdate(product: $product) {
    product { id handle }
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
    return items


def to_lines(body_html):
    """span まみれの body_html を「テキスト行 or 画像トークン」のリストに変換する"""
    s = body_html
    s = re.sub(r"<img[^>]*src=\"([^\"]+)\"[^>]*>", r"\n⟦IMG:\1⟧\n", s)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</(p|div|h\d|li|tr)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    # 行中にマーカーが連結しているケース（例: 「１年保存方法 高温多湿…」「賞味期限製造より1年」）を
    # 区切り文字の有無にかかわらず行分割する
    s = re.sub(r"(?<=[^\n])(?=(%s))" % ALL_MARKERS, "\n", s)
    lines = [re.sub(r"[ \t　]+", " ", ln).strip() for ln in s.split("\n")]
    return [ln for ln in lines if ln]


def classify(lines):
    """行を metafield 6枠と「本文に残す行」に振り分ける"""
    fields = {k: [] for k, _, _ in FIELDS}
    keep = []
    current = None  # 与え方など複数行にまたがるセクションの継続先
    for ln in lines:
        matched = False
        for key, _, pat in FIELDS:
            m = re.match(r"^(%s)[ 　：:]*" % pat, ln)
            if m:
                rest = ln[m.end():].strip()
                if rest:
                    fields[key].append(rest)
                # 与え方・ご注意は後続行（●…など）が続くので継続モードに入る
                current = key if key in ("product_table3", "product_table5") else key
                matched = True
                break
        if matched:
            continue
        if ln.startswith("⟦IMG:") or re.match(r"^(%s)" % KEEP_MARKERS, ln) or ln.startswith("【"):
            keep.append(ln)
            current = None
            continue
        if current and (ln.startswith("●") or ln.startswith("※") or ln.startswith("〈") or ln.startswith("＜")):
            fields[current].append(ln)
            continue
        if current == "product_table3" and not re.match(r"^(%s)" % ALL_MARKERS, ln):
            # 与え方セクションは表や続き文が来るのでマーカーが出るまで取り込む
            fields[current].append(ln)
            continue
        # ご注意ラベルが無い商品でも、電子レンジ注意の定型文はご注意へ
        if ln.startswith("電子レンジで温める場合"):
            fields["product_table5"].append(ln)
            current = "product_table5"
            continue
        keep.append(ln)
        current = None
    # ●で始まる給与上の注意（ドライ商品）は、与え方が抽出できていれば与え方へ寄せる。
    # 翻訳汚れで●ブロックが複数行に裂けている商品があるため、最初の●から
    # 次の見出し的な行（【…】/画像/内容量）までを連続ブロックとして丸ごと移す
    if fields["product_table3"]:
        start = next((i for i, ln in enumerate(keep) if ln.startswith("●")), None)
        if start is not None:
            end = start
            while end < len(keep) and not re.match(r"^(【|⟦IMG|内容量)", keep[end]):
                end += 1
            fields["product_table3"] += keep[start:end]
            keep = keep[:start] + keep[end:]
    # 栄養成分ラベルが欠落している商品（おやつ類）：本文側に残った成分値の行を移す
    if not fields["product_table6"]:
        for i, ln in enumerate(keep):
            if re.match(r"^たんぱく質\s*[0-9０-９]", ln):
                fields["product_table6"].append(ln)
                keep = keep[:i] + keep[i + 1:]
                break
    out = {k: "\n".join(v).strip() for k, v in fields.items()}
    # 栄養成分ラベルが欠落・文字化けしている商品向け：
    # 他フィールドの末尾に「たんぱく質 nn%…」が紛れていたら栄養成分へ移す
    if not out["product_table6"]:
        for k in ("product_table3", "product_table4", "product_table5"):
            m = re.search(r"たんぱく質\s*[0-9０-９]", out[k])
            if m:
                out["product_table6"] = out[k][m.start():].strip()
                out[k] = out[k][:m.start()].strip()
                break
    return out, keep


def rebuild_body(keep_lines):
    """本文に残す行を素直な <p> / <img> で組み直す（翻訳span汚れの除去を兼ねる）"""
    out = []
    for ln in keep_lines:
        m = re.match(r"^⟦IMG:(.+)⟧$", ln)
        if m:
            out.append('<img src="%s" alt="">' % m.group(1))
        else:
            out.append("<p>%s</p>" % html.escape(ln, quote=False))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--only")
    args = ap.parse_args()
    load_env()
    os.makedirs(OUTDIR, exist_ok=True)

    if args.revert:
        with open(BACKUP) as f:
            backup = json.load(f)
        for h, rec in backup.items():
            if args.only and h != args.only:
                continue
            mfs = [{"namespace": "custom", "key": k, "value": v, "type": "multi_line_text_field"}
                   for k, v in rec["metafields"].items() if v]
            product = {"id": rec["id"], "descriptionHtml": rec["body_html"]}
            if mfs:
                product["metafields"] = mfs
            r = gql(UPDATE, {"product": product})["productUpdate"]
            print("revert", h, r["userErrors"] or "OK")
            # 復元時、こちらが新規に作った metafield は空文字で上書き（削除相当）
            new_keys = [k for k, _, _ in FIELDS if k not in rec["metafields"] or not rec["metafields"].get(k)]
            if new_keys:
                gql(UPDATE, {"product": {"id": rec["id"], "metafields": [
                    {"namespace": "custom", "key": k, "value": "", "type": "multi_line_text_field"}
                    for k in new_keys]}})
        return

    products = fetch_all()
    targets = []
    for p in products:
        existing = {n["key"]: n["value"] for n in p["metafields"]["nodes"]
                    if n["key"].startswith("product_table")}
        if any(v.strip() for v in existing.values()):
            continue  # 既にテーブルが埋まっている商品には触れない
        lines = to_lines(p["descriptionHtml"] or "")
        fields, keep = classify(lines)
        for old, new in FIX_BODY.get(p["handle"], []):
            keep = [ln.replace(old, new) for ln in keep]
        for h, key, drop in FIX_FIELD_DROP:
            if h == p["handle"]:
                fields[key] = "\n".join(
                    ln for ln in fields[key].split("\n") if ln != drop).strip()
        n_filled = sum(1 for v in fields.values() if v)
        if n_filled < 2:
            continue  # 抽出できる情報が乏しい商品（特殊ページ等）はスキップ
        targets.append((p, existing, fields, keep))

    # プレビュー生成
    with open(PREVIEW, "w") as f:
        f.write("# 仕様テーブル抽出プレビュー（%d商品）\n\n" % len(targets))
        f.write("> `python3 scripts/set_product_table.py` により生成。--apply 前に目視確認する。\n\n")
        for p, existing, fields, keep in targets:
            f.write("---\n\n## %s\n`%s`\n\n" % (p["title"], p["handle"]))
            f.write("### → テーブルへ移す\n\n")
            for key, label, _ in FIELDS:
                if fields[key]:
                    f.write("**%s**\n```\n%s\n```\n" % (label, fields[key]))
            f.write("\n### → 本文に残す\n\n```\n%s\n```\n\n" % "\n".join(keep))
    print("preview: %s（%d商品）" % (PREVIEW, len(targets)))

    if not args.apply:
        for p, _, fields, _ in targets:
            filled = [label for key, label, _ in FIELDS if fields[key]]
            print("  %-40s %s" % (p["handle"][:40], "/".join(filled)))
        print("\n書き込みなし。適用は --apply。")
        return

    # バックアップ
    backup = {}
    if os.path.exists(BACKUP):
        with open(BACKUP) as f:
            backup = json.load(f)
    for p, existing, fields, keep in targets:
        if args.only and p["handle"] != args.only:
            continue
        backup.setdefault(p["handle"], {
            "id": p["id"], "body_html": p["descriptionHtml"], "metafields": existing})
    with open(BACKUP, "w") as f:
        json.dump(backup, f, ensure_ascii=False, indent=1)

    for p, existing, fields, keep in targets:
        if args.only and p["handle"] != args.only:
            continue
        mfs = [{"namespace": "custom", "key": k, "value": v, "type": "multi_line_text_field"}
               for k, v in fields.items() if v]
        r = gql(UPDATE, {"product": {
            "id": p["id"],
            "descriptionHtml": rebuild_body(keep),
            "metafields": mfs,
        }})["productUpdate"]
        print("apply", p["handle"], r["userErrors"] or "OK")


if __name__ == "__main__":
    main()
