"""Read-only image resources from one catalog; never infer certainty from a name."""
from .products import report

def image_resources(state,occurrence_id,available):
    occurrence=next((o for o in report(state)['occurrences'] if o['id']==occurrence_id),None)
    if occurrence is None:raise ValueError('掲載箇所が変わっています。商品一覧を更新してください。')
    doc=state['document'];assets=doc.get('assets',{});result=[]
    for candidate in occurrence['image_candidates']:
        aid=candidate.get('asset_id');asset=assets.get(aid,{})
        originals={}
        for a in state.get('attachments',[]):
            if aid and a.get('preview_asset')==aid:
                originals[a['id']]={**a,'association':'explicit'}
        name=asset.get('name') or candidate.get('name')
        for key,a in assets.items():
            if a.get('kind')=='source-image' and name and (name==a.get('name') or name in a.get('link_names',[])):
                originals.setdefault(key,{**a,'id':key,'association':'name_candidate'})
        def file_info(a):
            return {'id':a['id'],'name':a.get('name',a['id']),'association':a['association'],'available':available(a['id'])}
        uses=[{'page_label':p.get('label',''),'element_id':e['id']} for p in doc['pages'] if not p.get('deleted') for e in p['elements'] if not e.get('deleted') and e.get('kind')=='image' and ((aid and e.get('asset_id')==aid) or (not aid and e['id']==candidate['id'] and p['id']==occurrence['page_id']))]
        confirmed=occurrence['status']=='confirmed' and candidate['id'] in (occurrence.get('review') or {}).get('image_ids',[])
        result.append({'id':candidate['id'],'name':candidate['name'],'relation':candidate['relation'],'product_confirmed':confirmed,'preview':{'id':aid,'available':bool(aid and aid in assets and available(aid))},'originals':[file_info(a) for a in originals.values()],'uses':uses})
    return {'model':occurrence['model'],'page_label':occurrence['page_label'],'images':result,'scope':'この冊子の商品画像候補です。同名の元ファイルは原本候補として表示し、自動確定しません。表示用画像はPNG変換・最大2400pxのプレビューです。'}
