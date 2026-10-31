#!/usr/bin/env python3
"""2027年おせち・年越しそばの仕様表（原材料・賞味期限・保存方法・ご注意・栄養成分）を
西川さん回答（2026-10-31）で埋める。実行前の状態を records/spec-before.json に保存する。
使い方: python3 scripts/seasonal_2027/set_spec_tables.py [--apply]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import set_article_cta as api

RECORDS = Path(__file__).resolve().parent / 'records'
OSECHI = 'gid://shopify/Product/7727212691517'
SOBA = 'gid://shopify/Product/7503940091965'

# 西川さん回答そのまま。並びは商品本文の「セット内容（5品）」に合わせる
INGREDIENTS = [
    ('鹿肉の年越しそば', '蕎麦、鹿肉、かつお節、昆布、椎茸'),
    ('鹿肉の煮込みハンバーグ', '鹿肉、トマト、しめじ、鹿ボーンブロス'),
    ('真鯛のアクアパッツァ', '鯛、トマト、じゃがいも、えのき、オリーブ油、吉野本葛、チキンボーンブロス'),
    ('がいな鶏の親子丼', '鶏肉、卵、じゃがいも、人参、しいたけ、三つ葉、本葛、かつお節、昆布、椎茸'),
    ('サーモンクリームシチュー', 'サーモン、豆乳（有機大豆）、小松菜、人参、マッシュルーム、チーズ、本葛、鹿ボーンブロス'),
]
# (たんぱく質以上, 脂肪以上, 粗繊維以下, 灰分以下, 水分以下, kcal/100g)
NUTRITION = {
    '鹿肉の年越しそば': ('6.0', '0.5', '1.0', '1.0', '80.0', '140'),
    '鹿肉の煮込みハンバーグ': ('9.5', '0.5', '1.0', '1.0', '86.5', '51'),
    '真鯛のアクアパッツァ': ('6.6', '2.7', '0.6', '0.7', '86.2', '57'),
    'がいな鶏の親子丼': ('6.0', '4.5', '0.5', '1.0', '87.5', '102'),
    'サーモンクリームシチュー': ('7.0', '5.0', '0.5', '1.0', '85.5', '84'),
}
EXPIRY = '解凍せずに冷凍保存で2027年1月30日まで\n消費期限：解凍後に冷蔵保存で2日間'
STORAGE = '-18℃以下で保存してください'
SHIPPING = '注文確認後、2026年12月26日に発送予定です。冷凍発送。'


def nutrition_line(name):
    p, f, fi, a, w, kcal = NUTRITION[name]
    # 既存商品（例：鹿肉煮込みハンバーグ）の表記に合わせる：全角％・読点区切り・kcal/100g
    return (f'たんぱく質 {p}％以上、脂肪 {f}％以上、粗繊維 {fi}％以下、'
            f'灰分 {a}％以下、水分 {w}％以下、エネルギー {kcal}kcal/100g')


def mf(owner, key, value):
    return {'ownerId': owner, 'namespace': 'custom', 'key': key,
            'type': 'multi_line_text_field', 'value': value}


def build():
    osechi = [
        mf(OSECHI, 'product_table1', '\n'.join(f'{n}：{v}' for n, v in INGREDIENTS)),
        mf(OSECHI, 'product_table2', EXPIRY),
        mf(OSECHI, 'product_table4', STORAGE),
        mf(OSECHI, 'product_table5', SHIPPING),
        mf(OSECHI, 'product_table6', '\n'.join(f'{n}：{nutrition_line(n)}' for n, _ in INGREDIENTS)),
    ]
    soba = [
        mf(SOBA, 'product_table1', dict(INGREDIENTS)['鹿肉の年越しそば']),
        mf(SOBA, 'product_table2', EXPIRY),
        mf(SOBA, 'product_table4', STORAGE),
        mf(SOBA, 'product_table6', nutrition_line('鹿肉の年越しそば')),
    ]
    return osechi + soba


QUERY = '''query($ids:[ID!]!){nodes(ids:$ids){... on Product{id title status updatedAt
  metafields(first:20,namespace:"custom"){nodes{id key type value}}}}}'''


def main():
    metafields = build()
    for m in metafields:
        print(f"--- {m['ownerId'].rsplit('/', 1)[1]} {m['key']}\n{m['value']}")
    if '--apply' not in sys.argv:
        print('\n（dry-run）本番へ書くには --apply')
        return
    api.load_env()
    before_path = RECORDS / 'spec-before.json'
    assert not before_path.exists(), '実行記録あり。再実行前に records/spec-before.json を確認'
    before = api.gql(QUERY, {'ids': [OSECHI, SOBA]})
    for n in before['nodes']:
        assert not any(m['key'].startswith('product_table') for m in n['metafields']['nodes']), \
            f"{n['id']} に仕様表が既にある。内容を確認してから"
    before_path.write_text(json.dumps(before, ensure_ascii=False, indent=2) + '\n')
    result = api.gql('''mutation($m:[MetafieldsSetInput!]!){metafieldsSet(metafields:$m){
      metafields{id ownerType key value} userErrors{field message code}}}''', {'m': metafields})
    (RECORDS / 'spec-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    assert not result['metafieldsSet']['userErrors'], result
    after = api.gql(QUERY, {'ids': [OSECHI, SOBA]})
    (RECORDS / 'spec-after.json').write_text(json.dumps(after, ensure_ascii=False, indent=2) + '\n')
    got = {(n['id'], m['key']): m['value'] for n in after['nodes'] for m in n['metafields']['nodes']}
    for m in metafields:
        assert got.get((m['ownerId'], m['key'])) == m['value'], m['key']
    entry = ('- 2026-10-31 | product 7727212691517（おせち2027）・7503940091965（年越しそば） | '
             '西川さん回答の原材料・賞味期限／消費期限・保存方法・発送注記・栄養成分を custom.product_table1/2/4/5/6 へ設定'
             '（そばは 1/2/4/6）。与え方（table3）は調理方法が未確認のため空のまま | '
             'scripts/seasonal_2027/set_spec_tables.py --apply | '
             '復元: metafieldsDelete で同キーを削除（変更前は未設定・scripts/seasonal_2027/records/spec-before.json）\n')
    log = ROOT / 'docs/admin-changelog.md'
    log.write_text(entry + log.read_text())
    print('\n本番へ設定し、再取得で全値の一致を確認済み')


if __name__ == '__main__':
    main()
