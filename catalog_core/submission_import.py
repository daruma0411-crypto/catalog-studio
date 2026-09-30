"""Preview and apply keyed spreadsheet intake without silent overwrites."""
import hashlib
import json
import unicodedata
from .operations import text,uid,now
from .submissions import may_edit

def digest(fields):
    return hashlib.sha256(json.dumps(fields,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def content(item):return {k:item.get(k,'') for k in ('title','text','target')}

def build_preview(state,actor,spec,preview):
    namespace=text(spec.get('namespace'),100,True).strip()
    index=spec.get('sheet',0);header=spec.get('header_row',0)
    if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<len(preview['sheets']):raise ValueError('取り込むシートを選択してください。')
    sheet=preview['sheets'][index]
    if sheet.get('truncated') or sheet.get('content_truncated'):raise ValueError('表が上限を超えています。200行（見出し含む）・40列・1セル2000文字以内に分けて取り込んでください。')
    if isinstance(header,bool) or not isinstance(header,int) or not 0<=header<len(sheet['rows']):raise ValueError('見出し行を指定してください。')
    columns=spec.get('columns',{})
    if not isinstance(columns,dict):raise ValueError('列の対応を指定してください。')
    width=len(sheet['rows'][header])
    for k in ('key','title','text','target'):
        v=columns.get(k)
        if k=='target' and v is None:continue
        if isinstance(v,bool) or not isinstance(v,int) or not 0<=v<width:raise ValueError('原稿ID・件名・本文の列を指定してください。')
    existing={};errors=[];rows=[];seen=set()
    for s in state['submissions']:
        ref=s.get('import_ref',{})
        if ref.get('namespace')==namespace:
            if ref['key'] in existing:raise ValueError('保存済み原稿IDが重複しています。取り込み元を確認してください。')
            existing[ref['key']]=s
    for number,values in enumerate(sheet['rows'][header+1:],header+2):
        if not any(str(v).strip() for v in values):continue
        get=lambda name: str(values[columns[name]]).strip() if columns.get(name) is not None and columns[name]<len(values) else ''
        key=unicodedata.normalize('NFKC',get('key'))
        try:
            text(key,200,True)
            if key.startswith('='):raise ValueError('原稿IDには数式でなく固定の文字列を使用してください。')
            if key in seen:raise ValueError('原稿IDが表内で重複しています。')
            seen.add(key)
            incoming={'title':text(get('title'),200,True),'text':text(get('text'),50000,True),'target':text(get('target'),200)}
            old=existing.get(key)
            if old and not may_edit(old,actor):raise ValueError('別の担当が登録した原稿です。販促担当に取り込みを依頼してください。')
            if old is None:kind='new'
            elif digest(incoming)==digest(content(old)):kind='unchanged'
            elif digest(incoming)==old.get('import_ref',{}).get('baseline'):kind='local_only'
            elif digest(content(old))==old.get('import_ref',{}).get('baseline'):kind='update'
            else:kind='conflict'
            rows.append({'key':key,'row':number,'kind':kind,'submission_id':old['id'] if old else None,'before':content(old) if old else None,'after':incoming})
        except ValueError as error:errors.append({'row':number,'key':key,'message':str(error)})
    if not rows and not errors:errors.append({'row':None,'key':'','message':'見出し以降に原稿がありません。'})
    counts={k:sum(r['kind']==k for r in rows) for k in ('new','update','unchanged','local_only','conflict')}
    return {'namespace':namespace,'sheet_name':sheet['name'],'rows':rows,'counts':counts,'errors':errors,'missing_keys':sorted(set(existing)-seen),'note':'表から消えた原稿は削除しません。型番ではなく、改訂しても変わらない原稿IDを指定してください。'}

def apply_import(state,actor,spec,preview):
    result=build_preview(state,actor,spec,preview)
    if result['errors']:raise ValueError('取り込みに問題があります。プレビューの行番号と内容を確認してください。')
    resolutions=spec.get('resolutions',{})
    if not isinstance(resolutions,dict):raise ValueError('競合の扱いが不正です。')
    for row in result['rows']:
        if row['kind']=='conflict' and resolutions.get(row['key']) not in ('keep','incoming'):raise ValueError('競合した原稿は、Excelを採用するかシステムの内容を保持するか選んでください。')
    items={s['id']:s for s in state['submissions']}
    for row in result['rows']:
        old=items.get(row['submission_id'])
        if row['kind']=='local_only':continue
        if old is None:
            old={'id':uid(),**row['after'],'status':'received','author':actor.name,'author_id':actor.id,'created':now(),'asset_ids':[]}
            state['submissions'].append(old)
        use=row['kind'] in ('new','update') or (row['kind']=='conflict' and resolutions[row['key']]=='incoming')
        if use:
            old.update(row['after']);old['asset_ids']=list(dict.fromkeys(old.get('asset_ids',[])+[spec['asset_id']]))
        old['import_ref']={'namespace':result['namespace'],'key':row['key'],'baseline':digest(row['after']),'asset_id':spec['asset_id'],'sheet':result['sheet_name'],'row':row['row']}
    profiles=state.setdefault('submission_imports',[])
    profile={k:spec[k] for k in ('asset_id','columns')}
    profile.update(sheet=spec.get('sheet',0),namespace=result['namespace'])
    profile.update(header_row=spec.get('header_row',0),created=now(),author=actor.name,counts=result['counts'])
    profiles[:]=[p for p in profiles if p['namespace']!=result['namespace']]
    profiles.append(profile)
