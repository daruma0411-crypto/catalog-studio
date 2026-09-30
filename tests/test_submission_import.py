import unittest
import test_service
from catalog_core.service import ConflictError

class SubmissionImportTests(unittest.TestCase):
    setUp=test_service.ServiceTests.setUp
    def test_xlsx_without_dimensions_rejects_partial_import(self):
        import io
        from openpyxl import Workbook
        from catalog_core.assets import spreadsheet_preview
        from catalog_core.submission_import import build_preview
        for row_count,col_count in [(211,4),(2,41),(2,4)]:
            wb=Workbook(write_only=True);ws=wb.create_sheet()
            ws.append(['ID','Title','Text','Target']+['extra']*(col_count-4))
            for i in range(row_count-1):ws.append([str(i),'Title','Body','Model']+['value']*(col_count-4))
            out=io.BytesIO();wb.save(out)
            preview=spreadsheet_preview(out.getvalue(),'test.xlsx')
            self.assertEqual(preview['sheets'][0]['truncated'],row_count>200 or col_count>40)
            args=({'submissions':[]},self.dev,{'namespace':'test','columns':{'key':0,'title':1,'text':2,'target':3}},preview)
            if row_count>200 or col_count>40:
                with self.assertRaises(ValueError):build_preview(*args)
            else:self.assertEqual(build_preview(*args)['errors'],[])
    def test_default_sheet_and_trimmed_namespace(self):
        spec=self.upload('001,Title,Body,Model');spec.pop('sheet');spec['namespace']=' test '
        self.assertEqual(self.preview(spec)['counts']['new'],1)
        state=self.apply_import(spec)
        self.assertEqual(state['submission_imports'][0]['namespace'],'test')
        self.assertEqual(state['submission_imports'][0]['sheet'],0)
    def op(self,operation,actor=None):
        st=self.service.get_catalog(self.cid,self.editor)
        return self.service.apply_operation(self.cid,actor or self.editor,st['version'],operation)
    def upload(self,rows,name='draft.csv'):
        st=self.service.get_catalog(self.cid,self.editor)
        st=self.service.attach(self.cid,self.dev,st['version'],name,('ID,件名,本文,型番\n'+rows).encode('utf-8'))
        return {'asset_id':st['attachments'][-1]['id'],'sheet':0,'namespace':'開発原稿','columns':{'key':0,'title':1,'text':2,'target':3}}
    def preview(self,spec):return self.service.preview_submission_import(self.cid,self.dev,spec)
    def apply_import(self,spec,**extra):return self.op({'type':'import_submissions',**spec,**extra},self.dev)
    def test_repeat_and_reorder_do_not_duplicate(self):
        spec=self.upload('001,製品A,原稿A,A-1\n002,製品B,原稿B,B-1')
        self.assertEqual(self.preview(spec)['counts']['new'],2)
        st=self.apply_import(spec);ids={s['target']:s['id'] for s in st['submissions']}
        spec=self.upload('002,製品B,原稿B,B-1\n001,製品A,原稿A,A-1','renamed.csv')
        self.assertEqual(self.preview(spec)['counts']['unchanged'],2)
        st=self.apply_import(spec);self.assertEqual(ids,{s['target']:s['id'] for s in st['submissions']})
        self.assertEqual(len(st['submissions']),2)
    def test_update_invalidates_agreement_and_preserves_history(self):
        spec=self.upload('001,製品A,原稿A,A-1');st=self.apply_import(spec);sid=st['submissions'][0]['id']
        self.op({'type':'submission_review','submission_id':sid,'agreement':'agreed'})
        spec=self.upload('001,製品A,改訂A,A-1');self.assertEqual(self.preview(spec)['counts']['update'],1)
        s=self.apply_import(spec)['submissions'][0]
        self.assertEqual(s['text'],'改訂A');self.assertEqual(s['agreement'],'recheck');self.assertEqual(s['content_revision'],2)
    def test_conflicting_edit_requires_explicit_choice(self):
        spec=self.upload('001,製品A,原稿A,A-1');sid=self.apply_import(spec)['submissions'][0]['id']
        self.op({'type':'submission_update','submission_id':sid,'text':'画面で補足'})
        spec=self.upload('001,製品A,Excel改訂,A-1')
        self.assertEqual(self.preview(spec)['counts']['conflict'],1)
        with self.assertRaises(ValueError):self.apply_import(spec)
        st=self.apply_import(spec,resolutions={'001':'keep'});self.assertEqual(st['submissions'][0]['text'],'画面で補足')
        self.assertEqual(self.preview(spec)['counts']['local_only'],1)
        spec=self.upload('001,製品A,Excel再改訂,A-1')
        st=self.apply_import(spec,resolutions={'001':'incoming'});self.assertEqual(st['submissions'][0]['text'],'Excel再改訂')
    def test_duplicate_missing_and_formula_keys_are_atomic_errors(self):
        for rows in ['001,A,本文,A\n001,B,本文,B',',A,本文,A','=1+1,A,本文,A']:
            spec=self.upload(rows);p=self.preview(spec);self.assertTrue(p['errors'])
            with self.assertRaises(ValueError):self.apply_import(spec)
            self.assertEqual(self.service.get_catalog(self.cid,self.editor)['submissions'],[])
    def test_removed_row_is_not_deleted_and_no_false_update(self):
        spec=self.upload('001,A,本文,A\n002,B,本文,B');st=self.apply_import(spec)
        sid=st['submissions'][0]['id'];self.op({'type':'submission_update','submission_id':sid,'text':'画面変更'})
        spec=self.upload('001,A,本文,A')
        self.assertEqual(self.preview(spec)['counts']['local_only'],1)
        st=self.apply_import(spec);self.assertEqual(len(st['submissions']),2);self.assertEqual(st['submissions'][0]['text'],'画面変更')
    def test_truncation_and_permissions_and_stale_version(self):
        spec=self.upload('\n'.join(f'{i},A,本文,A' for i in range(210)))
        with self.assertRaises(ValueError):self.preview(spec)
        spec=self.upload('001,A,本文,A');p=self.preview(spec)
        with self.assertRaises(PermissionError):self.service.preview_submission_import(self.cid,self.reader,spec)
        self.op({'type':'add_submission','title':'別原稿','text':'本文'})
        with self.assertRaises(ConflictError):self.service.apply_operation(self.cid,self.dev,p['version'],{'type':'import_submissions',**spec})
