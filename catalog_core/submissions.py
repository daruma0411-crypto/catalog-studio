"""Submission revisions are distinct from document revisions and review decisions."""
import copy
import re
from datetime import date
from .operations import now,text,find_page

CONTENT_FIELDS=('title','target','text','asset_ids','page_id')
META_FIELDS=('assignee','due_date','ready_date')

def find_submission(state,sid):
    item=next((s for s in state['submissions'] if s['id']==sid),None)
    if item is None:raise ValueError('原稿が見つかりません。')
    return item

def may_edit(item,actor):
    return actor.role=='editor' or (actor.role=='developer' and (item.get('author_id')==actor.id or (not item.get('author_id') and item.get('author')==actor.name)))

def date_value(value):
    if value=='':return ''
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError('日付は年月日で指定してください。')
    try:date.fromisoformat(value)
    except ValueError:raise ValueError('存在する日付を指定してください。')
    return value

def update_submission(state,actor,op):
    item=find_submission(state,op.get('submission_id'))
    if not may_edit(item,actor):raise PermissionError('開発部門は自分が登録した原稿のみ更新できます。')
    if actor.role!='editor' and any(k in op for k in META_FIELDS):raise PermissionError('担当・期限は販促担当が設定します。')
    for key in ('title','target','text'):
        if key in op:item[key]=text(op[key],50000 if key=='text' else 200,key!='target')
    if 'page_id' in op:
        pid=op['page_id'] or None
        if pid:find_page(state['document'],pid)
        item['page_id']=pid
        if pid:item.pop('previous_page',None)
    if 'assignee' in op:item['assignee']=text(op['assignee'],100).strip()
    for key in ('due_date','ready_date'):
        if key in op:item[key]=date_value(op[key])

def require_recheck(item,reason):
    if item.get('agreement')=='agreed':item['agreement']='recheck'
    item['paper_checked']=False
    item['paper_recheck_reason']=reason
    if item.get('status')=='applied':item['status']='checking'

def reconcile(before,state,actor,reason=''):
    previous={s['id']:s for s in before.get('submissions',[])}
    for item in state['submissions']:
        old=previous.get(item['id'])
        if old is None:
            item.setdefault('author_id',actor.id);item.setdefault('content_revision',1)
            item.setdefault('updated_at',item.get('created',now()));item.setdefault('updated_by',actor.name)
            continue
        def value(record,key):
            if key=='page_id':return record.get(key) or None
            return record.get(key,[] if key=='asset_ids' else '')
        changed=[k for k in CONTENT_FIELDS+META_FIELDS if value(old,k)!=value(item,k)]
        if not changed:continue
        content=any(k in CONTENT_FIELDS for k in changed)
        revision=old.get('content_revision',1)
        item['content_revision']=revision+1 if content else revision
        item.setdefault('history',[]).append({'created':now(),'author':actor.name,'reason':text(reason or ('原稿・資料の変更' if content else '担当・期限の変更'),2000),'kind':'content' if content else 'schedule','revision_before':revision,'revision_after':item['content_revision'],'before':{k:copy.deepcopy(old.get(k)) for k in changed},'after':{k:copy.deepcopy(item.get(k)) for k in changed}})
        item.update(updated_at=now(),updated_by=actor.name)
        if content:require_recheck(item,'原稿・資料が変更されました。合意と紙面を再確認してください。')
    old_threads={t['id']:t for t in before.get('threads',[])}
    for thread in state.get('threads',[]):
        sid=thread.get('submission_id');old=old_threads.get(thread['id'])
        if sid and thread['status']=='open' and (not old or old.get('status')!='open' or old.get('messages')!=thread.get('messages')):
            require_recheck(find_submission(state,sid),'関連する質疑が更新されました。再確認してください。')
