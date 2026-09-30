import unittest
import test_service

class WorkflowTests(unittest.TestCase):
    setUp=test_service.ServiceTests.setUp

    def op(self,op,actor=None):
        st=self.service.get_catalog(self.cid,actor or self.editor)
        return self.service.apply_operation(self.cid,actor or self.editor,st['version'],op)

    def seed(self):
        return self.op({'type':'add_submission','title':'仕様改訂','target':'MODEL-1','text':'価格は9000円'},self.dev)['submissions'][0]['id']

    def test_schedule_validation_and_persistence(self):
        sid=self.seed()
        st=self.op({'type':'submission_update','submission_id':sid,'assignee':'販促担当','due_date':'2026-10-01','ready_date':'2026-10-10'})
        self.assertEqual(st['submissions'][0]['assignee'],'販促担当')
        self.assertEqual(self.service.get_catalog(self.cid,self.editor)['submissions'][0]['due_date'],'2026-10-01')
        for bad in ['2026-02-30','20261001','tomorrow',12]:
            with self.assertRaises(ValueError):self.op({'type':'submission_update','submission_id':sid,'due_date':bad})
        st=self.op({'type':'submission_update','submission_id':sid,'due_date':''})
        self.assertEqual(st['submissions'][0]['due_date'],'')

    def test_content_revision_invalidates_review_but_schedule_does_not(self):
        sid=self.seed();pid=self.service.get_catalog(self.cid,self.editor)['document']['pages'][0]['id']
        self.op({'type':'submission_review','submission_id':sid,'agreement':'agreed','paper_checked':True,'page_id':pid})
        st=self.op({'type':'submission_update','submission_id':sid,'assignee':'担当A'})
        self.assertEqual(st['submissions'][0]['agreement'],'agreed');self.assertTrue(st['submissions'][0]['paper_checked'])
        st=self.op({'type':'submission_update','submission_id':sid,'text':'価格は9800円','reason':'価格改訂'},self.dev)
        s=st['submissions'][0]
        self.assertEqual(s['content_revision'],2);self.assertEqual(s['agreement'],'recheck');self.assertFalse(s['paper_checked'])
        self.assertEqual(s['history'][-1]['before']['text'],'価格は9000円')
        self.assertEqual(s['history'][-1]['reason'],'価格改訂')
        self.assertEqual(s['agreed_content_revision'],1)

    def test_new_question_and_reply_reopen_review(self):
        sid=self.seed();self.op({'type':'submission_review','submission_id':sid,'agreement':'agreed'})
        st=self.op({'type':'comment','submission_id':sid,'text':'適用日は？'},self.dev)
        self.assertEqual(st['submissions'][0]['agreement'],'recheck')
        with self.assertRaises(ValueError):self.op({'type':'submission_review','submission_id':sid,'agreement':'agreed'})
        tid=st['threads'][0]['id'];self.op({'type':'resolve_thread','thread_id':tid})
        self.op({'type':'submission_review','submission_id':sid,'agreement':'agreed'})
        st=self.op({'type':'reply','thread_id':tid,'text':'追加で確認したい'},self.dev)
        self.assertEqual(st['submissions'][0]['agreement'],'recheck')

    def test_attachment_change_requires_review(self):
        sid=self.seed();self.op({'type':'submission_review','submission_id':sid,'agreement':'agreed'})
        st=self.service.get_catalog(self.cid,self.editor)
        st=self.service.attach(self.cid,self.dev,st['version'],'input.txt',b'changed',sid)
        self.assertEqual(st['submissions'][0]['agreement'],'recheck')
        self.assertEqual(st['submissions'][0]['content_revision'],2)

    def test_developer_cannot_edit_other_authors_or_schedule(self):
        sid=self.op({'type':'add_submission','title':'販促原稿','text':'本文'})['submissions'][0]['id']
        with self.assertRaises(PermissionError):self.op({'type':'submission_update','submission_id':sid,'text':'変更'},self.dev)
        sid=self.seed()
        with self.assertRaises(PermissionError):self.op({'type':'submission_update','submission_id':sid,'assignee':'担当A'},self.dev)
        with self.assertRaises(PermissionError):self.op({'type':'submission_update','submission_id':sid,'text':'変更'},self.reader)
