import tempfile
import unittest
from pathlib import Path
from test_importer import fixture


class ServiceTests(unittest.TestCase):
    def setUp(self):
        from catalog_core.service import Service, Actor
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service=Service(Path(self.tmp.name))
        self.editor=Actor('promo','販促担当','editor')
        self.reader=Actor('reader','社内ユーザー','reader')
        self.dev=Actor('development','開発部門','developer')
        self.cid=self.service.import_catalog(fixture(), 'test.idml', self.editor)['id']

    def test_draft_release_and_reader_write_permissions(self):
        s=self.service
        with self.assertRaises(PermissionError): s.get_catalog(self.cid,self.reader)
        state=s.get_catalog(self.cid,self.editor)
        element=state['document']['pages'][0]['elements'][0]
        state=s.apply_operation(self.cid,self.editor,state['version'],{'type':'edit_text','element_id':element['id'],'text':'PRIVATE MODEL','reason':'draft'})
        with self.assertRaises(PermissionError): s.apply_operation(self.cid,self.reader,state['version'],{'type':'publish'})
        with self.assertRaises(PermissionError): s.apply_operation(self.cid,self.dev,state['version'],{'type':'edit_text','element_id':element['id'],'text':'illegal'})
        state=s.apply_operation(self.cid,self.editor,state['version'],{'type':'publish'})
        self.assertEqual(s.search(self.cid,self.reader,'PRIVATE')['occurrence_count'],1)
        state=s.apply_operation(self.cid,self.editor,state['version'],{'type':'edit_text','element_id':element['id'],'text':'NEW PRIVATE'})
        self.assertEqual(s.search(self.cid,self.reader,'NEW')['occurrence_count'],0)
        self.assertNotIn('submissions',s.get_catalog(self.cid,self.reader))

    def test_conflict_and_restart_persistence(self):
        from catalog_core.service import ConflictError, Service
        s=self.service
        st=s.get_catalog(self.cid,self.editor)
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'add_page','title':'新規'})
        with self.assertRaises(ConflictError):
            s.apply_operation(self.cid,self.editor,1,{'type':'add_page','title':'stale'})
        restored=Service(Path(self.tmp.name)).get_catalog(self.cid,self.editor)
        self.assertEqual(len(restored['document']['pages']),2)
        self.assertEqual(restored['version'],st['version'])

    def test_scoped_replace_undo_and_flow_preserve_text(self):
        s=self.service; st=s.get_catalog(self.cid,self.editor)
        eid=st['document']['pages'][0]['elements'][0]['id']
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'replace_text','element_id':eid,'before':'18500','after':'19800'})
        self.assertIn('19800',st['document']['pages'][0]['elements'][0]['text'])
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'undo'})
        self.assertIn('18500',st['document']['pages'][0]['elements'][0]['text'])
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'flow_text','element_id':eid,'split_at':10,'title':'続き'})
        texts=[e['text'] for p in st['document']['pages'] for e in p['elements'] if e['kind']=='text']
        self.assertEqual(''.join(texts),'ERD9717WA price 18500')
        self.assertEqual(len(st['document']['pages']),2)

    def test_questions_input_and_resolution(self):
        s=self.service;st=s.get_catalog(self.cid,self.dev)
        st=s.apply_operation(self.cid,self.dev,st['version'],{'type':'add_submission','title':'価格改定','text':'価格を変更','target':'ERD9717WA'})
        sid=st['submissions'][0]['id']
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'comment','text':'適用範囲は？','destination':'developer','submission_id':sid})
        thread=st['threads'][0]['id']
        st=s.apply_operation(self.cid,self.dev,st['version'],{'type':'reply','thread_id':thread,'text':'2400TYPEのみ'})
        self.assertEqual(st['threads'][0]['status'],'open')
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'resolve_thread','thread_id':thread})
        self.assertEqual(st['threads'][0]['status'],'resolved')

    def test_reset_restores_pages_preserves_materials_and_release_and_is_undoable(self):
        s=self.service;st=s.get_catalog(self.cid,self.editor)
        original=st['document']['pages'];eid=original[0]['elements'][0]['id']
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'edit_text','element_id':eid,'text':'RELEASED'})
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'publish'})
        st=s.attach(self.cid,self.editor,st['version'],'input.csv',b'a,b\n1,2')
        st=s.apply_operation(self.cid,self.dev,st['version'],{'type':'add_submission','title':'原稿','text':'説明'})
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'add_page','title':'追加'})
        pid=st['document']['pages'][-1]['id']
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'comment','page_id':pid,'text':'新規ページの指示'})
        before=st
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'reset_document'})
        self.assertEqual(st['document']['pages'],original)
        self.assertEqual(st['changes'],[])
        self.assertEqual(st['attachments'],before['attachments'])
        self.assertEqual(st['submissions'],before['submissions'])
        self.assertEqual(st['threads'][0]['messages'],before['threads'][0]['messages'])
        self.assertIsNone(st['threads'][0]['page_id'])
        self.assertEqual(st['threads'][0]['previous_target']['page_id'],pid)
        self.assertEqual(s.search(self.cid,self.reader,'RELEASED')['occurrence_count'],1)
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'undo'})
        for key in ('document','changes','attachments','submissions','threads'):self.assertEqual(st[key],before[key])

    def test_reset_requires_editor_and_current_version(self):
        from catalog_core.service import ConflictError
        s=self.service;st=s.get_catalog(self.cid,self.editor)
        for actor in (self.dev,self.reader):
            with self.assertRaises(PermissionError):s.apply_operation(self.cid,actor,st['version'],{'type':'reset_document'})
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'add_page','title':'追加'})
        with self.assertRaises(ConflictError):s.apply_operation(self.cid,self.editor,1,{'type':'reset_document'})
        self.assertEqual(len(s.get_catalog(self.cid,self.editor)['document']['pages']),2)

    def test_login_and_explicit_role(self):
        session=self.service.login('promo','promo-demo')
        actor=self.service.authenticate(session['token'])
        self.assertEqual(actor.role,'editor')
        with self.assertRaises(PermissionError): self.service.login('promo','wrong')
        self.service.logout(session['token'])
        with self.assertRaises(PermissionError): self.service.authenticate(session['token'])

    def test_published_auto_title_does_not_retain_removed_text(self):
        s=self.service
        st=s.import_catalog(fixture('ORIGINAL CONFIDENTIAL'),'private.idml',self.editor)
        eid=st['document']['pages'][0]['elements'][0]['id']
        st=s.apply_operation(st['id'],self.editor,st['version'],{'type':'edit_text','element_id':eid,'text':'PUBLIC TEXT'})
        st=s.apply_operation(st['id'],self.editor,st['version'],{'type':'publish'})
        import json
        released=json.dumps(s.get_catalog(st['id'],self.reader))
        self.assertNotIn('ORIGINAL CONFIDENTIAL',released)

    def test_corrected_answer_requires_reconfirmation(self):
        s=self.service;st=s.get_catalog(self.cid,self.editor)
        eid=st['document']['pages'][0]['elements'][0]['id']
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'edit_text','element_id':eid,'text':'updated'})
        change=st['changes'][0]['id']
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'change_status','change_id':change,'status':'verified'})
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'comment','element_id':eid,'text':'確認','destination':'developer'})
        tid=st['threads'][0]['id']
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'resolve_thread','thread_id':tid})
        st=s.apply_operation(self.cid,self.dev,st['version'],{'type':'reply','thread_id':tid,'text':'先ほどの回答を訂正します'})
        self.assertEqual(st['threads'][0]['status'],'open')
        self.assertEqual(st['changes'][0]['status'],'open')
        with self.assertRaises(ValueError):s.apply_operation(self.cid,self.editor,st['version'],{'type':'publish'})

    def test_cross_page_move_updates_comments_and_reference_mask(self):
        s=self.service;st=s.get_catalog(self.cid,self.editor)
        original=st['document']['pages'][0]['id'];eid=st['document']['pages'][0]['elements'][0]['id']
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'comment','element_id':eid,'text':'確認','destination':'production'})
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'add_page','title':'送り先'})
        dest=st['document']['pages'][1]['id']
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'move','element_id':eid,'page_id':dest,'bounds':[20,40,100,40]})
        self.assertEqual(st['threads'][0]['page_id'],dest)
        self.assertEqual(st['document']['pages'][0]['removed_regions'][0]['element_id'],eid)


if __name__=='__main__': unittest.main()
