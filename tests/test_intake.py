import unittest,tempfile,copy
from pathlib import Path
from test_importer import fixture
from catalog_core.service import Service,Actor

class IntakeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.s=Service(Path(self.tmp.name));self.editor=Actor('promo','販促','editor');self.dev=Actor('development','開発','developer')
  self.st=self.s.import_catalog(fixture(),'test.idml',self.editor);self.cid=self.st['id']
  self.op({'type':'add_submission','title':'指示','text':'本文'},self.dev);self.sid=self.st['submissions'][0]['id']
 def op(self,op,actor=None):
  self.st=self.s.apply_operation(self.cid,actor or self.editor,self.st['version'],op);return self.st
 def test_review_permission_and_recheck(self):
  pid=self.st['document']['pages'][0]['id']
  review={'type':'submission_review','submission_id':self.sid,'agreement':'agreed','paper_checked':True,'page_id':pid}
  with self.assertRaises(PermissionError):self.op(review,self.dev)
  self.op(review);self.assertTrue(self.st['submissions'][0]['paper_checked'])
  eid=self.st['document']['pages'][0]['elements'][0]['id']
  self.op({'type':'edit_text','element_id':eid,'text':'updated'})
  self.assertFalse(self.st['submissions'][0]['paper_checked']);self.assertEqual(self.st['submissions'][0]['agreement'],'agreed')
 def test_assets_must_exist(self):
  with self.assertRaises(ValueError):self.op({'type':'submission_assets','submission_id':self.sid,'asset_ids':['missing']},self.dev)
  self.op({'type':'submission_assets','submission_id':self.sid,'asset_ids':[]},self.dev)
 def test_group_instruction_does_not_change_paper(self):
  pid=self.st['document']['pages'][0]['id']
  self.op({'type':'add_text','page_id':pid,'text':'追加の文章','bounds':[10,20,60,20]})
  p=self.st['document']['pages'][0];ids=[e['id'] for e in p['elements'][:2]]
  self.op({'type':'create_group','name':'対象商品','element_ids':ids});gid=self.st['document']['groups'][0]['id'];before=copy.deepcopy(self.st['document'])
  self.op({'type':'comment','group_id':gid,'text':'165ページ左下','destination':'production'})
  self.assertEqual(before,self.st['document']);self.assertEqual(self.st['threads'][-1]['group_id'],gid);self.assertEqual(self.st['threads'][-1]['element_ids'],ids)
 def test_blank_page_can_receive_instruction_without_text_element(self):
  self.op({'type':'add_page','title':'新商品ページ'});pid=self.st['document']['pages'][-1]['id']
  self.op({'type':'comment','page_id':pid,'destination':'production','text':'添付資料を使って配置してください'})
  self.assertEqual(self.st['threads'][-1]['page_id'],pid)
  self.assertEqual(self.st['document']['pages'][-1]['elements'],[])
