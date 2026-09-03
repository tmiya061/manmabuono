#!/usr/bin/env python3
"""テスト用の顧客アカウントを作る／消す（メール不要）

クーポンや会員限定の動作を「まだ買っていない新規会員」として確認したいときに使う。
実在しないメールアドレスで顧客を作り、有効化URLをAPIから直接もらうので、
メールを受け取る必要も、捨てアドレスを用意する必要も無い。

  python3 scripts/test_customer.py create              # 作る → 有効化URLとカートURLを表示
  python3 scripts/test_customer.py create --code 1122  # カートURLに割引コードも付ける
  python3 scripts/test_customer.py list                # 残っているテスト顧客を表示
  python3 scripts/test_customer.py delete              # テスト顧客を全部消す（注文0件のものだけ）

使い方の流れ
------------
1. create で出た「有効化URL」をブラウザで開く → パスワードを決める → その場でログイン状態になる
2. 続けて出た「カートURL」を開く → 商品が入った状態でチェックアウトへ飛ぶ
   （割引コードを付けていれば自動で入力された状態になる）
3. 注文サマリーで割引が効いているか／効いていないかを見る。**注文は完了させない**
4. 見終わったら delete で消す

⚠️ 安全のため、delete が消すのは「タグ test-account が付いていて、注文が0件で、
   メールが @example.com のもの」だけ。本物の顧客には手が届かない。

⚠️ 作成・削除は管理画面への書き込みなので、まとめて docs/admin-changelog.md に1行残す
   （例: 「テスト顧客を作成→検証→削除」）。
"""
import argparse
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shopifyql  # noqa: E402

TAG = "test-account"
DOMAIN = "example.com"
STORE = "https://manmabuono.jp"


def find_test_customers(retries=6):
    """タグで検索する。⚠️ 作成直後は検索インデックスに数秒のラグがあり空で返ることがあるので、
    空なら少し待って引き直す（実測: 作成→約10秒で出る）。"""
    for i in range(retries):
        d = shopifyql.gql(
            'query($q:String!){ customers(first:50, query:$q){ nodes{ id email numberOfOrders tags createdAt } } }',
            {"q": f"tag:{TAG}"},
        )
        rows = [c for c in d["customers"]["nodes"]
                if TAG in c["tags"] and (c["email"] or "").lower().endswith("@" + DOMAIN)]
        if rows or i == retries - 1:
            return rows
        time.sleep(3)
    return []


def pick_variant():
    """クーポン対象の商品を1つ選ぶ（お試しセット以外・販売中）"""
    d = shopifyql.gql(
        '''{ products(first:1, query:"status:active -tag:'お試しセット' price:>1000"){
             nodes{ title variants(first:1){ nodes{ id price availableForSale } } } } }''')
    p = d["products"]["nodes"][0]
    v = p["variants"]["nodes"][0]
    return p["title"], v["id"].split("/")[-1], v["price"]


def cmd_create(a):
    email = a.email or f"test-{datetime.now().strftime('%Y%m%d-%H%M%S')}@{DOMAIN}"
    r = shopifyql.gql(
        '''mutation($in:CustomerInput!){ customerCreate(input:$in){
             customer{ id email } userErrors{ field message } } }''',
        {"in": {"email": email, "firstName": "テスト", "lastName": "アカウント", "tags": [TAG]}},
    )["customerCreate"]
    if r["userErrors"]:
        print("🔴", r["userErrors"]); sys.exit(1)
    cid = r["customer"]["id"]
    url = shopifyql.gql(
        'mutation($id:ID!){ customerGenerateAccountActivationUrl(customerId:$id){ accountActivationUrl userErrors{ message } } }',
        {"id": cid},
    )["customerGenerateAccountActivationUrl"]["accountActivationUrl"]

    title, vid, price = pick_variant()
    cart = f"{STORE}/cart/{vid}:1" + (f"?discount={a.code}" if a.code else "")

    print(f"テスト顧客を作成: {email}  ({cid})\n")
    print("① まずこれを開いてパスワードを決める（＝ログイン状態になる）:")
    print(f"   {url}\n")
    print(f"② 次にこれを開く（{title} ¥{price} が入った状態でチェックアウトへ）:")
    print(f"   {cart}\n")
    print("③ 注文サマリーで割引を確認。注文は完了させない")
    print("④ 終わったら: python3 scripts/test_customer.py delete")


def cmd_list(a):
    rows = find_test_customers()
    if not rows:
        print("テスト顧客は残っていない"); return
    for c in rows:
        print(f'  {c["email"]}  注文{c["numberOfOrders"]}件  作成 {c["createdAt"][:16]}  {c["id"]}')


def cmd_delete(a):
    if a.id:
        # 検索に頼らず ID 指定で消す（作成直後など検索に出ないとき用）。ガードは同じ
        c = shopifyql.gql('query($id:ID!){ customer(id:$id){ id email numberOfOrders tags } }', {"id": a.id})["customer"]
        rows = [c] if c and TAG in c["tags"] and (c["email"] or "").lower().endswith("@" + DOMAIN) and int(c["numberOfOrders"]) == 0 else []
    else:
        rows = [c for c in find_test_customers() if int(c["numberOfOrders"]) == 0]
    if not rows:
        print("消すものがない（注文0件・test-account・@example.com のテスト顧客は無い）"); return
    for c in rows:
        r = shopifyql.gql(
            'mutation($in:CustomerDeleteInput!){ customerDelete(input:$in){ deletedCustomerId userErrors{ message } } }',
            {"in": {"id": c["id"]}},
        )["customerDelete"]
        print(("削除: " if r["deletedCustomerId"] else "🔴 失敗: ") + c["email"], r["userErrors"] or "")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create"); c.add_argument("--email"); c.add_argument("--code", help="カートURLに付ける割引コード")
    sub.add_parser("list")
    d = sub.add_parser("delete"); d.add_argument("--id", help="gid://shopify/Customer/… を直接指定（検索に出ないとき用）")
    a = p.parse_args()
    shopifyql.load_env()
    {"create": cmd_create, "list": cmd_list, "delete": cmd_delete}[a.cmd](a)


if __name__ == "__main__":
    main()
