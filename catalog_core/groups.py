"""Explicit editorial groups preserve element identity and relative geometry."""
import copy
import math
from .operations import find_element,find_page,text,uid,now

def apply_group(state,actor,op):
    doc=state['document'];kind=op['type'];groups=doc.setdefault('groups',[])
    entry={'id':uid(),'type':kind,'author':actor.name,'created':now(),'status':'open'}
    if kind=='create_group':
        ids=op.get('element_ids')
        if not isinstance(ids,list) or not 2<=len(ids)<=1000 or any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):raise ValueError('異なる要素を2個以上選択してください。')
        members=[find_element(doc,i) for i in ids]
        if len({p['id'] for p,e in members})!=1 or any(e.get('deleted') or e['kind'] not in ('text','image','shape') for p,e in members):raise ValueError('同じページの文字・画像・図形を選択してください。')
        if any(set(ids)&set(g['element_ids']) for g in groups):raise ValueError('別の商品ブロックに含まれています。先にそのブロックを解除してください。')
        group={'id':'group-'+uid(),'name':text(op.get('name'),100,True),'element_ids':ids}
        groups.append(group);entry.update(group_id=group['id'],page_id=members[0][0]['id'],after=copy.deepcopy(group))
    else:
        group=next((g for g in groups if g['id']==op.get('group_id')),None)
        if group is None:raise ValueError('商品ブロックが見つかりません。')
        entry.update(group_id=group['id'],before=copy.deepcopy(group))
        if kind=='ungroup':groups.remove(group)
        else:
            members=[find_element(doc,i) for i in group['element_ids']]
            if any(e.get('deleted') for p,e in members):raise ValueError('削除指定の要素があります。復元するかブロックを解除してください。')
            if len({p['id'] for p,e in members})!=1:raise ValueError('要素が別ページに分かれています。ブロックを解除して作り直してください。')
            source=members[0][0];target=find_page(doc,op.get('page_id',source['id']))
            delta=op.get('delta')
            if not isinstance(delta,list) or len(delta)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in delta):raise ValueError('移動量が不正です。')
            moved=[]
            for p,e in members:
                x,y,w,h=e['bounds'];b=[round(x+delta[0],3),round(y+delta[1],3),w,h]
                if b[0]<0 or b[1]<0 or b[0]+w>target['width']+.01 or b[1]+h>target['height']+.01:raise ValueError('商品ブロックがページからはみ出します。移動量を調整してください。')
                moved.append((e,b))
            entry.update(page_id=source['id'],destination_page_id=target['id'],before={'name':group['name'],'elements':[copy.deepcopy(e) for p,e in members]})
            for e,b in moved:
                if source['id']!=target['id']:
                    if e.get('source',{}).get('page_id')==source['id']:
                        regions=source.setdefault('removed_regions',[])
                        regions[:]=[r for r in regions if r['element_id']!=e['id']]
                        regions.append({'element_id':e['id'],'bounds':e['source'].get('original_bounds',e['bounds']),'label':'商品ブロックを移動'})
                    target['removed_regions']=[r for r in target.get('removed_regions',[]) if r['element_id']!=e['id']]
                    source['elements'].remove(e);target['elements'].append(e)
                e['bounds']=b;e['position_modified']=True
                for t in state['threads']:
                    if t.get('element_id')==e['id']:t['page_id']=target['id']
            entry['after']={'name':group['name'],'elements':[copy.deepcopy(e) for e,b in moved]}
    state['changes'].append(entry)
