"""Evidence-bearing product candidates. Geometry suggests; an editor decides."""
import copy
import hashlib
import json
import re
from .search import normalize
from .operations import now

MODEL=re.compile(r'(?<![A-Z0-9-])[A-Z]{1,8}-?\d{3,8}[A-Z0-9]*(?:-[A-Z0-9]+)*(?![A-Z0-9-])')
PRICE=re.compile(r'(?:[¥￥]\s*(\d[\d,]*(?:\.\d+)?)|(\d[\d,]*(?:\.\d+)?)\s*円)')
KINDS={'body','set','list','unspecified'}
SCOPE='作業版の本文テキストから抽出した候補です。画像内文字・未対応要素は対象外です。同じ型番も掲載ごとに確認します。近い位置の価格・画像が、その商品の情報とは限りません。'

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def extract_index(document):
    occurrences=[]
    groups={eid:g['id'] for g in document.get('groups',[]) for eid in g['element_ids']}
    for order,page in enumerate(document.get('pages',[]),1):
        if page.get('deleted'):continue
        elements=[e for e in page.get('elements',[]) if not e.get('deleted')]
        prices=[];images=[];descriptions=[]
        for e in elements:
            base={'element_id':e['id'],'bounds':e.get('bounds',[]),'source':e.get('source',{})}
            if e['kind']=='image':
                images.append({**base,'id':e['id'],'asset_id':e.get('asset_id'),'name':e.get('name','画像')})
            if e['kind']!='text':continue
            raw=e.get('text','');normalized=normalize(raw)
            descriptions.append({**base,'id':e['id'],'text':raw})
            for n,m in enumerate(PRICE.finditer(normalized)):
                prefix=normalized[max(0,m.start()-20):m.start()]
                labels=list(re.finditer('本体|セット|定価|希望小売',prefix))
                label=labels[-1].group() if labels else ''
                kind='body' if label=='本体' else 'set' if label=='セット' else 'list' if label else 'unspecified'
                prices.append({**base,'id':e['id']+':price:'+str(n),'amount':(m.group(1) or m.group(2)).replace(',',''),'notation':m.group(),'context':raw,'kind':kind})
        for e in elements:
            if e['kind']!='text':continue
            for ordinal,m in enumerate(MODEL.finditer(normalize(e.get('text','')))):
                model=m.group()
                if re.fullmatch(r'(?:L|H|W|D|IP|RA|CRI|AC|DC)\d+',model):continue
                def candidates(items,limit):
                    ranked=[]
                    for item in items:
                        same=item['element_id']==e['id']
                        grouped=bool(groups.get(e['id'])) and groups.get(e['id'])==groups.get(item['element_id'])
                        a=e.get('bounds') or [0,0,0,0];b=item.get('bounds') or [0,0,0,0]
                        distance=(a[0]+a[2]/2-b[0]-b[2]/2)**2+(a[1]+a[3]/2-b[1]-b[3]/2)**2
                        relation='same_frame' if same else 'manual_group' if grouped else 'nearby'
                        ranked.append((0 if same else 1 if grouped else 2,distance,{**item,'relation':relation}))
                    ranked.sort(key=lambda x:(x[0],x[1],x[2]['id']))
                    return [r[2] for r in ranked[:limit]]
                record={'id':digest([page['id'],e['id'],model,ordinal])[:24],'model':model,'page_id':page['id'],'page_label':page.get('label',str(order)),'order':order,'element_id':e['id'],'text':e.get('text',''),'bounds':e.get('bounds',[]),'source':e.get('source',{}),
                        'price_candidates':candidates(prices,12),'image_candidates':candidates(images,6),'description_candidates':candidates([d for d in descriptions if d['id']!=e['id']],8)}
                # Fingerprint selected candidate evidence too; changing nearby source requires review.
                record['fingerprint']=digest(record)
                occurrences.append(record)
    return {'schema':1,'occurrences':occurrences}

def report(state):
    index=extract_index(state['document']);reviews=state.get('product_reviews',{})
    records=[]
    for occurrence in index['occurrences']:
        review=reviews.get(occurrence['id'])
        status=('recheck' if review['fingerprint']!=occurrence['fingerprint'] else review['status']) if review else 'pending'
        records.append({**occurrence,'status':status,'review':copy.deepcopy(review)})
    current={r['id'] for r in records}
    return {'scope':SCOPE,'model_count':len({r['model'] for r in records if r['status']!='ignored'}),'occurrence_count':len(records),'occurrences':records,'orphan_review_count':len(set(reviews)-current),'counts':{s:sum(r['status']==s for r in records) for s in ('pending','confirmed','recheck','ignored')}}

def review_product(state,actor,op):
    occurrence=next((o for o in extract_index(state['document'])['occurrences'] if o['id']==op.get('occurrence_id')),None)
    if not occurrence or occurrence['fingerprint']!=op.get('fingerprint'):raise ValueError('元データが変わりました。一覧を更新して再確認してください。')
    status=op.get('status');price_state=op.get('price_state','unconfirmed')
    if status not in ('confirmed','ignored') or price_state not in ('confirmed','unconfirmed','not_applicable','unavailable'):raise ValueError('確認状態が不正です。')
    prices=op.get('prices',[]);images=op.get('image_ids',[]);descriptions=op.get('description_ids',[])
    valid={p['id'] for p in occurrence['price_candidates']}
    if not isinstance(prices,list) or len(prices)>12 or any(not isinstance(p,dict) or p.get('id') not in valid or p.get('kind') not in KINDS for p in prices):raise ValueError('価格候補を確認してください。')
    if len({p['id'] for p in prices})!=len(prices):raise ValueError('同じ価格が重複しています。')
    if (price_state=='confirmed')!=bool(prices):raise ValueError('価格確認済みには価格を選択し、それ以外では選択を外してください。')
    for ids,candidates in ((images,occurrence['image_candidates']),(descriptions,occurrence['description_candidates'])):
        if not isinstance(ids,list) or any(not isinstance(i,str) or i not in {c['id'] for c in candidates} for i in ids) or len(set(ids))!=len(ids):raise ValueError('関連候補の選択が不正です。')
    note=op.get('note','')
    if not isinstance(note,str) or len(note)>3000:raise ValueError('メモは3000文字以内にしてください。')
    reviews=state.setdefault('product_reviews',{});previous=reviews.get(occurrence['id'])
    if previous:state.setdefault('product_review_history',[]).append({'occurrence_id':occurrence['id'],**copy.deepcopy(previous)})
    reviews[occurrence['id']]={'fingerprint':occurrence['fingerprint'],'status':status,'price_state':price_state,'prices':copy.deepcopy(prices),'image_ids':images[:],'description_ids':descriptions[:],'note':note,'author':actor.name,'actor_id':actor.id,'created':now()}

def product_csv(result):
    from .exports import csv_bytes
    statuses={'pending':'未確認','confirmed':'確認済み','recheck':'再確認','ignored':'対象外'}
    kinds={'body':'本体','set':'セット','list':'定価','unspecified':'区分未確認'}
    rows=[['型番候補','掲載ページ','掲載順','文字枠ID','確認状態','価格確認状態','確認した価格（円）','未確定の価格候補（円）','確認した画像ID','確認した説明枠ID','原文','元Story','確認者','メモ','版']]
    for o in result['occurrences']:
        r=o.get('review') or {};confirmed=o['status']=='confirmed';pool={p['id']:p for p in o['price_candidates']}
        selected=' / '.join(kinds[p['kind']]+':'+pool[p['id']]['amount'] for p in r.get('prices',[]) if p['id'] in pool) if confirmed else ''
        rows.append([o['model'],o['page_label'],o['order'],o['element_id'],statuses[o['status']],{'confirmed':'確認済み','unconfirmed':'未確認','not_applicable':'該当なし','unavailable':'読取不能・不明'}.get(r.get('price_state'),'未確認') if confirmed else '未確認',selected,' / '.join(p['amount'] for p in o['price_candidates']),' / '.join(r.get('image_ids',[])) if confirmed else '',' / '.join(r.get('description_ids',[])) if confirmed else '',o['text'],o['source'].get('story_id',''),r.get('author',''),r.get('note',''),result.get('revision','')])
    return csv_bytes(rows)
