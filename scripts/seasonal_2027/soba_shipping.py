"""承認済みの年越しそば発送案内を本文・カートへ追加し、変更前後を保存する。"""
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / 'scripts'))
import set_article_cta as api
api.load_env()
records = Path(__file__).parent / 'records'
before = records / 'soba-shipping-before.json'
assert not before.exists(), '実行記録あり。再実行前に確認してください。'
product_id = 'gid://shopify/Product/7503940091965'
query = '''query($id:ID!){product(id:$id){id title handle descriptionHtml metafield(namespace:"custom",key:"shipping_notice"){id type value}}}'''
data = api.gql(query, {'id': product_id})
before.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
notice = '年越しそばは2026年12月26日発送予定です。カートで選択した配送希望日にかかわらず、この日程での発送となります。'
product = data['product']
assert not product['metafield'], '既存の案内があります。内容を確認してください。'
payload = {'id': product_id, 'descriptionHtml': product['descriptionHtml'] + '<p><strong>' + notice + '</strong></p>', 'metafields': [{'namespace': 'custom', 'key': 'shipping_notice', 'type': 'multi_line_text_field', 'value': notice}]}
result = api.gql('''mutation($product:ProductUpdateInput!){productUpdate(product:$product){product{id} userErrors{field message}}}''', {'product': payload})
(records / 'soba-shipping-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
assert not result['productUpdate']['userErrors'], result
after = api.gql(query, {'id': product_id})
(records / 'soba-shipping-after.json').write_text(json.dumps(after, ensure_ascii=False, indent=2) + '\n')
assert after['product']['metafield']['value'] == notice
entry = '- 2026-10-31 | product 7503940091965（年越しそば） | 12/26発送予定・配送希望日にかかわらない旨を本文とカート用shipping_noticeへ追加 | scripts/seasonal_2027/soba_shipping.py | 復元: scripts/seasonal_2027/records/soba-shipping-before.json\n'
for log in [Path(__file__).resolve().parents[2] / 'docs/admin-changelog.md', root / 'docs/admin-changelog.md']:
    log.write_text(entry + log.read_text())
print('年越しそばの本文・カート用発送案内を更新し、再取得で確認済み')
