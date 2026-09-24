"""Remove only food-consultation's seo.hidden, with a non-overwritten backup."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import set_article_cta as api
P=Path(__file__).resolve().parent
ID='gid://shopify/Product/8004568088637'
QUERY='query($id:ID!){product(id:$id){id handle hidden:metafield(namespace:"seo",key:"hidden"){id namespace key type value}}}'
if __name__=='__main__':
 if '--apply' not in sys.argv:raise SystemExit('Pass --apply to remove seo.hidden for food-consultation only.')
 api.load_env()
 before=api.gql(QUERY,{'id':ID})['product']
 assert before['handle']=='food-consultation'
 backup=P/'noindex-before-20260924.json'
 if not backup.exists():backup.write_text(json.dumps(before,ensure_ascii=False,indent=2))
 if before['hidden']:
  assert before['hidden']['value']=='1'
  result=api.gql('mutation($metafields:[MetafieldIdentifierInput!]!){metafieldsDelete(metafields:$metafields){deletedMetafields{ownerId namespace key} userErrors{field message}}}',{'metafields':[{'ownerId':ID,'namespace':'seo','key':'hidden'}]})['metafieldsDelete']
  if result['userErrors']:raise RuntimeError(result['userErrors'])
 after=api.gql(QUERY,{'id':ID})['product']
 assert after['hidden'] is None
 (P/'noindex-after-20260924.json').write_text(json.dumps(after,ensure_ascii=False,indent=2))
 print('food-consultation: seo.hidden removed; verified null')
