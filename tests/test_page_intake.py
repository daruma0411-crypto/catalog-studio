import unittest
import test_service

class PageIntakeTests(unittest.TestCase):
    setUp=test_service.ServiceTests.setUp
    def op(self,operation,actor=None):
        actor=actor or self.editor
        state=self.service.get_catalog(self.cid,actor)
        return self.service.apply_operation(self.cid,actor,state['version'],operation)
    def new_page(self):
        return self.op({'type':'add_page','title':'新製品紹介'})['document']['pages'][-1]['id']
    def submit(self,pid):
        return self.op({'type':'add_submission','title':'開発からの原稿','text':'新しい仕様','page_id':pid},self.dev)['submissions'][-1]['id']
    def test_editor_page_developer_submission_and_editor_receipt(self):
        pid=self.new_page()
        self.assertEqual(self.service.get_catalog(self.cid,self.dev)['document']['pages'][-1]['id'],pid)
        sid=self.submit(pid)
        state=self.service.get_catalog(self.cid,self.editor)
        self.assertEqual(state['submissions'][-1]['page_id'],pid)
        self.assertEqual(state['submissions'][-1]['author_id'],self.dev.id)
        self.op({'type':'rename_page','page_id':pid,'title':'更新したページ名'})
        ids=[p['id'] for p in state['document']['pages']]
        self.op({'type':'reorder_pages','page_ids':list(reversed(ids))})
        self.assertEqual(self.service.get_catalog(self.cid,self.dev)['submissions'][-1]['page_id'],pid)
        self.op({'type':'submission_review','submission_id':sid,'agreement':'agreed','page_id':pid,'paper_checked':True})
        state=self.op({'type':'submission_update','submission_id':sid,'page_id':ids[0]},self.dev)
        self.assertEqual(state['submissions'][-1]['agreement'],'recheck')
        self.assertFalse(state['submissions'][-1]['paper_checked'])
    def test_invalid_page_and_role_restrictions(self):
        with self.assertRaises(ValueError):self.submit('missing')
        pid=self.new_page();sid=self.submit(pid)
        with self.assertRaises(ValueError):self.op({'type':'submission_update','submission_id':sid,'page_id':'missing'},self.dev)
        with self.assertRaises(PermissionError):self.op({'type':'add_page','title':'禁止'},self.dev)
        with self.assertRaises(PermissionError):self.op({'type':'rename_page','page_id':pid,'title':'禁止'},self.dev)
        self.op({'type':'publish'})
        self.assertNotIn('submissions',self.service.get_catalog(self.cid,self.reader))
    def test_delete_protection_and_reset_preserve_source(self):
        pid=self.new_page();sid=self.submit(pid)
        with self.assertRaises(ValueError):self.op({'type':'delete_page','page_id':pid})
        state=self.op({'type':'reset_document'})
        item=state['submissions'][-1]
        self.assertIsNone(item['page_id'])
        self.assertEqual(item['previous_page']['id'],pid)
        self.assertEqual(item['text'],'新しい仕様')
        self.assertFalse(item['paper_checked'])
    def test_legacy_unassigned_page_does_not_invalidate_schedule_only_edit(self):
        from catalog_core.submissions import reconcile
        import copy
        old={'submissions':[{'id':'legacy','title':'旧原稿','text':'本文','agreement':'agreed','paper_checked':True,'status':'applied'}],'threads':[]}
        new=copy.deepcopy(old);new['submissions'][0].update(page_id=None,assignee='担当A')
        reconcile(old,new,self.editor)
        item=new['submissions'][0]
        self.assertEqual(item['agreement'],'agreed');self.assertTrue(item['paper_checked'])
        self.assertEqual(item['content_revision'],1)

    def test_upload_receipt_identifies_own_file_during_concurrent_attachment(self):
        original=self.service.get_catalog;inserted=False
        def concurrent_get(cid,actor,**kwargs):
            nonlocal inserted
            if not inserted:
                inserted=True
                current=original(cid,actor)
                self.service.attach(cid,self.editor,current['version'],'other.txt',b'other')
            return original(cid,actor,**kwargs)
        state=original(self.cid,self.dev)
        self.service.get_catalog=concurrent_get
        response=self.service.attach(self.cid,self.dev,state['version'],'mine.txt',b'mine')
        mine=next(a['id'] for a in response['attachments'] if a['name']=='mine.txt')
        self.assertEqual(response['uploaded_asset_id'],mine)
        self.assertNotEqual(response['uploaded_asset_id'],response['attachments'][-1]['id'])
