#!/usr/bin/env python3
"""西川さんの著者プロフィールを登録する（2026-08-19・垣谷さん作成の草案より）

出典: Googleドキュメント「著者プロフィール草案と確認事項」（2026-08-18 垣谷）
      https://docs.google.com/document/d/1bY9VSzwBQVkettjy3k_7bibOPr-dSOu0K0TBZqKbkx0/

やること（3段階。--step で個別実行もできる）
  1. defs   : article_author の定義にフィールドを2つ追加
               - name_kana (single_line_text_field) ふりがな。著者ページだけに出す
               - long_bio  (rich_text_field)        著者ページ用の長文（見出し付き・約850字）
               ※ bio（約160字）は記事下の著者ボックス用＋meta description 用として従来どおり
  2. photo  : 顔写真（800×800）を Shopify ファイルへアップロード
  3. entry  : エントリー nishikawa の全フィールドを更新

退避: scripts/metaobject_defs/article_author.backup_20260819_pre_profile.json（定義＋全エントリー）
戻す: 定義は追加した2フィールドを削除、エントリーは退避JSONの値で metaobjectUpdate
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from shopifyql import load_env, gql  # noqa: E402
import upload_file  # noqa: E402

load_env()

DEF_ID = "gid://shopify/MetaobjectDefinition/11262722109"
ENTRY_ID = "gid://shopify/Metaobject/172483510333"  # handle: nishikawa
PHOTO_PATH = os.path.expanduser("~/Documents/manmabuono/著者写真/nishikawa_800.jpg")
PHOTO_ALT = "西川 友保（株式会社MANMA BUONO KYOTO JAPAN 代表）"

# ---------- 値（草案 C表＋A/B本文） ----------
NAME = "西川 友保"
NAME_KANA = "にしかわ ともやす"
ROLE_TITLE = "株式会社MANMA BUONO KYOTO JAPAN 代表"
QUALIFICATION = "犬の管理栄養士／犬の腸活管理アドバイザー／犬猫アレルギー管理アドバイザー"
BIO = (
    "食品メーカーで25年間、商品の企画開発に携わる。愛猫を癌で亡くした経験から犬と猫の食事を学び直し、"
    "2022年にマンマボーノを立ち上げる。手作りごはんの料理教室は100回を超え、のべ5,000頭以上の犬と猫の"
    "食事に向き合ってきた。現在は猫4頭・犬1頭と暮らす。"
)
PROFILE_URL = "https://manmabuono.jp/pages/author/nishikawa"
SAME_AS = [
    "https://www.kbs-kyoto.co.jp/tv/taniryu/entry/275.htm",
    "https://kyotokurasu.jp/kbs/tv/57567",
    "https://manmabuono.jp/pages/story",
]


def h(text):
    return {"type": "heading", "level": 2, "children": [{"type": "text", "value": text}]}


def p(*children):
    out = []
    for c in children:
        out.append({"type": "text", "value": c} if isinstance(c, str) else c)
    return {"type": "paragraph", "children": out}


def link(text, url):
    return {"type": "link", "url": url, "title": text, "children": [{"type": "text", "value": text}]}


LONG_BIO = {
    "type": "root",
    "children": [
        h("25年間、人の食品をつくってきた"),
        p("25歳から50歳までの25年間、京都の食品会社に勤めました。企画開発、営業、経営戦略。原材料をどう選び、どう組み立てて一つの商品にするか。人が口にするものを、その手順で考え続けてきました。"),
        p("その経験が、いま犬と猫のごはんづくりの土台になっています。"),
        h("一頭の猫が、すべてを変えた"),
        p("家族だった保護猫のしずかちゃんが、癌で旅立ちました。15歳でした。"),
        p("診断のとき、獣医師にこう言われました。「シニアには、ドライフードだけの食事が疾患の引き金になることが多いのです」。"),
        p("総合栄養食を与えていれば安心だと信じていました。その前提が崩れました。当時与えていたフードを調べ直すと、人の食品では使用が認められていない添加物が入っていました。25年間、人の食品の原材料を見てきたはずの自分が、家族の食事については何も見ていなかった。"),
        p("（このときのことは「", link("マンマボーノの思い", "https://manmabuono.jp/pages/story"), "」に詳しく書いています）"),
        h("知識を、感覚ではなく資格として持つ"),
        p("2023年から犬と猫の栄養を学び直し、2024年4月に犬の管理栄養士の資格を取得しました。その後、飼い主さんからアレルギーの相談を受けることが増え、2026年5月に犬猫アレルギー管理アドバイザーと犬の腸活管理アドバイザーの資格を取得しています。"),
        p("自分の経験だけで語らないためです。"),
        h("5,000頭ぶんの、実際の相談"),
        p("2022年3月にマンマボーノの販売を始め、並行して手作りごはんの料理教室を続けてきました。開催は100回を超え、参加していただいた犬と猫は、のべ5,000頭以上になります。"),
        p("そこで最も多く受ける相談は、「ドライフードを食べてくれない」「涙やけが気になる」「病気を抱えていて、何を食べさせればよいのか分からない」の3つです。"),
        p("このサイトの記事は、その相談に答えるために書いています。一般論ではなく、実際に聞かれたことに答えます。"),
        h("今の家族"),
        p("猫4頭と、犬1頭と暮らしています。最年長のあんかけは推定21歳、家族になって11年目です。シュプーとサバァが10歳、メルシーが推定1歳。犬のボンジュールはスタンダードプードルの1歳8か月。"),
        h("伝えたいこと"),
        p("「水がなければ栄養は身体を巡らない。水がなければ、身体は毒素を出すこともできない」"),
        p("犬と猫の栄養を学び始めたとき、教本の最初に書かれていた一文です。私はこれを知らないまま、しずかちゃんを見送りました。"),
        p("同じ後悔を、誰にもしてほしくない。それだけです。"),
    ],
}

# ---------- GraphQL ----------
M_DEF = """
mutation($id: ID!, $definition: MetaobjectDefinitionUpdateInput!) {
  metaobjectDefinitionUpdate(id: $id, definition: $definition) {
    metaobjectDefinition { fieldDefinitions { key name type { name } } }
    userErrors { field message code }
  }
}
"""

M_ENTRY = """
mutation($id: ID!, $metaobject: MetaobjectUpdateInput!) {
  metaobjectUpdate(id: $id, metaobject: $metaobject) {
    metaobject { handle fields { key value } }
    userErrors { field message code }
  }
}
"""


def step_defs():
    vars_ = {
        "id": DEF_ID,
        "definition": {
            "fieldDefinitions": [
                {"create": {
                    "key": "name_kana", "name": "ふりがな",
                    "description": "著者ページの氏名の下に表示。記事下の著者ボックスには出ない",
                    "type": "single_line_text_field"}},
                {"create": {
                    "key": "long_bio", "name": "プロフィール（著者ページ用）",
                    "description": "著者ページ /pages/author/◯◯ の本文。見出し（H2）と段落で書く。"
                                   "空なら「プロフィール」（短文）が代わりに表示される",
                    "type": "rich_text_field"}},
            ]
        },
    }
    d = gql(M_DEF, vars_)["metaobjectDefinitionUpdate"]
    print(json.dumps(d, ensure_ascii=False, indent=2))
    if d["userErrors"]:
        sys.exit(1)


def step_photo():
    nodes = upload_file.upload([PHOTO_PATH])
    if not nodes:
        sys.exit(1)
    gid = nodes[0]["id"]
    # alt を付ける
    r = gql("""
      mutation($files: [FileUpdateInput!]!) {
        fileUpdate(files: $files) { files { id alt } userErrors { field message } }
      }""", {"files": [{"id": gid, "alt": PHOTO_ALT}]})
    print(json.dumps(r, ensure_ascii=False))
    with open(os.path.join(HERE, "nishikawa_photo_gid.txt"), "w") as f:
        f.write(gid + "\n")
    print("photo gid:", gid)
    return gid


def step_entry(photo_gid):
    fields = [
        {"key": "name", "value": NAME},
        {"key": "name_kana", "value": NAME_KANA},
        {"key": "role_title", "value": ROLE_TITLE},
        {"key": "qualification", "value": QUALIFICATION},
        {"key": "bio", "value": BIO},
        {"key": "long_bio", "value": json.dumps(LONG_BIO, ensure_ascii=False)},
        {"key": "profile_url", "value": PROFILE_URL},
        {"key": "same_as", "value": json.dumps(SAME_AS)},
    ]
    if photo_gid:
        fields.append({"key": "photo", "value": photo_gid})
    d = gql(M_ENTRY, {"id": ENTRY_ID, "metaobject": {"fields": fields}})["metaobjectUpdate"]
    print(json.dumps(d, ensure_ascii=False, indent=2))
    if d["userErrors"]:
        sys.exit(1)


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    if step in ("defs", "all"):
        step_defs()
    gid = None
    if step in ("photo", "all"):
        gid = step_photo()
    if step in ("entry", "all"):
        if gid is None:
            p_ = os.path.join(HERE, "nishikawa_photo_gid.txt")
            if os.path.exists(p_):
                gid = open(p_).read().strip()
        step_entry(gid)
