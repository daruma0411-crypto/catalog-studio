import unittest
import test_service
from test_importer import fixture
from catalog_core.service import ConflictError

class CampaignTests(unittest.TestCase):
    setUp=test_service.ServiceTests.setUp
    def prepare(self):
        self.other=self.service.import_catalog(fixture(),'second.idml',self.editor)['id']
        return self.service.library_search(self.editor,'ERD9717WA',[self.cid,self.other])
    def create(self,results):
        return self.service.create_campaign(self.editor,{'title':'価格改訂','query':'ERD9717WA','instruction':'本体価格を19,800円へ修正。セット価格は別途確認。','targets':[{'catalog_id':r['catalog_id'],'element_id':r['element_id'],'version':r['revision']} for r in results]})
    def op(self,cid,op):
        return self.service.apply_operation(cid,self.editor,self.service.get_catalog(cid,self.editor)['version'],op)
    def test_two_catalogs_partial_completion_and_recheck(self):
        search=self.prepare();self.assertEqual(search['occurrence_count'],2)
        created=self.create(search['results']);self.assertEqual(len(created['targets']),2)
        first=created['targets'][0]
        for status in ['fixed','verified']:
            self.op(first['catalog_id'],{'type':'change_status','change_id':first['change_id'],'status':status})
        detail=self.service.campaigns(self.editor)[0]
        self.assertFalse(detail['complete']);self.assertEqual(detail['counts']['verified'],1)
        self.op(first['catalog_id'],{'type':'edit_text','element_id':first['element_id'],'text':'ERD9717WA price 20000'})
        self.assertEqual(self.service.campaigns(self.editor)[0]['counts']['recheck'],1)
    def test_duplicate_occurrences_in_one_frame_and_restart(self):
        self.op(self.cid,{'type':'edit_text','element_id':'f1','text':'ERD9717WA と ERD9717WA'})
        result=self.service.library_search(self.editor,'ERD9717WA',[self.cid])
        self.assertEqual(result['occurrence_count'],2);self.assertEqual(result['target_count'],1)
        created=self.create(result['results'])
        from catalog_core.service import Service
        restarted=Service(self.tmp.name)
        self.assertEqual(restarted.campaigns(self.editor)[0]['id'],created['id'])
        target=created['targets'][0]
        self.op(self.cid,{'type':'change_status','change_id':target['change_id'],'status':'verified'})
        self.assertTrue(restarted.campaigns(self.editor)[0]['complete'])
        self.op(self.cid,{'type':'delete','element_id':'f1','space_policy':'空きを残す'})
        self.assertFalse(restarted.campaigns(self.editor)[0]['complete'])
        with self.assertRaises(ValueError):self.op(self.cid,{'type':'change_status','change_id':target['change_id'],'status':'verified'})
    def test_conflict_rolls_back_every_catalog(self):
        search=self.prepare();before=self.service.get_catalog(self.cid,self.editor)
        self.op(self.other,{'type':'add_page','title':'changed'})
        with self.assertRaises(ConflictError):self.create(search['results'])
        after=self.service.get_catalog(self.cid,self.editor)
        self.assertEqual(before['version'],after['version']);self.assertEqual(self.service.campaigns(self.editor),[])
    def test_selection_and_permissions_and_missing(self):
        search=self.prepare();untouched=self.service.get_catalog(self.other,self.editor)
        created=self.create([next(r for r in search['results'] if r['catalog_id']==self.cid)])
        self.assertEqual(self.service.get_catalog(self.other,self.editor)['version'],untouched['version'])
        with self.assertRaises(PermissionError):self.service.create_campaign(self.dev,{})
        with self.assertRaises(PermissionError):self.service.campaigns(self.reader)
        with self.assertRaises(PermissionError):self.service.library_search(self.reader,'ERD9717WA',[self.cid])
        self.assertEqual(len(self.service.campaigns(self.dev)),1)
        with self.assertRaises(ValueError):self.op(self.cid,{'type':'undo'})
        self.op(self.cid,{'type':'reset_document'})
        self.assertEqual(self.service.campaigns(self.editor)[0]['counts']['missing'],1)
        self.assertFalse(self.service.campaigns(self.editor)[0]['complete'])
