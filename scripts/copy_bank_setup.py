#!/usr/bin/env python3
"""訴求文バンクをShopifyに一括登録するスクリプト（冪等・再実行可）

やること:
1. 商品メタフィールド定義 custom.recommend_copy（なければ作成）
2. メタオブジェクト定義 product_recommendation（なければ作成）
3. 記事メタフィールド定義 custom.recommendations / custom.related_products（なければ作成）
4. 商品にデフォルトキャッチを書き込み（docs/recommend-copy-bank.md ①）
5. おすすめ商品セットのエントリーをupsert（docs/recommend-copy-bank.md ②）

実行: python3 scripts/copy_bank_setup.py
必要: .env に SHOPIFY_CLIENT_ID / SHOPIFY_CLIENT_SECRET / SHOPIFY_STORE_DOMAIN
"""
import json
import os
import sys
import urllib.request
import urllib.parse

API_VERSION = "2026-07"


def load_env():
    path = os.path.join(os.path.dirname(__file__), "..", ".env")
    with open(path) as f:
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


TOKEN = None


def gql(query, variables=None):
    global TOKEN
    if TOKEN is None:
        TOKEN = get_token()
    domain = os.environ["SHOPIFY_STORE_DOMAIN"]
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        f"https://{domain}/admin/api/{API_VERSION}/graphql.json", data=body,
        headers={"Content-Type": "application/json", "X-Shopify-Access-Token": TOKEN})
    with urllib.request.urlopen(req) as r:
        res = json.load(r)
    if res.get("errors"):
        raise RuntimeError(json.dumps(res["errors"], ensure_ascii=False))
    return res["data"]


# ============================================================
# データ：商品デフォルトキャッチ（handle → copy）
# ============================================================
PRODUCT_COPIES = {
    "だし薫る犬のごはん-チキン": "だしの香りで食いつきが変わる、無添加の総合栄養食",
    "だし薫る犬のごはん-チキン-150g": "だしの香りで食いつきが変わる、無添加の総合栄養食",
    "だし薫る犬のごはん-フィッシュ-800g": "鶏が合わない子に。低アレルゲンの魚が主原料",
    "だし薫る犬のごはん-フィッシュ-150g": "鶏が合わない子に。低アレルゲンの魚が主原料",
    "ダブルだし猫のごはん-チキン-800g": "かつお＋まぐろのダブルだし。毛玉ケアも配合",
    "ダブルだし猫のごはん-チキン-150g": "かつお＋まぐろのダブルだし。毛玉ケアも配合",
    "地鶏のそぼろ煮1袋": "いつものごはんにのせるだけの無添加おかず",
    "地鶏のそぼろ煮3袋": "いつものごはんにのせるだけの無添加おかず",
    "舞鶴-ぶりのうま煮1袋": "DHA・EPAたっぷり。皮膚・毛並みが気になる子に",
    "舞鶴-ぶりのうま煮3袋": "DHA・EPAたっぷり。皮膚・毛並みが気になる子に",
    "枕崎-かつおのうま煮1袋": "低脂質であっさり。魚好きの子の定番おかず",
    "枕崎-かつおのうま煮3袋": "低脂質であっさり。魚好きの子の定番おかず",
    "京都笠置-鹿肉と無農薬野菜の煮込み": "低脂質な天然鹿肉。体を温めたい季節に",
    "京都笠置-鹿肉と無農薬野菜の煮込み3袋": "低脂質な天然鹿肉。体を温めたい季節に",
    "犬と猫のプレミアム料理-京のだし薫る-親子丼の素": "特別な日に。溶き卵で仕上げる本格親子丼",
    "犬と猫のプレミアム料理-京都舞笠置天然鹿肉-煮込みハンバーグ": "天然鹿肉100%の贅沢ハンバーグ",
    "京都舞鶴港-鰤と大根の炊いたん": "だしが染みた、京都舞鶴の鰤の炊き合わせ",
    "京の一番だし": "かけるだけで水分補給。食欲スイッチの入るだし",
    "京の一番だし5袋": "かけるだけで水分補給。食欲スイッチの入るだし",
    "チキンボーンブロス": "コラーゲンたっぷり。関節が気になる子の水分補給に",
    "チキンボーンブロス5袋": "コラーゲンたっぷり。関節が気になる子の水分補給に",
    "無塩-鹿児島枕崎-おつお削り節": "ふりかけるだけで食いつきUP。まず試すならこれ",
    "広島呉-ちりめんじゃこのふりかけ": "無加塩だから安心。カルシウム補給のふりかけ",
    "長野信州-熟成黒毛和牛": "信州プレミアム牛の、体にやさしい熟成おやつ",
    "犬と猫のおやつ-京都笠置-熟成鹿肉": "低カロリー高タンパク。ヘルシーなご褒美",
    "犬と猫のおやつ-京都舞鶴-熟成鰤-30ｇ": "魚好きの子に。DHA・EPAが摂れるおやつ",
    "犬と猫のおやつ-鳥取大山-熟成がいな鶏-30ｇ": "30gで40kcal。ダイエット中のご褒美に",
    "国内産-吉野本葛": "とろみでお腹にやさしく。下痢しやすい子に",
    "旬の無農薬野菜セット-送料込み": "手作りごはんデビューに必要なものが全部届く",
    "チキンボーンブロス2袋-旬の無農薬野菜セット-送料込み": "手作りごはんデビューに必要なものが全部届く",
    "dog-trial-set": "主食もおかずも。まるごと試せる初回限定セット",
    "cat-trial-set": "猫ちゃんの「ごはんとおかず」を試せる初回セット",
    "食事代行サービス": "管理栄養士がうちの子専用ごはんを設計",
}

# ============================================================
# データ：おすすめ商品セット（エントリーhandle → (商品handle, 訴求文)）
# ============================================================
RECOMMENDATIONS = {
    # trouble（食べない・好き嫌い）
    "katsuobushi-trouble": ("無塩-鹿児島枕崎-おつお削り節", "いつものフードにひとふり。香りで「食べない」が変わる第一歩"),
    "ichibandashi-trouble": ("京の一番だし", "フードにかけるだけ。だしの香りで食欲スイッチを入れる"),
    "jako-trouble": ("広島呉-ちりめんじゃこのふりかけ", "香ばしいじゃこの香りで、食に興味のない子も寄ってくる"),
    "buri-trouble": ("舞鶴-ぶりのうま煮1袋", "ドライに飽きた子に。焼き鰤とだしの香りは別格"),
    "trial-dog-trouble": ("dog-trial-set", "何なら食べるか分からない…をまとめて試せる初回セット"),
    "trial-cat-trouble": ("cat-trial-set", "偏食の猫ちゃんに。ドライもおかずも少量ずつ試せる"),
    # health（健康・症状別ケア）
    "ichibandashi-health": ("京の一番だし", "「食事からの水分」を今日から。飲まない子の水分補給に"),
    "bonebroth-joint": ("チキンボーンブロス", "コラーゲン豊富なスープで、シニアの関節ケアをサポート"),
    "kuzu-onaka": ("国内産-吉野本葛", "とろみが胃腸にやさしい。お腹をこわしやすい子の食事に"),
    "gainadori-diet": ("犬と猫のおやつ-鳥取大山-熟成がいな鶏-30ｇ", "ダイエット中でもご褒美を。高タンパク低脂質の40kcal"),
    "shika-diet": ("京都笠置-鹿肉と無農薬野菜の煮込み", "低脂質な鹿肉おかずで、満足感はそのままカロリーオフ"),
    "neko-kedama": ("ダブルだし猫のごはん-チキン-800g", "甜菜繊維とイヌリンで毛玉の排出をサポートする主食"),
    "buri-hifu": ("舞鶴-ぶりのうま煮1袋", "DHA・EPAで皮膚・毛並みが気になる子の食事ケア"),
    "fish-allergy": ("だし薫る犬のごはん-フィッシュ-800g", "鶏や牛が合わない子に。低アレルゲンの魚が主原料"),
    # feeding（与え方・食事管理）
    "okazu-feeding": ("地鶏のそぼろ煮1袋", "「ドライ＋おかず」スタイルの入門に。のせるだけで完成"),
    "ichibandashi-feeding": ("京の一番だし", "ふやかし・トッピングに万能。混ぜ方に迷ったらまずだし"),
    "katsuobushi-feeding": ("無塩-鹿児島枕崎-おつお削り節", "お湯を注げばだしも取れる、一番手軽なトッピング"),
    "bonebroth-feeding": ("チキンボーンブロス", "ふやかしにも手作りにも。冷凍ストックできる万能スープ"),
    # choose（選び方・おすすめ）
    "dry-dog-choose": ("だし薫る犬のごはん-チキン", "無添加・グルテンフリー・国産。迷ったらこの総合栄養食"),
    "dry-cat-choose": ("ダブルだし猫のごはん-チキン-800g", "猫の食いつきを考え抜いた、ダブルだしの総合栄養食"),
    "trial-dog-choose": ("dog-trial-set", "いきなり大袋は不安…に応える初回限定3,300円"),
    "trial-cat-choose": ("cat-trial-set", "切り替え前に少量で相性チェックできる初回セット"),
    "premium-gift": ("犬と猫のプレミアム料理-京都舞笠置天然鹿肉-煮込みハンバーグ", "誕生日・記念日のごちそうに。天然鹿肉100%"),
    # storage（保存・容器）
    "okazu-storage": ("地鶏のそぼろ煮3袋", "常温1年保存OK。ローリングストック・防災食にも"),
    "katsuobushi-storage": ("無塩-鹿児島枕崎-おつお削り節", "常温保存できて開封後も使い切りやすい20g"),
    # homemade（手作り・レシピ）
    "yasai-homemade": ("旬の無農薬野菜セット-送料込み", "野菜もだしも葛も届く。月1手作りごはんの全部入り"),
    "kuzu-homemade": ("国内産-吉野本葛", "仕上げのとろみはこれ。手作りごはんの必需品"),
    "bonebroth-homemade": ("チキンボーンブロス", "手作りのベーススープに。鶏がらを長時間炊いた本物"),
    "daiko-homemade": ("食事代行サービス", "作ってあげたいけど時間がない…は管理栄養士に任せる手も"),
    # basics（基礎知識）
    "dry-dog-basics": ("だし薫る犬のごはん-チキン", "無添加表示の見本のような原材料リスト、見てみてください"),
    "trial-dog-basics": ("dog-trial-set", "「総合栄養食＋おかず」の考え方をセットで体験"),
    # senior（シニア）
    "bonebroth-senior": ("チキンボーンブロス", "噛む力・飲む量が落ちてきた子の水分・栄養補給に"),
    "okazu-senior": ("京都笠置-鹿肉と無農薬野菜の煮込み", "柔らかく低脂質。シニアの胃腸にやさしいおかず"),
    "buri-senior": ("京都舞鶴港-鰤と大根の炊いたん", "だしが染みて柔らかい。食が細くなった子のごちそう"),
    # puppy / kitten
    "ichibandashi-puppy": ("京の一番だし", "ふやかしごはんの卒業期に。だしで食トレをスムーズに"),
    "trial-cat-kitten": ("cat-trial-set", "子猫のうちに色々な食感に慣らす、はじめてセット"),
}


def ensure_product_metafield_def():
    q = """query { metafieldDefinitions(first: 5, ownerType: PRODUCT, namespace: "custom", key: "recommend_copy") { nodes { id } } }"""
    if gql(q)["metafieldDefinitions"]["nodes"]:
        print("[skip] 商品メタフィールド custom.recommend_copy は定義済み")
        return
    m = """mutation($def: MetafieldDefinitionInput!) {
      metafieldDefinitionCreate(definition: $def) {
        createdDefinition { id }
        userErrors { field message code }
      }
    }"""
    res = gql(m, {"def": {
        "name": "おすすめキャッチ", "namespace": "custom", "key": "recommend_copy",
        "type": "single_line_text_field", "ownerType": "PRODUCT", "pin": True,
    }})["metafieldDefinitionCreate"]
    if res["userErrors"]:
        raise RuntimeError(res["userErrors"])
    print("[作成] 商品メタフィールド定義 custom.recommend_copy")


def ensure_metaobject_def():
    q = """query { metaobjectDefinitionByType(type: "product_recommendation") { id } }"""
    node = gql(q)["metaobjectDefinitionByType"]
    if node:
        print("[skip] メタオブジェクト定義 product_recommendation は定義済み")
        return node["id"]
    m = """mutation($def: MetaobjectDefinitionCreateInput!) {
      metaobjectDefinitionCreate(definition: $def) {
        metaobjectDefinition { id }
        userErrors { field message code }
      }
    }"""
    res = gql(m, {"def": {
        "name": "おすすめ商品セット", "type": "product_recommendation",
        "displayNameKey": "copy",
        "access": {"storefront": "PUBLIC_READ"},
        "fieldDefinitions": [
            {"key": "product", "name": "商品", "type": "product_reference"},
            {"key": "copy", "name": "訴求文", "type": "single_line_text_field"},
        ],
    }})["metaobjectDefinitionCreate"]
    if res["userErrors"]:
        raise RuntimeError(res["userErrors"])
    print("[作成] メタオブジェクト定義 product_recommendation")
    return res["metaobjectDefinition"]["id"]


def ensure_article_metafield_defs(metaobject_def_id):
    defs = [
        {
            "name": "おすすめ商品セット", "namespace": "custom", "key": "recommendations",
            "type": "list.metaobject_reference", "ownerType": "ARTICLE", "pin": True,
            "validations": [{"name": "metaobject_definition_id", "value": metaobject_def_id}],
        },
        {
            "name": "おすすめ商品", "namespace": "custom", "key": "related_products",
            "type": "list.product_reference", "ownerType": "ARTICLE", "pin": True,
        },
    ]
    q = """query($key: String!) { metafieldDefinitions(first: 5, ownerType: ARTICLE, namespace: "custom", key: $key) { nodes { id } } }"""
    m = """mutation($def: MetafieldDefinitionInput!) {
      metafieldDefinitionCreate(definition: $def) {
        createdDefinition { id }
        userErrors { field message code }
      }
    }"""
    for d in defs:
        if gql(q, {"key": d["key"]})["metafieldDefinitions"]["nodes"]:
            print(f"[skip] 記事メタフィールド custom.{d['key']} は定義済み")
            continue
        res = gql(m, {"def": d})["metafieldDefinitionCreate"]
        if res["userErrors"]:
            raise RuntimeError(res["userErrors"])
        print(f"[作成] 記事メタフィールド定義 custom.{d['key']}")


def fetch_products():
    q = """query($cursor: String) {
      products(first: 100, after: $cursor) {
        nodes { id handle title }
        pageInfo { hasNextPage endCursor }
      }
    }"""
    products, cursor = {}, None
    while True:
        data = gql(q, {"cursor": cursor})["products"]
        for n in data["nodes"]:
            products[n["handle"]] = n
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]
    return products


def set_product_copies(products):
    metafields, missing = [], []
    for handle, copy in PRODUCT_COPIES.items():
        p = products.get(handle)
        if not p:
            missing.append(handle)
            continue
        metafields.append({
            "ownerId": p["id"], "namespace": "custom", "key": "recommend_copy",
            "type": "single_line_text_field", "value": copy,
        })
    m = """mutation($metafields: [MetafieldsSetInput!]!) {
      metafieldsSet(metafields: $metafields) {
        metafields { id }
        userErrors { field message code }
      }
    }"""
    done = 0
    for i in range(0, len(metafields), 25):
        res = gql(m, {"metafields": metafields[i:i+25]})["metafieldsSet"]
        if res["userErrors"]:
            raise RuntimeError(res["userErrors"])
        done += len(res["metafields"])
    print(f"[書込] 商品キャッチ {done}件 設定完了")
    if missing:
        print(f"[警告] handleが見つからない商品: {missing}")


def upsert_recommendations(products):
    m = """mutation($handle: MetaobjectHandleInput!, $metaobject: MetaobjectUpsertInput!) {
      metaobjectUpsert(handle: $handle, metaobject: $metaobject) {
        metaobject { id handle }
        userErrors { field message code }
      }
    }"""
    done, missing = 0, []
    for entry_handle, (product_handle, copy) in RECOMMENDATIONS.items():
        p = products.get(product_handle)
        if not p:
            missing.append(f"{entry_handle} -> {product_handle}")
            continue
        res = gql(m, {
            "handle": {"type": "product_recommendation", "handle": entry_handle},
            "metaobject": {"fields": [
                {"key": "product", "value": p["id"]},
                {"key": "copy", "value": copy},
            ]},
        })["metaobjectUpsert"]
        if res["userErrors"]:
            raise RuntimeError(f"{entry_handle}: {res['userErrors']}")
        done += 1
    print(f"[登録] おすすめ商品セット {done}件 upsert完了")
    if missing:
        print(f"[警告] 商品が見つからないエントリー: {missing}")


def main():
    load_env()
    print(f"対象ストア: {os.environ['SHOPIFY_STORE_DOMAIN']}")
    ensure_product_metafield_def()
    def_id = ensure_metaobject_def()
    if def_id is None:
        def_id = gql("""query { metaobjectDefinitionByType(type: "product_recommendation") { id } }""")["metaobjectDefinitionByType"]["id"]
    ensure_article_metafield_defs(def_id)
    products = fetch_products()
    print(f"[取得] 商品 {len(products)}件")
    set_product_copies(products)
    upsert_recommendations(products)
    print("\n完了。")


if __name__ == "__main__":
    main()
