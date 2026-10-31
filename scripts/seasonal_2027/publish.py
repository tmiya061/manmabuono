#!/usr/bin/env python3
"""2027おせち既存商品を更新。記録と承認済み計画を引数で指定する。"""
import argparse, json, sys
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--api-root',type=Path,required=True)
    parser.add_argument('--records',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    plan=json.loads((args.records/'production-plan.json').read_text())
    if not args.apply:
        print('既存おせちの本文・SEO・画像6枚・仕様空欄・6600円、両商品CONTINUE。--applyで実行。')
        return
    sys.path.insert(0,str(args.api_root/'scripts'))
    import set_article_cta as api
    api.load_env()
    if (args.records/'production-product.json').exists():
        raise RuntimeError('実行記録あり。部分実行を点検してから再開してください。')
    logs=[Path(__file__).resolve().parents[2]/'docs/admin-changelog.md',args.api_root/'docs/admin-changelog.md']
    def run(name,query,variables,key,summary):
        result=api.gql(query,variables)
        (args.records/('production-'+name+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        if result[key].get('userErrors'):
            raise RuntimeError(result[key]['userErrors'])
        for log in dict.fromkeys(logs):
            log.write_text('- 2026-10-31 | 季節商品（おせち7727212691517／そば7503940091965） | '+summary+' | scripts/seasonal_2027/publish.py | 復元: verify/20261031_seasonal/before.json。実行結果production-'+name+'.json\n'+log.read_text())
        print(name+' OK')
        return result
    run('product', 'mutation($product:ProductUpdateInput!){productUpdate(product:$product){product{id title} userErrors{field message}}}', {'product':plan['product']},'productUpdate','おせちを2027年5品へ更新・12/26発送予定を本文とカート用メタフィールドへ設定')
    run('tables', 'mutation($metafields:[MetafieldIdentifierInput!]!){metafieldsDelete(metafields:$metafields){deletedMetafields{ownerId key namespace} userErrors{field message}}}', {'metafields':plan['clear_tables']},'metafieldsDelete','未確定の仕様6項目を空欄化（旧年の原材料・発送日等を非表示）')
    for name,field,summary in [('images-add','images_add','採用済み画像6枚を既存おせちへ関連付け'),('images-detach','images_detach','旧画像8枚を商品から関連解除（ファイルは保持）')]:
        run(name,'mutation($files:[FileUpdateInput!]!){fileUpdate(files:$files){files{id} userErrors{field message}}}',{'files':plan[field]},'fileUpdate',summary)
    run('images-order','mutation($id:ID!,$moves:[MoveInput!]!){productReorderMedia(id:$id,moves:$moves){job{id done} userErrors{field message}}}',{'id':plan['product']['id'],'moves':plan['images_order']},'productReorderMedia','主画像と個別5品を指定順に整列')
    for i,item in enumerate(plan['variants']):
        run('variant-'+str(i),'mutation($productId:ID!,$variants:[ProductVariantsBulkInput!]!){productVariantsBulkUpdate(productId:$productId,variants:$variants){productVariants{id price inventoryPolicy} userErrors{field message}}}',item,'productVariantsBulkUpdate','おせち6600円・両商品を受付上限なしに設定' if i==0 else '年越しそば1320円を維持し受付上限なしへ')
if __name__=='__main__':
    main()
