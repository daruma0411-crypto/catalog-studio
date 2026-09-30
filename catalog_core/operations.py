"""Validated editing commands. Original imported bytes are never overwritten."""
import copy
import math
import uuid
from datetime import datetime,timezone


def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def uid(): return uuid.uuid4().hex[:16]


def text(value,maximum=50000,required=False):
    if not isinstance(value,str) or len(value)>maximum or (required and not value.strip()):
        raise ValueError(f'文字列を正しく入力してください（最大{maximum}文字）。')
    return value


def find_element(doc,eid):
    for page in doc['pages']:
        for element in page['elements']:
            if element['id']==eid:
                return page,element
    raise ValueError('対象要素が見つかりません。画面を更新してください。')


def find_page(doc,pid):
    page=next((p for p in doc['pages'] if p['id']==pid),None)
    if page is None: raise ValueError('対象ページが見つかりません。')
    return page


def new_page(doc,title):
    template=doc['pages'][0]
    return {'id':'page-'+uid(),'source_label':None,'label':'新規','title':text(title or '新規ページ',200),'width':template['width'],'height':template['height'],'elements':[],'original':False}


def valid_bounds(bounds,page):
    if not isinstance(bounds,list) or len(bounds)!=4 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in bounds):
        raise ValueError('配置座標が不正です。')
    x,y,w,h=bounds
    if w<1 or h<1 or w>page['width']*2 or h>page['height']*2 or abs(x)>page['width'] or abs(y)>page['height']:
        raise ValueError('配置がページの許容範囲を超えています。')
    return [round(v,3) for v in bounds]


def apply(state,actor,op):
    kind=op.get('type')
    doc=state['document']
    entry={'id':uid(),'type':kind,'author':actor.name,'created':now(),'reason':text(op.get('reason',''),2000),'status':'open'}
    if kind in ('edit_text','replace_text','move','delete','restore','replace_image','flow_text'):
        page,el=find_element(doc,op.get('element_id'))
        entry.update(element_id=el['id'],page_id=page['id'],page_label=page['label'],source=copy.deepcopy(el.get('source',{})),before=copy.deepcopy(el))
        if el.get('deleted') and kind!='restore': raise ValueError('削除済みの対象です。先に復元してください。')
        if kind in ('edit_text','replace_text','flow_text') and el['kind']!='text': raise ValueError('文章の要素を選択してください。')
        if kind=='edit_text':
            el['text']=text(op.get('text'))
            el['modified']=True
        elif kind=='replace_text':
            before=text(op.get('before'),50000,True);after=text(op.get('after'))
            count=el['text'].count(before)
            if count!=1: raise ValueError(f'選択範囲内に変更前の文字列が{count}件あります。1か所に絞れる文字列を指定してください。')
            el['text']=el['text'].replace(before,after,1);el['modified']=True
        elif kind=='move':
            destination=find_page(doc,op.get('page_id',page['id']))
            el['bounds']=valid_bounds(op.get('bounds'),destination)
            if destination['id']!=page['id']:
                if el.get('source',{}).get('page_id')==page['id']:
                    regions=page.setdefault('removed_regions',[])
                    regions[:]=[r for r in regions if r['element_id']!=el['id']]
                    regions.append({'element_id':el['id'],'bounds':el['source'].get('original_bounds',entry['before']['bounds']),'label':'別ページへ移動'})
                destination['removed_regions']=[r for r in destination.get('removed_regions',[]) if r['element_id']!=el['id']]
                page['elements'].remove(el);destination['elements'].append(el)
                for thread in state['threads']:
                    if thread.get('element_id')==el['id']:thread['page_id']=destination['id']
            el['modified']=True;entry['destination_page_id']=destination['id']
        elif kind=='delete':
            el['deleted']=True;entry['space_policy']=text(op.get('space_policy','空きを残す'),100)
        elif kind=='restore': el['deleted']=False
        elif kind=='replace_image':
            if el['kind']!='image': raise ValueError('画像を選択してください。')
            aid=op.get('asset_id');asset=doc['assets'].get(aid)
            if not asset or asset.get('kind')!='image': raise ValueError('差し替え画像が見つかりません。')
            el['asset_id']=aid;el['name']=asset['name'];el['modified']=True
        elif kind=='flow_text':
            split=op.get('split_at')
            if isinstance(split,bool) or not isinstance(split,int) or not 0<=split<len(el['text']): raise ValueError('文章を送る開始位置が不正です。')
            target=op.get('page_id')
            destination=find_page(doc,target) if target else new_page(doc,op.get('title','続きのページ'))
            if destination['id']==page['id']: raise ValueError('送り先は別のページにしてください。')
            if not target:
                doc['pages'].insert(doc['pages'].index(page)+1,destination)
            tail=copy.deepcopy(el);tail['id']='text-'+uid();tail['text']=el['text'][split:];tail['modified']=True
            tail['bounds']=[30,40,min(el['bounds'][2],destination['width']-60),max(80,el['bounds'][3])]
            tail['source']={**el.get('source',{}),'derived_from':el['id'],'split_at':split}
            destination['elements'].append(tail)
            el['text']=el['text'][:split];el['modified']=True
            entry.update(destination_page_id=destination['id'],continuation=copy.deepcopy(tail),split_at=split)
        entry['after']=copy.deepcopy(el)
    elif kind=='add_text':
        p=find_page(doc,op.get('page_id'))
        el={'id':'text-'+uid(),'kind':'text','text':text(op.get('text'),required=True),'font_size':min(48,max(6,float(op.get('font_size',12)))),'bounds':valid_bounds(op.get('bounds',[35,50,220,110]),p),'source':{'new':True},'modified':True}
        p['elements'].append(el);entry.update(element_id=el['id'],page_id=p['id'],after=copy.deepcopy(el))
    elif kind=='add_page':
        p=new_page(doc,op.get('title','新規ページ'));after=op.get('after_page_id')
        index=doc['pages'].index(find_page(doc,after))+1 if after else len(doc['pages'])
        doc['pages'].insert(index,p);entry.update(page_id=p['id'],after={'title':p['title'],'position':index+1})
    elif kind=='rename_page':
        p=find_page(doc,op.get('page_id'));entry['before']=p['title'];p['title']=text(op.get('title'),200,True);p['title_auto']=False;entry.update(page_id=p['id'],after=p['title'])
    elif kind=='delete_page':
        p=find_page(doc,op.get('page_id'))
        if any(s.get('page_id')==p['id'] for s in state['submissions']):raise ValueError('このページに原稿が登録されています。原稿の対象ページを変更または未指定にしてから削除してください。')
        if len(doc['pages'])==1: raise ValueError('最後の1ページは削除できません。')
        if any(not e.get('deleted') for e in p['elements']): raise ValueError('内容が残っています。要素を移動または削除指定してからページを削除してください。')
        if any(t.get('page_id')==p['id'] and t['status']=='open' for t in state['threads']): raise ValueError('未解決のコメントが残っています。')
        doc['pages'].remove(p);entry.update(page_id=p['id'],before=copy.deepcopy(p))
    elif kind=='reorder_pages':
        ids=op.get('page_ids')
        if not isinstance(ids,list) or len(ids)!=len(doc['pages']) or set(ids)!={p['id'] for p in doc['pages']}: raise ValueError('ページ順序が不正です。')
        entry['before']=[p['id'] for p in doc['pages']];doc['pages']=[find_page(doc,i) for i in ids];entry['after']=ids
    elif kind=='add_submission':
        item={'id':uid(),'title':text(op.get('title'),200,True),'text':text(op.get('text'),required=True),'target':text(op.get('target',''),200),'status':'received','author':actor.name,'created':now(),'asset_ids':[]}
        pid=op.get('page_id') or None
        if pid:find_page(doc,pid)
        item['page_id']=pid
        asset_ids=op.get('asset_ids',[])
        if not isinstance(asset_ids,list) or len(asset_ids)>30 or any(not any(a['id']==aid for a in state['attachments']) for aid in asset_ids):raise ValueError('原稿の添付資料が不正です。')
        item['asset_ids']=list(dict.fromkeys(asset_ids))
        source=op.get('source_ref')
        if source:
            if not isinstance(source,dict) or source.get('asset_id') not in item['asset_ids'] or not isinstance(source.get('row'),int) or source['row']<1:raise ValueError('表の参照元が不正です。')
            item['source_ref']={'asset_id':source['asset_id'],'sheet':text(source.get('sheet',''),200),'row':source['row']}
        state['submissions'].append(item)
        return
    elif kind=='submission_update':
        from .submissions import update_submission
        update_submission(state,actor,op)
        return
    elif kind=='submission_review':
        item=next((s for s in state['submissions'] if s['id']==op.get('submission_id')),None)
        if item is None:raise ValueError('原稿が見つかりません。')
        agreement=op.get('agreement',item.get('agreement','pending'))
        if agreement not in ('pending','agreed','recheck'):raise ValueError('合意状態が不正です。')
        if agreement=='agreed' and any(t.get('submission_id')==item['id'] and t['status']=='open' for t in state['threads']):raise ValueError('未解決の質問を確認し、解決にしてから合意を記録してください。')
        checked=op.get('paper_checked',item.get('paper_checked',False))
        if not isinstance(checked,bool):raise ValueError('確認状態が不正です。')
        pid=op.get('page_id',item.get('review_page_id')) or None
        if pid:find_page(doc,pid)
        if checked and not pid:raise ValueError('確認した紙面のページを選んでください。')
        item.update(agreement=agreement,paper_checked=checked,review_page_id=pid,reviewed_by=actor.name,reviewed_at=now())
        if 'agreement' in op and agreement=='agreed':item.update(agreed_content_revision=item.get('content_revision',1),agreed_at=now(),agreed_by=actor.name)
        if checked:item.update(checked_content_revision=item.get('content_revision',1),checked_at=now(),checked_by=actor.name)
        return
    elif kind=='submission_assets':
        item=next((s for s in state['submissions'] if s['id']==op.get('submission_id')),None)
        ids=op.get('asset_ids')
        if item is None or not isinstance(ids,list) or any(not any(a['id']==aid for a in state['attachments']) for aid in ids):raise ValueError('原稿または資料が不正です。')
        from .submissions import may_edit
        if not may_edit(item,actor):raise PermissionError('自分が登録した原稿の資料を選択してください。')
        item['asset_ids']=list(dict.fromkeys(ids))
        return
    elif kind=='submission_status':
        item=next((s for s in state['submissions'] if s['id']==op.get('submission_id')),None)
        status=op.get('status')
        if item is None or status not in ('received','checking','applied'): raise ValueError('原稿または状態が不正です。')
        item['status']=status
        return
    elif kind=='comment':
        eid=op.get('element_id');pid=op.get('page_id');sid=op.get('submission_id')
        gid=op.get('group_id');group=None
        if gid:
            group=next((g for g in doc.get('groups',[]) if g['id']==gid),None)
            if not group:raise ValueError('商品ブロックが見つかりません。')
            pid=find_element(doc,group['element_ids'][0])[0]['id']
        if eid: pid=find_element(doc,eid)[0]['id']
        elif pid: find_page(doc,pid)
        if sid and not any(s['id']==sid for s in state['submissions']): raise ValueError('原稿が見つかりません。')
        destination=op.get('destination','production')
        if destination not in ('production','developer','editor'): raise ValueError('宛先が不正です。')
        item={'id':uid(),'element_id':eid,'page_id':pid,'submission_id':sid,'destination':destination,'status':'open','messages':[{'author':actor.name,'role':actor.role,'text':text(op.get('text'),10000,True),'created':now()}]}
        if group:item.update(group_id=gid,group_name=group['name'],element_ids=list(group['element_ids']))
        state['threads'].append(item)
        return
    elif kind in ('reply','resolve_thread','reopen_thread'):
        thread=next((t for t in state['threads'] if t['id']==op.get('thread_id')),None)
        if thread is None: raise ValueError('コメントが見つかりません。')
        if kind=='reply':
            thread['messages'].append({'author':actor.name,'role':actor.role,'text':text(op.get('text'),10000,True),'created':now()})
            thread['status']='open'
            for change in state['changes']:
                if thread.get('element_id') and change.get('element_id')==thread['element_id']:
                    change['status']='open';change['recheck_reason']='関連する確認事項に新しい回答があります。'
        else: thread['status']='resolved' if kind=='resolve_thread' else 'open'
        return
    elif kind=='change_status':
        change=next((c for c in state['changes'] if c['id']==op.get('change_id')),None)
        if change is None or op.get('status') not in ('open','fixed','verified'): raise ValueError('指示または状態が不正です。')
        change['status']=op['status']
        return
    else:
        raise ValueError('未対応の操作です。')
    state['changes'].append(entry)


def public_document(document):
    doc=copy.deepcopy(document)
    doc.pop('stories',None)
    doc.pop('groups',None)
    used=set()
    for p in doc['pages']:
        p.pop('reference_asset',None)
        p.pop('removed_regions',None)
        p['elements']=[e for e in p['elements'] if not e.get('deleted')]
        if p.get('title_auto',p.get('original',False)):
            candidates=[e for e in p['elements'] if e['kind']=='text' and e['bounds'][1]<80 and len(e.get('text',''))>6]
            p['title']=max(candidates,key=lambda e:e.get('font_size',0))['text'][:70] if candidates else 'カタログページ'
        for e in p['elements']:
            if e.get('modified'):
                e.pop('runs',None)
            if e.get('asset_id'): used.add(e['asset_id'])
    doc['assets']={k:v for k,v in doc['assets'].items() if k in used}
    return doc
