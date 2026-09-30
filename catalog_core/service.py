import copy
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass,asdict
from pathlib import Path

from .importer import parse_idml,read_package
from .operations import apply,now,uid,public_document
from .search import find_occurrences
from .store import Store,dump
from .submissions import reconcile,may_edit,find_submission


class ConflictError(Exception): pass


@dataclass(frozen=True)
class Actor:
    id:str
    name:str
    role:str


class Service:
    def __init__(self,directory):
        self.directory=Path(directory)
        self.assets_dir=self.directory/'assets'
        self.sources_dir=self.directory/'sources'
        self.assets_dir.mkdir(parents=True,exist_ok=True)
        self.sources_dir.mkdir(parents=True,exist_ok=True)
        self.store=Store(self.directory/'catalog.sqlite3')
        self.seed_users()

    def seed_users(self):
        with self.store.connection(write=True) as db:
            for user,name,role,password in [('promo','販促担当','editor','promo-demo'),('development','開発部門','developer','development-demo'),('reader','社内ユーザー','reader','reader-demo')]:
                if db.execute('SELECT 1 FROM users WHERE id=?',(user,)).fetchone(): continue
                salt=secrets.token_hex(16)
                hashed=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
                db.execute('INSERT INTO users VALUES (?,?,?,?,?)',(user,name,role,salt,hashed))

    def login(self,user,password):
        if not isinstance(user,str) or not isinstance(password,str) or len(user)>100 or len(password)>500: raise PermissionError('ユーザー名またはパスワードが違います。')
        with self.store.connection(write=True) as db:
            row=db.execute('SELECT * FROM users WHERE id=?',(user,)).fetchone()
            if row is None: raise PermissionError('ユーザー名またはパスワードが違います。')
            candidate=hashlib.scrypt(password.encode(),salt=bytes.fromhex(row['salt']),n=16384,r=8,p=1).hex()
            if not hmac.compare_digest(candidate,row['password_hash']): raise PermissionError('ユーザー名またはパスワードが違います。')
            token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24)
            db.execute('DELETE FROM sessions WHERE expires < ?',(time.time(),))
            db.execute('INSERT INTO sessions VALUES (?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user,time.time()+12*3600,csrf))
            return {'token':token,'csrf':csrf,'actor':{'id':user,'name':row['name'],'role':row['role']}}

    def session(self,token):
        with self.store.connection() as db:
            row=db.execute('SELECT u.id,u.name,u.role,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?',(hashlib.sha256((token or '').encode()).hexdigest(),time.time())).fetchone()
            if row is None: raise PermissionError('ログインしてください。')
            return Actor(row['id'],row['name'],row['role']),row['csrf']

    def authenticate(self,token): return self.session(token)[0]

    def logout(self,token):
        with self.store.connection(write=True) as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))

    def _row(self,db,cid):
        row=db.execute('SELECT * FROM catalogs WHERE id=?',(cid,)).fetchone()
        if row is None: raise ValueError('カタログが見つかりません。')
        return row

    def list_catalogs(self,actor):
        with self.store.connection() as db:
            rows=db.execute('SELECT id,title,version,published_version,created FROM catalogs ORDER BY created DESC').fetchall()
        return [{**dict(r),'version':r['published_version'] if actor.role=='reader' else r['version']} for r in rows if actor.role!='reader' or r['published_version'] is not None]

    def import_catalog(self,data,filename,actor):
        if actor.role!='editor': raise PermissionError('カタログの取り込みは販促担当が行います。')
        raw,name,links,pdf=read_package(data,filename)
        doc=parse_idml(raw,self.assets_dir,links)
        cid=uid()
        (self.sources_dir/(cid+'.idml')).write_bytes(raw)
        if pdf:
            from .assets import add_pdf_reference
            add_pdf_reference(doc,pdf,self.assets_dir)
        state={'document':doc,'changes':[],'submissions':[],'threads':[],'attachments':[]}
        with self.store.connection(write=True) as db:
            db.execute('INSERT INTO catalogs(id,title,version,state,original,published,published_version,created) VALUES (?,?,?,?,?,?,?,?)',(cid,name,1,dump(state),dump(doc),None,None,now()))
        return self.get_catalog(cid,actor)

    def get_catalog(self,cid,actor):
        with self.store.connection() as db:
            row=self._row(db,cid)
            event=db.execute('SELECT actor,action FROM events WHERE catalog_id=? ORDER BY id DESC LIMIT 1',(cid,)).fetchone()
        if actor.role=='reader':
            if row['published'] is None: raise PermissionError('このカタログは社内共有されていません。')
            return {'id':cid,'title':row['title'],'version':row['published_version'],'published_version':row['published_version'],'document':json.loads(row['published']),'readonly':True,'can_undo':False}
        state=json.loads(row['state'])
        state.update(id=cid,title=row['title'],version=row['version'],published_version=row['published_version'],readonly=actor.role!='editor',can_undo=bool(event and event['actor']==actor.id and event['action'] not in ('undo','publish')))
        return state

    def search(self,cid,actor,query):
        state=self.get_catalog(cid,actor)
        return {**find_occurrences(state['document'],query),'catalog_id':cid,'title':state['title'],'revision':state['version']}

    def apply_operation(self,cid,actor,expected_version,op):
        kind=op.get('type')
        developer_ops={'add_submission','submission_update','submission_assets','comment','reply','import_submissions'}
        if actor.role!='editor' and not (actor.role=='developer' and kind in developer_ops): raise PermissionError('この操作を行う権限がありません。')
        if isinstance(expected_version,bool) or not isinstance(expected_version,int): raise ValueError('版番号が不正です。')
        with self.store.connection(write=True) as db:
            row=self._row(db,cid)
            if row['version']!=expected_version: raise ConflictError('別の変更が保存されています。再読み込みしてから操作してください。')
            state=json.loads(row['state']);version=row['version']+1
            if kind=='undo':
                event=db.execute('SELECT * FROM events WHERE catalog_id=? ORDER BY id DESC LIMIT 1',(cid,)).fetchone()
                if not event or event['actor']!=actor.id or event['action'] in ('undo','publish'): raise ValueError('直前の自分の編集のみ取り消せます。公開の取り消しはできません。')
                state=json.loads(event['before_state'])
            elif kind in ('create_group','move_group','ungroup'):
                from .groups import apply_group
                apply_group(state,actor,op)
            elif kind=='reset_document':
                original=json.loads(row['original'])
                # Keep uploaded materials available for the next editing pass.
                original['assets']={**state['document']['assets'],**original['assets']}
                pages={p['id']:p for p in original['pages']}
                elements={e['id']:p['id'] for p in original['pages'] for e in p['elements']}
                for thread in state['threads']:
                    eid=thread.get('element_id');pid=thread.get('page_id')
                    if eid or pid:
                        thread['status']='open'
                        if eid in elements:thread['page_id']=elements[eid]
                        elif eid or pid not in pages:
                            thread['previous_target']={'element_id':eid,'page_id':pid}
                            thread['element_id']=None;thread['page_id']=None
                for submission in state['submissions']:
                    if submission['status']=='applied':submission['status']='checking'
                    pid=submission.get('page_id')
                    if pid and pid not in pages:
                        old_page=next((p for p in state['document']['pages'] if p['id']==pid),{})
                        submission['previous_page']={'id':pid,'title':old_page.get('title','削除されたページ')}
                        submission['page_id']=None
                state['document']=original
                state['changes']=[]
            elif kind=='import_submissions':
                from .submission_import import apply_import
                apply_import(state,actor,op,self._submission_sheet(state,op))
            elif kind=='publish':
                pending=sum(t['status']=='open' for t in state['threads'])
                if pending: raise ValueError(f'未解決の確認事項が{pending}件あります。解決してから社内共有してください。')
                db.execute('UPDATE catalogs SET published=?,published_version=? WHERE id=?',(dump(public_document(state['document'])),version,cid))
            else:
                apply(state,actor,op)
            if kind not in ('undo','publish'):
                reconcile(json.loads(row['state']),state,actor,op.get('reason',''))
            paper_ops={'edit_text','replace_text','move','delete','restore','replace_image','flow_text','add_text','add_page','rename_page','delete_page','reorder_pages','move_group','reset_document'}
            if kind in paper_ops:
                page_ids={p['id'] for p in state['document']['pages']}
                for submission in state['submissions']:
                    if submission.get('review_page_id') not in page_ids:
                        submission['review_page_id']=None
                    if submission.get('paper_checked'):
                        submission['paper_checked']=False
                        submission['paper_recheck_reason']='紙面が変更されました。再確認してください。'
            db.execute('INSERT INTO events(catalog_id,version,actor,action,before_state,created) VALUES (?,?,?,?,?,?)',(cid,version,actor.id,kind,row['state'],now()))
            db.execute('UPDATE catalogs SET state=?,version=? WHERE id=?',(dump(state),version,cid))
        return self.get_catalog(cid,actor)

    def _submission_sheet(self,state,spec):
        from .assets import spreadsheet_preview
        aid=spec.get('asset_id')
        asset=next((a for a in state['attachments'] if a['id']==aid and a.get('kind')=='spreadsheet'),None)
        if asset is None:raise ValueError('取り込むExcel・CSVを先にアップロードしてください。')
        return spreadsheet_preview((self.assets_dir/asset['id']).read_bytes(),asset['name'])

    def preview_submission_import(self,cid,actor,spec):
        if actor.role not in ('editor','developer'):raise PermissionError('原稿取り込みの権限がありません。')
        from .submission_import import build_preview
        state=self.get_catalog(cid,actor)
        return {**build_preview(state,actor,spec,self._submission_sheet(state,spec)),'version':state['version']}

    def attach(self,cid,actor,expected_version,filename,data,submission_id=None):
        if actor.role not in ('editor','developer'): raise PermissionError('素材を追加する権限がありません。')
        from .assets import ingest_attachment
        attachment,assets=ingest_attachment(data,filename,self.assets_dir)
        with self.store.connection(write=True) as db:
            row=self._row(db,cid)
            if row['version']!=expected_version: raise ConflictError('別の変更が保存されています。画面を更新してください。')
            state=json.loads(row['state'])
            if submission_id and not any(s['id']==submission_id for s in state['submissions']): raise ValueError('原稿が見つかりません。')
            if submission_id and not may_edit(find_submission(state,submission_id),actor):raise PermissionError('自分が登録した原稿に資料を追加してください。')
            attachment.update(author=actor.name,created=now(),submission_id=submission_id)
            state['attachments'].append(attachment);state['document']['assets'].update(assets)
            if submission_id:
                item=find_submission(state,submission_id)
                item['asset_ids']=list(dict.fromkeys(item.get('asset_ids',[])+[attachment['id']]))
            reconcile(json.loads(row['state']),state,actor,'資料の追加')
            version=row['version']+1
            db.execute('INSERT INTO events(catalog_id,version,actor,action,before_state,created) VALUES (?,?,?,?,?,?)',(cid,version,actor.id,'attach',row['state'],now()))
            db.execute('UPDATE catalogs SET state=?,version=? WHERE id=?',(dump(state),version,cid))
        return self.get_catalog(cid,actor)

    def asset_path(self,cid,actor,asset_id):
        if not isinstance(asset_id,str) or Path(asset_id).name!=asset_id or '/' in asset_id or '\\' in asset_id: raise ValueError('素材IDが不正です。')
        st=self.get_catalog(cid,actor)
        permitted=set(st['document']['assets'])
        if actor.role!='reader':
            permitted.update(a['id'] for a in st.get('attachments',[]))
        if asset_id not in permitted: raise PermissionError('この素材は閲覧できません。')
        file=self.assets_dir/asset_id
        if not file.is_file(): raise ValueError('素材ファイルが見つかりません。')
        return file

    def original_document(self,cid,actor):
        if actor.role!='editor': raise PermissionError('原版を出力する権限がありません。')
        with self.store.connection() as db: return json.loads(self._row(db,cid)['original'])
