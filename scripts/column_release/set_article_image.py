"""Set the approved article image. Requires SHOPIFY_* env vars (uses ../set_article_cta.py)."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import set_article_cta as api
P=Path(__file__).resolve().parent
ID='gid://shopify/Article/564977696829'
URL='https://manmabuono.jp/cdn/shop/t/2/assets/manmabuono-column-20260924-padding-26-v1.jpg'
if __name__=='__main__':
 if '--apply' not in sys.argv:raise SystemExit('Pass --apply to set the approved design 26.')
 # Use the repo .env loader only when credentials have not been supplied.
 import os
 if not os.environ.get('SHOPIFY_CLIENT_ID'):api.load_env()
 before=api.gql('query($id:ID!){article(id:$id){id handle title image{url altText width height}}}',{'id':ID})['article']
 assert before['handle']=='dog-homemade-recipe'
 backup=P/'article-before-20260924.json'
 if not backup.exists():backup.write_text(json.dumps(before,ensure_ascii=False,indent=2))
 result=api.gql('''mutation($id:ID!,$article:ArticleUpdateInput!){articleUpdate(id:$id,article:$article){article{id handle image{url altText width height}} userErrors{field message}}}''',{'id':ID,'article':{'image':{'url':URL,'altText':'のせるだけでOK！ 手作りご飯の作り方'}}})['articleUpdate']
 (P/'article-after-20260924.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 if result['userErrors']:raise RuntimeError(result['userErrors'])
 print(json.dumps(result['article'],ensure_ascii=False))
