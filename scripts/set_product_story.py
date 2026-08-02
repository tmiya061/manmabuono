#!/usr/bin/env python3
"""商品説明文を「型」に沿った構成（見出し・チェックリスト・面ブロック）に書き換える

背景:
  本文がテキストの羅列で、見出し・改行が機能していなかった（2026-08-02 オーナー指摘）。
  ペトコトフーズ等の参考EC調査を踏まえた「型」をオーナー承認済み（チキン150g・ぶりのうま煮で試作）:
    h3キャッチ → リード → こんな子におすすめ（✓リスト） → 特徴h4×2-3（各2-4文）
    → 無添加のこだわり（面） → 内容量 → 注記（グレー小）
  文言は既存本文・products.md・recommend-copy-bank.md の範囲で再構成。効能の断定はしない。
  表示には assets/c_product.scss の「商品ストーリー」スタイル（c_prodStory__*）が必要。
  **テーマを本番に push してから --apply すること**（先に本文だけ変えるとスタイルなしで表示される）。

使い方:
  python3 scripts/set_product_story.py             # 点検のみ（preview.md 生成・書き込みなし）
  python3 scripts/set_product_story.py --apply     # 本番の body_html を書き換える
  python3 scripts/set_product_story.py --apply --only <handle>
  python3 scripts/set_product_story.py --revert    # バックアップから復元
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from set_product_seo import load_env, gql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "scripts", "product_story")
PREVIEW = os.path.join(OUTDIR, "preview.md")
BACKUP = os.path.join(OUTDIR, "backup.json")
HISTORY = os.path.join(ROOT, "docs", "product-copy-history.md")
TABLE_BACKUP = os.path.join(ROOT, "scripts", "product_table", "backup.json")  # ①整理前の原文

CERT_DOG_ALL = "総合栄養食（オールステージ）：この商品は、ペットフード公正取引協議会の定める分析試験の結果、総合栄養食の基準を満たすことが証明されています。"
CERT_CAT_MAINT = "総合栄養食（メンテナンス）：この商品は、ペットフード公正取引協議会の定める分析試験の結果、総合栄養食の基準を満たすことが証明されています。"
CERT_OKAZU = "本商品は栄養補完食（おかず）です。総合栄養食と一緒にお与えください。"
CERT_OYATSU = "本商品はおやつです。ご褒美やしつけのトリーツとして適量をお与えください。"
POLICY_DRY = "香料・着色料・合成酸化防止剤（BHA、BHT、エトキシキン）は使用していません。"

IMG_DRY_1 = "https://cdn.shopify.com/s/files/1/0589/6591/7757/files/MB-D-01w.png?v=1710860704"
IMG_DRY_2 = "https://cdn.shopify.com/s/files/1/0589/6591/7757/files/MB-DC_15w.png?v=1710860730"
IMG_FISH = "https://cdn.shopify.com/s/files/1/0589/6591/7757/files/pdWlo6XDpbel5bXrscLK_cuh.webp?v=1710860893"
IMG_CAT = "https://cdn.shopify.com/s/files/1/0589/6591/7757/files/teuxws7M.webp?v=1710860973"
IMG_SOBORO = "https://cdn.shopify.com/s/files/1/0589/6591/7757/files/img07.shop-pro.png?v=1710862576"


def fam_chicken(size):
    return {
        "h3": "九州産銘柄鶏と8種の国産雑穀。<br>だし薫る、毎日の総合栄養食",
        "lead": "九州産銘柄鶏と国内産8種の雑穀米をベースに、国内産野菜12種類・海藻3種類を配合。主食としてこれひとつで、毎日の栄養バランスが整う総合栄養食です。",
        "fit": ["食いつきにムラがある子", "小麦アレルギーが気になる子", "おなかの調子を整えたい子", "子犬からシニアまで全年齢"],
        "imgs_fit": [IMG_DRY_1],
        "sections": [
            ["だしの香りで、食いつきが変わる",
             '香料には頼らず、<span class="c_prodStory__em">鰹節のだしの香り</span>で食欲を引き出します。オイルコーティング処理をしていないので、素材そのままの自然な味わい。食いつきにムラがある子も、だしの香りが食事のスイッチを入れてくれます。'],
            ["アレルギーに配慮した小麦グルテンフリー",
             "食物アレルギーに配慮した<strong>小麦グルテンフリー</strong>。遺伝子組み換えの作物も使用していません。鶏が合わない子には、低アレルゲン素材の魚を主原料にした「だし薫る犬のごはん フィッシュ」もご用意しています。"],
            ["乳酸菌と、野菜12種・海藻3種",
             "乳酸菌を配合し、腸内環境の健康維持をサポート。国内産の野菜12種類と海藻3種類、8種の雑穀米が、毎日のごはんに必要な栄養をバランスよく届けます。"],
        ],
        "policy": POLICY_DRY,
        "meta": f"内容量：{size}",
        "imgs_meta": [IMG_DRY_2],
        "cert": CERT_DOG_ALL,
    }


def fam_fish(size):
    return {
        "h3": "鶏が合わない子に。<br>低アレルゲンの魚が主原料の総合栄養食",
        "lead": "鹿児島県産のかつおと北海道産のたらを主原料にした犬用の総合栄養食。国内産8種の雑穀米と野菜12種類・海藻3種類を合わせ、主食としてこれひとつで毎日の栄養バランスが整います。",
        "fit": ["鶏肉アレルギーが気になる子", "魚が好きな子", "おなかの調子を整えたい子", "子犬からシニアまで全年齢"],
        "imgs_fit": [],
        "sections": [
            ["低アレルゲン素材の魚が主原料",
             '鶏由来の原料が合わない子のために、主原料を<span class="c_prodStory__em">かつおとたら</span>に。食物アレルギーに配慮した小麦グルテンフリーで、遺伝子組み換えの作物も使用していません。'],
            ["DHAと、だしの香り",
             "魚由来のDHAを配合。オイルコーティング処理をしない自然な味わいと、鰹節のだしの香りが食欲を引き出します。食いつきにムラがある子も、だしの香りが食事のスイッチを入れてくれます。"],
            ["乳酸菌と、野菜12種・海藻3種",
             "乳酸菌を配合し、腸内環境の健康維持をサポート。国内産の野菜12種類と海藻3種類が、毎日のごはんに必要な栄養をバランスよく届けます。"],
        ],
        "policy": POLICY_DRY,
        "meta": f"内容量：{size}",
        "imgs_meta": [IMG_FISH],
        "cert": CERT_DOG_ALL,
    }


def fam_cat(size):
    return {
        "h3": "かつお節とまぐろ節、ダブルのだし。<br>猫のための総合栄養食",
        "lead": "九州産銘柄鶏をベースに、かつお節とまぐろ節のダブルの魚だし風味に仕上げた猫用の総合栄養食。契約農家が丹精込めてつくった8種の雑穀と、国内産野菜を配合しています。",
        "fit": ["食いつきにムラがある子", "毛玉を吐きやすい子", "おなかの調子を整えたい子", "成猫からシニアまで"],
        "imgs_fit": [],
        "sections": [
            ["ダブルの魚だしで、食いつきが変わる",
             '香料には頼らず、<span class="c_prodStory__em">かつお節とまぐろ節のダブルだし</span>の香りで食欲を引き出します。オイルコーティング処理をしていない、素材そのままの自然な味わいです。'],
            ["毛玉の排出をサポート",
             "甜菜繊維とイヌリン（水溶性食物繊維）を配合。腸内環境の健康維持と、毛玉の排出をサポートします。毛づくろいの多い子の毎日のごはんにどうぞ。"],
            ["アレルギーに配慮した小麦グルテンフリー",
             "食物アレルギーに配慮した<strong>小麦グルテンフリー</strong>。遺伝子組み換えの作物も使用していません。毎日の主食だからこそ、余計なものを入れずに仕上げています。"],
        ],
        "policy": POLICY_DRY,
        "meta": f"内容量：{size}",
        "imgs_meta": [IMG_CAT],
        "cert": CERT_CAT_MAINT,
    }


def fam_buri(size, is_set=False):
    lead = "京都府漁業協同組合とのご縁から仕入れる、舞鶴の旨味の強い鰤。熱湯で油抜きをしてほぐし、京の一番だしでうま煮に仕上げました。いつものごはんにのせるだけで、だしの香りとうまみが広がります。"
    if is_set:
        lead += "毎日続けたい方・多頭飼いのご家庭には3袋セットをどうぞ。"
    return {
        "h3": "京都舞鶴の鰤を、<br>京の一番だしでうま煮に",
        "lead": lead,
        "fit": ["皮膚・毛並みが気になる子", "体重が気になる子・シニア", "水分をあまり摂らない子", "魚が好きな子"],
        "imgs_fit": [],
        "sections": [
            ["DHA・EPAが豊富な青魚",
             "鰤は青魚の中でもDHA・EPAが豊富な魚。脂肪の酸化を抑えるビタミンEも一緒に摂れます。良質な脂肪は皮膚や毛並みの健康維持に欠かせない栄養素なので、毛づやが気になってきた子の毎日のおかずにぴったりです。"],
            ["うまみはしっかり、あっさり低脂質",
             '調理の最初に熱湯で油抜きをしてから、京の一番だしで炊き上げています。だからだしのうまみはしっかり、<span class="c_prodStory__em">脂質は0.3%</span>。体重が気になる子や、脂っこいものが苦手なシニアの子にも与えやすいおかずです。'],
            ["「ごはんとおかず」で、食事から水分を",
             "水分たっぷりのウェットタイプ。ドライの主食にのせる<strong>「ごはんとおかず」スタイル</strong>は、マンマボーノが提案する食事のかたちです。お水をあまり飲まない子も、毎日の食事から無理なく水分を補えます。"],
        ],
        "policy": "食品添加物は使用していません。素材と京の一番だし、とろみの本葛だけで仕上げています。",
        "meta": f"内容量：{size}",
        "imgs_meta": [],
        "cert": CERT_OKAZU,
    }


def fam_katsuo(size, is_set=False):
    lead = "太平洋で釣り上げられた鹿児島枕崎のかつおを、一度茹でてから京の一番だしで炊き上げたおかずです。いつものごはんにのせるだけで、かつおとだしの香りが広がります。"
    if is_set:
        lead += "毎日続けたい方・多頭飼いのご家庭には3袋セットをどうぞ。"
    return {
        "h3": "鹿児島枕崎のかつおを、<br>京の一番だしで炊き上げて",
        "lead": lead,
        "fit": ["魚が好きな子", "体重が気になる子・シニア", "水分をあまり摂らない子", "いつまでも元気でいてほしい子"],
        "imgs_fit": [],
        "sections": [
            ["ビタミンB12と必須アミノ酸",
             "かつおにはビタミンB12が豊富。疲労回復をサポートすると言われる必須アミノ酸のバリンも含まれ、わんちゃん・猫ちゃんの元気の源になる魚です。",],
            ["うまみはしっかり、あっさり低脂質",
             'かつおを一度茹でてから、京の一番だしで炊き上げています。<span class="c_prodStory__em">脂質は0.4%</span>と低脂質。体重が気になる子や、脂っこいものが苦手な子にも与えやすいおかずです。'],
            ["「ごはんとおかず」で、食事から水分を",
             "水分たっぷりのウェットタイプ。ドライの主食にのせる<strong>「ごはんとおかず」スタイル</strong>は、マンマボーノが提案する食事のかたちです。お水をあまり飲まない子も、毎日の食事から無理なく水分を補えます。"],
        ],
        "policy": "食品添加物は使用していません。素材と京の一番だし、とろみの本葛だけで仕上げています。",
        "meta": f"内容量：{size}",
        "imgs_meta": [],
        "cert": CERT_OKAZU,
    }


def fam_soboro(size, is_set=False):
    lead = "鳥取大山の雪解け水と特別なごはんで、手塩にかけて育てられた「がいな鶏」。グルメも唸る銘柄鶏を食べやすいミンチにし、チキンボーンブロスで炊き上げた、無添加でやさしい味のおかずです。"
    if is_set:
        lead += "毎日続けたい方・多頭飼いのご家庭には3袋セットをどうぞ。"
    return {
        "h3": "大山育ちの「がいな鶏」を、<br>ボーンブロスで炊いたそぼろ煮",
        "lead": lead,
        "fit": ["食が細い子", "お肌・関節が気になる子", "水分をあまり摂らない子", "初めてのおかずに"],
        "imgs_fit": [IMG_SOBORO],
        "sections": [
            ["グルメも唸る、大山の銘柄鶏",
             "がいな鶏は、大山の雪解け水と特別なごはんで育てられた鳥取の銘柄鶏。京都の老舗の衛生的な食品工場で、食べやすいそぼろに仕上げています。"],
            ["コラーゲンたっぷりのボーンブロス",
             '炊き込みに使うのは、鶏がらを長時間炊いた<span class="c_prodStory__em">チキンボーンブロス</span>。コラーゲンが豊富で、お肌や関節の健康維持を支えます。'],
            ["「ごはんとおかず」で、食事から水分を",
             "水分たっぷりのウェットタイプ。ドライの主食にのせる<strong>「ごはんとおかず」スタイル</strong>は、マンマボーノが提案する食事のかたちです。お水をあまり飲まない子も、毎日の食事から無理なく水分を補えます。"],
        ],
        "policy": "食品添加物は使用していません。素材は鶏肉と鶏だし、とろみの本葛だけです。",
        "meta": f"内容量：{size}",
        "imgs_meta": [],
        "cert": CERT_OKAZU,
    }


def fam_shika(size, is_set=False):
    lead = "京都笠置で捕獲された天然の鹿肉と、大根・さつま芋などの無農薬野菜を、チキンボーンブロスのお出汁でことこと煮込みました。体を温めたい季節にぴったりのおかずです。"
    if is_set:
        lead += "毎日続けたい方・多頭飼いのご家庭には3袋セットをどうぞ。"
    return {
        "h3": "京都笠置の天然鹿肉と無農薬野菜を、<br>ことこと煮込んで",
        "lead": lead,
        "fit": ["寒い季節、冷えが気になる子", "体重が気になる子", "初めてのジビエに", "犬にも猫にも"],
        "imgs_fit": [],
        "sections": [
            ["低脂質・高たんぱくな天然鹿肉",
             '鹿肉は<span class="c_prodStory__em">低脂質・高たんぱく</span>で、鉄分も豊富なヘルシーな食材。しっかりとした血抜き処理で臭みが少なく、初めてのジビエにも取り入れやすいおかずです。'],
            ["寒い季節の、温活おかず",
             "人間と同じように、体を温めることは寒い季節の健康維持に大切と言われます。温かいだしで煮込んだ鹿肉と野菜を、足裏が冷たくなる時期のごはんにどうぞ。"],
            ["「ごはんとおかず」で、食事から水分を",
             "水分たっぷりのウェットタイプ。ドライの主食にのせる<strong>「ごはんとおかず」スタイル</strong>は、マンマボーノが提案する食事のかたちです。お水をあまり飲まない子も、毎日の食事から無理なく水分を補えます。"],
        ],
        "policy": "食品添加物は使用していません。素材は鹿肉と無農薬野菜、鶏だし、とろみの本葛だけです。",
        "meta": f"内容量：{size}",
        "imgs_meta": [],
        "cert": CERT_OKAZU,
    }


def fam_bonebroth(size):
    return {
        "h3": "鶏がらと丸鶏だけを、<br>長時間炊いたスープ",
        "lead": "素材は鶏骨と鶏肉のみ。長時間かけて炊き出したチキンボーンブロスは、いつものごはんにかけるだけで、香りとうまみ、そして水分を一緒に摂れるスープです。",
        "fit": ["水分をあまり摂らない子", "お肌・関節が気になる子", "食いつきにムラがある子", "シニアの子"],
        "imgs_fit": [],
        "sections": [
            ["鶏コラーゲンたっぷり",
             '鶏がらを長時間炊くことで溶け出す<span class="c_prodStory__em">鶏コラーゲン</span>が豊富。お肌や関節の健康維持のために、毎日のごはんに取り入れやすいスープです。'],
            ["かけるだけで、食事から水分を",
             "わんちゃん・猫ちゃんの健康維持には、食事から摂れる水分がとても大切。ドライフードにかけるだけで香りが立ち、食いつきと水分補給を同時にサポートします。"],
        ],
        "policy": "食品添加物は使用していません。素材は鶏骨と鶏肉だけです。",
        "meta": f"内容量：{size}",
        "imgs_meta": [],
        "cert": CERT_OKAZU,
    }


def fam_dashi(size):
    return {
        "h3": "昆布、鰹節、椎茸。<br>京都の軟水でひいた一番だし",
        "lead": "京都の軟水に昆布・鰹節・乾燥椎茸で丁寧にひいた一番だし。思わず飼い主さんも飲みたくなる香りです。ドライフードにかけるだけで、食欲のスイッチが入ります。",
        "fit": ["食いつきにムラがある子", "水分をあまり摂らない子", "体重が気になる子", "食が細い子・シニア"],
        "imgs_fit": [],
        "sections": [
            ["食欲スイッチの入る香り",
             'だしの香りは、わんちゃん・猫ちゃんの<span class="c_prodStory__em">食欲のスイッチ</span>。食いつきにムラがある子や食の細い子のごはんに、かけるだけで香りが立ちます。'],
            ["低カロリーで、食事から水分を",
             "100gあたり14kcalと低カロリー。体重が気になる子のかさ増しにも使いやすく、毎日の食事から無理なく水分を補えます。"],
        ],
        "policy": "食品添加物は使用していません。素材は鰹節と昆布、椎茸だけです。",
        "meta": f"内容量：{size}",
        "imgs_meta": [],
        "cert": CERT_OKAZU,
    }


STORIES = {
    "だし薫る犬のごはん-チキン-150g": fam_chicken("150g"),
    "だし薫る犬のごはん-チキン": fam_chicken("800g"),
    "だし薫る犬のごはん-フィッシュ-150g": fam_fish("150g"),
    "だし薫る犬のごはん-フィッシュ-800g": fam_fish("800g"),
    "ダブルだし猫のごはん-チキン-150g": fam_cat("150g"),
    "ダブルだし猫のごはん-チキン-800g": fam_cat("800g"),
    "舞鶴-ぶりのうま煮1袋": fam_buri("120g"),
    "舞鶴-ぶりのうま煮3袋": fam_buri("120g×3袋", is_set=True),
    "枕崎-かつおのうま煮1袋": fam_katsuo("120g"),
    "枕崎-かつおのうま煮3袋": fam_katsuo("120g×3袋", is_set=True),
    "地鶏のそぼろ煮1袋": fam_soboro("120g"),
    "地鶏のそぼろ煮3袋": fam_soboro("120g×3袋", is_set=True),
    "京都笠置-鹿肉と無農薬野菜の煮込み": fam_shika("70g"),
    "京都笠置-鹿肉と無農薬野菜の煮込み3袋": fam_shika("70g×3袋", is_set=True),
    "チキンボーンブロス": fam_bonebroth("100g×2袋"),
    "チキンボーンブロス5袋": fam_bonebroth("100g×5袋"),
    "京の一番だし": fam_dashi("100g×2袋"),
    "京の一番だし5袋": fam_dashi("100g×5袋"),
    "無塩-鹿児島枕崎-おつお削り節": {
        "h3": "塩分0.1%。<br>犬と猫のための、かつお削り節",
        "lead": "鹿児島枕崎のかつおを、塩を使わずに加工した削り節。塩分量はわずか0.1%です。いつものごはんにふりかけるだけで、かつおの香りが立ち、食いつきが変わります。",
        "fit": ["食いつきにムラがある子", "塩分が気になる子", "トッピングが好きな子", "手作りごはんの子"],
        "imgs_fit": [],
        "sections": [
            ["「無塩」へのこだわり",
             'かつおを釣り上げて冷凍する際、勢いのある冷風で表面の塩水を吹き飛ばし、加工の段階でも塩を使いません。だから<span class="c_prodStory__em">塩分量0.1%</span>。塩分が気になるわんちゃん・猫ちゃんにも与えやすい削り節です。'],
            ["ふりかけて、だしを取って",
             "そのままふりかけるほか、お湯にひとつまみ入れて3〜5分置けば、かつおだしが取れます。だしをドライフードにかければ、香りと一緒に水分補給もできます。"],
        ],
        "policy": "食品添加物は使用していません。原材料はかつおのふしだけです。",
        "meta": "内容量：20g",
        "imgs_meta": [],
        "cert": CERT_OKAZU,
    },
    "広島呉-ちりめんじゃこのふりかけ": {
        "h3": "無加塩で釜揚げした、<br>広島呉のちりめんじゃこ",
        "lead": "人間用のちりめんじゃこは塩ゆでで作られるため、わんちゃん・猫ちゃんには塩分過多になりがち。マンマボーノは、無加塩のお湯で釜揚げして乾燥させた犬と猫のためのおじゃこを、広島呉の職人さんに作ってもらいました。",
        "fit": ["塩分が気になる子", "カルシウムを補いたい子", "食いつきにムラがある子", "成長期の子"],
        "imgs_fit": [],
        "sections": [
            ["塩分を最小限に",
             '通常は塩分を含んだお湯で釜揚げされるおじゃこを、<span class="c_prodStory__em">無加塩のお湯</span>で釜揚げ。腎臓や心臓に負担をかけたくない子にも与えやすいふりかけです。'],
            ["カルシウムとミネラルが豊富",
             "ちりめんじゃこには、骨や筋肉の生成に欠かせないカルシウムや、体内で作れないミネラルが豊富。いつものごはんに少しふりかけるだけで、香りにつられて食事に興味のない子も喜んで食べてくれます。"],
        ],
        "policy": "食品添加物は使用していません。原材料はかたくちいわしだけです。",
        "meta": "内容量：35g",
        "imgs_meta": [],
        "cert": CERT_OKAZU,
    },
    "犬と猫のおやつ-京都笠置-熟成鹿肉": {
        "h3": "京都笠置の天然鹿肉を、<br>ドライエイジングでおやつに",
        "lead": "京都府相楽郡笠置で捕獲された天然の鹿肉を使ったおやつです。しっかりとした血抜き処理で臭みが少なく、赤身が多くあっさりとした味わい。肉質は繊細で柔らかです。",
        "fit": ["ご褒美・しつけのトリーツに", "硬いおやつが苦手な子・シニア", "体重が気になる子", "添加物が気になる子"],
        "imgs_fit": [],
        "sections": [
            ["低カロリー・高たんぱくなジビエ",
             '鹿肉は<span class="c_prodStory__em">低カロリーで高たんぱく</span>、鉄分も豊富なヘルシー食材です。おやつの与えすぎや体重が気になる子にも取り入れやすく、毎日のしつけのトリーツにぴったりです。'],
            ["ドライエイジングで、からだにやさしく",
             "ジャーキーのような水分の少ない乾燥肉とは違い、ドライエイジング加工で水分を残した、やわらかい仕上がり。噛む力が弱くなってきたシニアの子にも与えやすいおやつです。"],
        ],
        "policy": "食品添加物は使用していません。原材料は鹿肉だけです。",
        "meta": "内容量：30g",
        "imgs_meta": [],
        "cert": CERT_OYATSU,
    },
    "長野信州-熟成黒毛和牛": {
        "h3": "信州プレミアム牛を、<br>贅沢にドライエイジングのおやつに",
        "lead": "長野県が独自に定めた基準を満たした黒毛和種だけが認定される「信州プレミアム牛」。サシの等級とオレイン酸含有率の両方が基準を超えた、風味も口溶けも別格の牛肉をおやつにしました。",
        "fit": ["特別な日のご褒美に", "硬いおやつが苦手な子・シニア", "食いつきにムラがある子", "添加物が気になる子"],
        "imgs_fit": [],
        "sections": [
            ["基準を超えたものだけの、認定和牛",
             '脂肪交雑（サシ）の等級と<span class="c_prodStory__em">オレイン酸含有率</span>、両方の基準を満たした黒毛和種だけが名乗れる信州プレミアム牛。風味と口溶けの良さは、グルメな子にこそ伝わります。'],
            ["ドライエイジングで、からだにやさしく",
             "ジャーキーのような水分の少ない乾燥肉とは違い、ドライエイジング加工で水分を残した、やわらかい仕上がり。噛む力が弱くなってきたシニアの子にも与えやすいおやつです。"],
        ],
        "policy": "食品添加物は使用していません。原材料は牛肉だけです。",
        "meta": "内容量：30g",
        "imgs_meta": [],
        "cert": CERT_OYATSU,
    },
    "犬と猫のおやつ-京都舞鶴-熟成鰤-30ｇ": {
        "h3": "京都舞鶴港の鰤を、<br>そのままドライエイジングのおやつに",
        "lead": "京都舞鶴港で水揚げされた鰤を使ったおやつです。鰤はたんぱく質、DHA・EPA、ビタミンB群・ビタミンDなどを豊富に含む、栄養価の高い魚です。",
        "fit": ["魚が好きな子", "硬いおやつが苦手な子・シニア", "皮膚・毛並みが気になる子", "添加物が気になる子"],
        "imgs_fit": [],
        "sections": [
            ["DHA・EPAが豊富な青魚のおやつ",
             '青魚の中でも<span class="c_prodStory__em">DHA・EPAが豊富</span>な鰤。良質な脂肪と一緒にビタミンB群・ビタミンDも摂れる、健康維持をサポートするおやつです。'],
            ["ドライエイジングで、からだにやさしく",
             "ジャーキーのような水分の少ない乾燥肉とは違い、ドライエイジング加工で水分を残した、やわらかい仕上がり。噛む力が弱くなってきたシニアの子にも与えやすいおやつです。"],
        ],
        "policy": "食品添加物は使用していません。原材料は鰤だけです。",
        "meta": "内容量：30g",
        "imgs_meta": [],
        "cert": CERT_OYATSU,
    },
    "犬と猫のおやつ-鳥取大山-熟成がいな鶏-30ｇ": {
        "h3": "大山育ちの「がいな鶏」を、<br>じっくり熟成させたおやつに",
        "lead": "鳥取大山で長期飼育された銘柄鶏「がいな鶏」を使ったおやつです。鶏肉は高たんぱくで、ビタミンB群やミネラルも豊富。毎日のトリーツにぴったりの素材です。",
        "fit": ["ご褒美・しつけのトリーツに", "体重が気になる子", "硬いおやつが苦手な子・シニア", "添加物が気になる子"],
        "imgs_fit": [],
        "sections": [
            ["高たんぱく・低脂質",
             'たんぱく質30.0%に対して<span class="c_prodStory__em">脂質は2.3%</span>。おやつの与えすぎが気になる子や、体重管理中の子のトリーツに取り入れやすい数字です。'],
            ["ドライエイジングで、からだにやさしく",
             "ジャーキーのような水分の少ない乾燥肉とは違い、ドライエイジング加工で水分を残した、やわらかい仕上がり。噛む力が弱くなってきたシニアの子にも与えやすいおやつです。"],
        ],
        "policy": "食品添加物は使用していません。原材料は鶏肉だけです。",
        "meta": "内容量：30g",
        "imgs_meta": [],
        "cert": CERT_OYATSU,
    },
}


def build_html(s):
    out = []
    out.append("<h3>%s</h3>" % s["h3"])
    out.append("<p>%s</p>" % s["lead"])
    out.append('<div class="c_prodStory__fit">')
    out.append('  <p class="c_prodStory__fit-title">こんな子におすすめ</p>')
    out.append("  <ul>")
    for item in s["fit"]:
        out.append("    <li>%s</li>" % item)
    out.append("  </ul>")
    out.append("</div>")
    for url in s.get("imgs_fit", []):
        out.append('<img src="%s" alt="">' % url)
    for h4, body in s["sections"]:
        out.append("<h4>%s</h4>" % h4)
        out.append("<p>%s</p>" % body)
    out.append('<div class="c_prodStory__policy">')
    out.append('  <p class="c_prodStory__policy-title">無添加のこだわり</p>')
    out.append("  <p>%s</p>" % s["policy"])
    out.append("</div>")
    out.append('<p class="c_prodStory__meta">%s</p>' % s["meta"])
    for url in s.get("imgs_meta", []):
        out.append('<img src="%s" alt="">' % url)
    if s.get("cert"):
        out.append('<p class="c_prodStory__cert">%s</p>' % s["cert"])
    return "\n".join(out)


def to_plain(html_str):
    """本文HTMLを履歴用のプレーンテキストに変換する"""
    s = re.sub(r"<img[^>]*src=\"(data:[^\"]{40})[^\"]*\"[^>]*>", r"〔画像（埋め込み）〕", html_str or "")
    s = re.sub(r"<img[^>]*src=\"([^\"]+)\"[^>]*>", r"〔画像〕", s)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</(p|div|h\d|li)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    import html as H
    s = H.unescape(s)
    lines = [re.sub(r"[ \t　]+", " ", ln).strip() for ln in s.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def write_history(backup):
    """どの文章からどの文章に変わったかの履歴を docs/ に残す（オーナー要望 2026-08-02）"""
    original = {}
    if os.path.exists(TABLE_BACKUP):
        with open(TABLE_BACKUP) as f:
            original = {h: rec.get("body_html", "") for h, rec in json.load(f).items()}
    with open(HISTORY, "w") as f:
        f.write("# 商品説明文の変更履歴（2026-08-02 一括改修）\n\n")
        f.write("本文を2段階で改修した記録。**復元は各スクリプトの --revert**。\n\n")
        f.write("1. **整理**（`set_product_table.py`）: 仕様情報を metafield テーブルへ移し、翻訳由来のHTML汚れを除去\n")
        f.write("2. **型適用**（`set_product_story.py`）: 見出し・チェックリスト・面ブロックの「型」で再構成（参考EC調査に基づきオーナー承認済み）\n\n")
        f.write("表現の変更点: 効能断定（〜予防・治る等）は表現ルールに従い「〜と言われる」「〜な子に」へ言い換え。\n\n")
        for h, s in STORIES.items():
            f.write("---\n\n## `%s`\n\n" % h)
            if h in original:
                f.write("### 元の本文（改修前・原文ママ）\n\n```\n%s\n```\n\n" % to_plain(original[h]))
            if h in backup:
                f.write("### 整理後（仕様テーブル分離後）\n\n```\n%s\n```\n\n" % to_plain(backup[h]["body_html"]))
            f.write("### 型適用後（現行）\n\n```\n%s\n```\n\n" % to_plain(build_html(s)))
    print("history: %s" % HISTORY)


FETCH_ONE = """
query($handle: String!) {
  productByIdentifier(identifier: {handle: $handle}) { id handle title descriptionHtml }
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
            r = gql(UPDATE, {"product": {"id": rec["id"], "descriptionHtml": rec["body_html"]}})["productUpdate"]
            print("revert", h, r["userErrors"] or "OK")
        return

    # プレビュー生成
    with open(PREVIEW, "w") as f:
        f.write("# 商品ストーリー原稿プレビュー（%d商品）\n\n" % len(STORIES))
        f.write("> `python3 scripts/set_product_story.py` により生成。--apply 前に目視確認する。\n\n")
        for h, s in STORIES.items():
            f.write("---\n\n## `%s`\n\n" % h)
            f.write("```html\n%s\n```\n\n" % build_html(s))
    print("preview: %s（%d商品）" % (PREVIEW, len(STORIES)))

    if not args.apply:
        for h, s in STORIES.items():
            lens = [len(re.sub("<[^>]+>", "", b)) for _, b in s["sections"]]
            print("  %-40s h4×%d 本文%s字" % (h[:40], len(s["sections"]), "/".join(map(str, lens))))
        print("\n書き込みなし。適用は --apply。")
        return

    backup = {}
    if os.path.exists(BACKUP):
        with open(BACKUP) as f:
            backup = json.load(f)
    for h, s in STORIES.items():
        if args.only and h != args.only:
            continue
        p = gql(FETCH_ONE, {"handle": h})["productByIdentifier"]
        if not p:
            print("SKIP（商品が見つからない）", h)
            continue
        backup.setdefault(h, {"id": p["id"], "body_html": p["descriptionHtml"]})
        with open(BACKUP, "w") as f:
            json.dump(backup, f, ensure_ascii=False, indent=1)
        r = gql(UPDATE, {"product": {"id": p["id"], "descriptionHtml": build_html(s)}})["productUpdate"]
        print("apply", h, r["userErrors"] or "OK")
    write_history(backup)


if __name__ == "__main__":
    main()
