"""Cross-catalog instructions reference existing per-catalog changes."""
import json
from .operations import now,uid,text
from .products import digest
from .search import find_occurrences
from .store import dump

def require_staff(actor):
    if actor.role not in ('editor','developer'):raise PermissionError('本棚・変更案件は販促・開発部門で確認してください。')

def evidence(document,element_id):
    for page in document['pages']:
        if page.get('deleted'):continue
        for element in page['elements']:
            if element['id']==element_id and not element.get('deleted'):
                return page,element,digest(page)
    return None,None,None

def refresh_checks(state):
    for change in state['changes']:
        if not change.get('campaign_id'):continue
        page,_,stamp=evidence(state['document'],change['element_id'])
        if page:
            change['page_id']=page['id'];change['page_label']=page.get('label','')
        if change.get('status') not in ('fixed','verified'):continue
        if not stamp or stamp!=change.get('checked_evidence'):
            change['status']='open';change['recheck_reason']='対象ページが変更されました。紙面を再確認してください。'

def library(service,actor):
    require_staff(actor)
    with service.store.connection() as db:
        rows=db.execute('SELECT id,title,version,published_version,state FROM catalogs ORDER BY created DESC').fetchall()
    return [{k:r[k] for k in ('id','title','version','published_version')}|{'page_count':len(json.loads(r['state'])['document']['pages'])} for r in rows]

def search(service,actor,query,catalog_ids):
    require_staff(actor)
    if not isinstance(catalog_ids,list) or not 1<=len(catalog_ids)<=100 or any(not isinstance(c,str) for c in catalog_ids) or len(set(catalog_ids))!=len(catalog_ids):raise ValueError('対象のカタログを1〜100冊選択してください。')
    results=[];counts=[];total=0;versions={}
    with service.store.connection() as db:
        # A single read snapshot covers every catalog.
        db.execute('BEGIN')
        for cid in catalog_ids:
            row=service._row(db,cid);state=json.loads(row['state'])
            found=find_occurrences(state['document'],query)
            total+=found['occurrence_count'];versions[cid]=row['version']
            counts.append({'catalog_id':cid,'title':row['title'],'count':found['occurrence_count'],'revision':row['version']})
            seen=set()
            for result in found['results']:
                if result['element_id'] in seen:continue
                seen.add(result['element_id'])
                results.append({**result,'catalog_id':cid,'title':row['title'],'revision':row['version']})
    return {'query':query,'results':results,'occurrence_count':total,'target_count':len(results),'catalogs':counts,'versions':versions,'scope':'作業版の本文を検索。1冊につき先頭200出現まで表示し、同じ文字枠の指示は1件にまとめます。画像内文字は対象外です。','truncated':any(c['count']>200 for c in counts)}

def create(service,actor,spec):
    if actor.role!='editor':raise PermissionError('変更指示の登録は販促担当が行います。')
    title=text(spec.get('title'),200,True);instruction=text(spec.get('instruction'),5000,True);query=text(spec.get('query'),200,True)
    targets=spec.get('targets')
    if not isinstance(targets,list) or not 1<=len(targets)<=1000:raise ValueError('変更対象を1〜1000箇所選択してください。')
    if any(not isinstance(t,dict) or not isinstance(t.get('catalog_id'),str) or not isinstance(t.get('element_id'),str) or type(t.get('version')) is not int for t in targets):raise ValueError('変更対象が不正です。')
    keys={(t['catalog_id'],t['element_id']) for t in targets}
    if len(keys)!=len(targets):raise ValueError('変更対象が重複しています。')
    campaign={'id':uid(),'title':title,'instruction':instruction,'query':query,'created':now(),'author':actor.name,'targets':[]}
    with service.store.connection(write=True) as db:
        states={};rows={}
        for target in targets:
            cid=target['catalog_id']
            if cid not in rows:
                rows[cid]=service._row(db,cid);states[cid]=json.loads(rows[cid]['state'])
            row=rows[cid];state=states[cid]
            if row['version']!=target['version']:
                from .service import ConflictError
                raise ConflictError('対象カタログに別の変更があります。横断検索を更新し、対象を選び直してください。')
            page,element,_=evidence(state['document'],target['element_id'])
            if element is None or element['kind']!='text':raise ValueError('対象の文章が見つかりません。検索を更新してください。')
            # Validate provenance even for crafted requests; only matching frames can be selected.
            single={'pages':[{**page,'elements':[element]}]}
            if not find_occurrences(single,query)['occurrence_count']:raise ValueError('検索語と一致しない対象が含まれています。')
            change={'id':uid(),'campaign_id':campaign['id'],'type':'product_change_request','status':'open','author':actor.name,'created':campaign['created'],'element_id':element['id'],'page_id':page['id'],'page_label':page.get('label',''),'before':element.get('text',''),'after':instruction,'reason':'変更案件：'+title}
            state['changes'].append(change)
            campaign['targets'].append({'catalog_id':cid,'element_id':element['id'],'change_id':change['id'],'original_page_id':page['id'],'original_text':element.get('text','')})
        for cid,state in states.items():
            row=rows[cid];version=row['version']+1
            db.execute('INSERT INTO events(catalog_id,version,actor,action,before_state,created) VALUES (?,?,?,?,?,?)',(cid,version,actor.id,'product_change_request',row['state'],now()))
            db.execute('UPDATE catalogs SET state=?,version=? WHERE id=?',(dump(state),version,cid))
        db.execute('INSERT INTO change_campaigns(id,state,created) VALUES (?,?,?)',(campaign['id'],dump(campaign),campaign['created']))
    return next(c for c in listing(service,actor) if c['id']==campaign['id'])

def listing(service,actor):
    require_staff(actor);output=[]
    with service.store.connection() as db:
        db.execute('BEGIN')
        catalogs={r['id']:(r,json.loads(r['state'])) for r in db.execute('SELECT * FROM catalogs')}
        for row in db.execute('SELECT state FROM change_campaigns ORDER BY created DESC'):
            campaign=json.loads(row['state']);targets=[]
            for target in campaign['targets']:
                pair=catalogs.get(target['catalog_id']);status='missing';page=None;change=None;catalog={}
                if pair:
                    catalog,state=pair;page,element,stamp=evidence(state['document'],target['element_id'])
                    change=next((c for c in state['changes'] if c['id']==target['change_id']),None)
                    if element is not None and change:
                        status=change['status']
                        if change.get('recheck_reason') or status in ('verified','fixed') and stamp!=change.get('checked_evidence'):status='recheck'
                targets.append({**target,'status':status,'catalog_title':catalog['title'] if pair else '削除されたカタログ','catalog_version':catalog['version'] if pair else None,'page_id':page['id'] if page else None,'page_label':page.get('label','') if page else '','reason':change.get('recheck_reason','') if change else '指示または対象がありません','current_text':element.get('text','') if pair and element else ''})
            counts={s:sum(t['status']==s for t in targets) for s in ('open','fixed','verified','recheck','missing')}
            output.append({**campaign,'targets':targets,'counts':counts,'complete':bool(targets) and counts['verified']==len(targets)})
    return output
