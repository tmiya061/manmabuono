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
    "katsuobushi-trouble": ("無塩-鹿児島枕崎-おつお削り節", "「食べない」対策の最初の一手に。ふりかけるだけで香りが立ち、食いつきが変わります"),
    "ichibandashi-trouble": ("京の一番だし", "記事で紹介した「香りで食欲を誘う」を、いつものフードにかけるだけで試せます"),
    "jako-trouble": ("広島呉-ちりめんじゃこのふりかけ", "かつお節がダメだった子の二の矢に。香ばしいじゃこの香りで興味を引きます"),
    "buri-trouble": ("舞鶴-ぶりのうま煮1袋", "「ドライに飽きた」サインが出ている子に。焼き鰤とだしの香りで変化をつけられます"),
    "trial-dog-trouble": ("dog-trial-set", "何なら食べてくれるか探している最中なら、少量ずつまとめて試せるこのセットが近道です"),
    "trial-cat-trouble": ("cat-trial-set", "偏食の猫ちゃんの「食べるもの探し」を、ドライもおかずも少量ずつ一度にできます"),
    # health（健康・症状別ケア）
    "ichibandashi-health": ("京の一番だし", "記事の結論「水分は食事から」を今日から始めるなら、かけるだけのこのだしからです"),
    "bonebroth-joint": ("チキンボーンブロス", "関節が気になり始めた子に。コラーゲン豊富なスープで水分と栄養を一緒に摂れます"),
    "kuzu-onaka": ("国内産-吉野本葛", "お腹をこわしやすい子に。記事で触れた「とろみ」を毎日のごはんに足せる本葛です"),
    "gainadori-diet": ("犬と猫のおやつ-鳥取大山-熟成がいな鶏-30ｇ", "減量中の「おやつどうする問題」はこれで解決。高タンパク低脂質の40kcalです"),
    "shika-diet": ("京都笠置-鹿肉と無農薬野菜の煮込み", "カロリーは抑えたいけど満足感は残したい子に。低脂質な天然鹿肉のおかずです"),
    "neko-kedama": ("ダブルだし猫のごはん-チキン-800g", "毛玉対策を主食から。甜菜繊維とイヌリンで排出をサポートする総合栄養食です"),
    "buri-hifu": ("舞鶴-ぶりのうま煮1袋", "皮膚・毛並みのケアを食事から始めたい方に。DHA・EPA豊富な鰤のおかずです"),
    "fish-allergy": ("だし薫る犬のごはん-フィッシュ-800g", "鶏や牛が合わないと分かった子の受け皿に。低アレルゲンの魚が主原料の主食です"),
    # feeding（与え方・食事管理）
    "okazu-feeding": ("地鶏のそぼろ煮1袋", "記事の「ドライ＋おかず」スタイルを始めるなら、のせるだけのこの一品が定番です"),
    "ichibandashi-feeding": ("京の一番だし", "ふやかしにもトッピングにも使える万能だし。混ぜ方に迷ったらまずこれからです"),
    "katsuobushi-feeding": ("無塩-鹿児島枕崎-おつお削り節", "トッピング入門に。そのままふりかけても、お湯を注いでだしにしても使えます"),
    "bonebroth-feeding": ("チキンボーンブロス", "ふやかし用のスープを常備したい方に。冷凍ストックできるボーンブロスです"),
    # choose（選び方・おすすめ）
    "dry-dog-choose": ("だし薫る犬のごはん-チキン", "記事の選び方基準（無添加・国産・グルテンフリー）をすべて満たす総合栄養食です"),
    "dry-cat-choose": ("ダブルだし猫のごはん-チキン-800g", "選び方で迷ったらこれ。猫の食いつきを考え抜いたダブルだしの総合栄養食です"),
    "trial-dog-choose": ("dog-trial-set", "いきなり大袋を買うのが不安な方に。初回限定3,300円で主食もおかずも試せます"),
    "trial-cat-choose": ("cat-trial-set", "フード切り替え前の相性チェックに。少量ずつ試せる初回限定セットです"),
    "premium-gift": ("犬と猫のプレミアム料理-京都舞笠置天然鹿肉-煮込みハンバーグ", "特別な日のごちそうを探している方に。天然鹿肉100%の煮込みハンバーグです"),
    # storage（保存・容器）
    "okazu-storage": ("地鶏のそぼろ煮3袋", "常温1年保存できるおかずは備蓄にも。ローリングストックの1軍になります"),
    "katsuobushi-storage": ("無塩-鹿児島枕崎-おつお削り節", "保存に気を使いたくない方に。常温OK・20gで使い切りやすいサイズです"),
    # homemade（手作り・レシピ）
    "yasai-homemade": ("旬の無農薬野菜セット-送料込み", "記事のレシピをすぐ実践できます。無農薬野菜もだしも葛も入った全部入りセット"),
    "kuzu-homemade": ("国内産-吉野本葛", "手作りごはんの仕上げに欠かせない、とろみ付け用の本葛100%です"),
    "bonebroth-homemade": ("チキンボーンブロス", "手作りのベーススープはこれ。鶏がらと丸鶏を長時間炊いた本物です"),
    "daiko-homemade": ("食事代行サービス", "「作りたいけど時間がない」なら、管理栄養士に任せるという選択肢もあります"),
    # basics（基礎知識）
    "dry-dog-basics": ("だし薫る犬のごはん-チキン", "記事で解説した「良い原材料表示」の実例として、一度見てほしい総合栄養食です"),
    "trial-dog-basics": ("dog-trial-set", "記事の「総合栄養食＋おかず」の考え方を、実際にセットで体験できます"),
    # senior（シニア）
    "bonebroth-senior": ("チキンボーンブロス", "食が細くなってきたシニアに。スープなら水分と栄養を無理なく摂れます"),
    "okazu-senior": ("京都笠置-鹿肉と無農薬野菜の煮込み", "噛む力が落ちてきた子に。柔らかく煮込んだ低脂質な鹿肉のおかずです"),
    "buri-senior": ("京都舞鶴港-鰤と大根の炊いたん", "食欲が落ちたシニアのごちそうに。だしが染みた柔らかい鰤の炊き合わせです"),
    # puppy / kitten
    "ichibandashi-puppy": ("京の一番だし", "ふやかしごはん卒業期の食トレに。だしの香りを味方にできます"),
    "trial-cat-kitten": ("cat-trial-set", "子猫のうちに色々な味と食感に慣らしておける、はじめてのセットです"),
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
