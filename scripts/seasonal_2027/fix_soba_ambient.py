"""年越しそばを常温・順次発送の条件へ訂正する（西川さん 10/31 架電）。

1. 本文・カート用 shipping_notice の「12/26 発送予定」を「11/15 以降順次発送・12/31 まで受付」へ差し替え
2. おせちの条件を流用していた仕様表 table2（賞味期限）・table4（保存方法）を削除（正しい文言は西川さん回答待ち）

実行: python3 scripts/seasonal_2027/fix_soba_ambient.py <repo_root> [--apply]
"""
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
apply = '--apply' in sys.argv
sys.path.insert(0, str(root / 'scripts'))
import set_article_cta as api  # noqa: E402

api.load_env()
records = Path(__file__).parent / 'records'
before_path = records / 'soba-ambient-before.json'
PRODUCT = 'gid://shopify/Product/7503940091965'
OLD = '年越しそばは2026年12月26日発送予定です。カートで選択した配送希望日にかかわらず、この日程での発送となります。'
NEW = '年越しそばは常温便で、2026年11月15日以降にご注文順で発送いたします。ご注文は2026年12月31日まで承ります。'

QUERY = '''query($id:ID!){product(id:$id){id title descriptionHtml
  metafields(namespace:"custom", first:20){nodes{id key type value}}}}'''


def fetch():
    return api.gql(QUERY, {'id': PRODUCT})['product']


before = fetch()
mf = {m['key']: m for m in before['metafields']['nodes']}
assert mf.get('shipping_notice', {}).get('value') == OLD, '発送案内が想定と違います。中断'
assert OLD in before['descriptionHtml'], '本文に旧案内がありません。中断'
to_delete = [k for k in ('product_table2', 'product_table4') if k in mf]
print('削除対象:', {k: mf[k]['value'] for k in to_delete})
print('新しい案内:', NEW)

if not apply:
    print('dry-run。--apply で本番へ反映')
    sys.exit(0)

assert not before_path.exists(), '実行記録あり。再実行前に確認してください。'
before_path.write_text(json.dumps(before, ensure_ascii=False, indent=2) + '\n')

payload = {
    'id': PRODUCT,
    'descriptionHtml': before['descriptionHtml'].replace(OLD, NEW),
    'metafields': [{'namespace': 'custom', 'key': 'shipping_notice',
                    'type': 'multi_line_text_field', 'value': NEW}],
}
r1 = api.gql('''mutation($product:ProductUpdateInput!){productUpdate(product:$product){product{id} userErrors{field message}}}''',
             {'product': payload})
assert not r1['productUpdate']['userErrors'], r1

r2 = api.gql('''mutation($ids:[MetafieldIdentifierInput!]!){metafieldsDelete(metafields:$ids){deletedMetafields{key} userErrors{field message}}}''',
             {'ids': [{'ownerId': PRODUCT, 'namespace': 'custom', 'key': k} for k in to_delete]})
assert not r2['metafieldsDelete']['userErrors'], r2
(records / 'soba-ambient-result.json').write_text(json.dumps({'productUpdate': r1, 'metafieldsDelete': r2}, ensure_ascii=False, indent=2) + '\n')

after = fetch()
(records / 'soba-ambient-after.json').write_text(json.dumps(after, ensure_ascii=False, indent=2) + '\n')
amf = {m['key']: m for m in after['metafields']['nodes']}
assert amf['shipping_notice']['value'] == NEW
assert NEW in after['descriptionHtml'] and OLD not in after['descriptionHtml']
assert not any(k in amf for k in to_delete)

entry = ('- 2026-10-31 | product 7503940091965（年越しそば） | 西川さん架電「常温・11/15以降発送・年内締切」に合わせ、'
         '本文とshipping_noticeを「常温便・11/15以降順次発送・12/31まで受付」へ差し替え、'
         'おせち条件を流用していたproduct_table2（賞味期限）・table4（保存方法）を削除 | '
         'scripts/seasonal_2027/fix_soba_ambient.py --apply | 復元: scripts/seasonal_2027/records/soba-ambient-before.json\n')
log = root / 'docs/admin-changelog.md'
log.write_text(entry + log.read_text())
print('反映完了・再取得で一致を確認')
