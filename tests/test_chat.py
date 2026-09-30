import copy,json,unittest
from pathlib import Path
from types import SimpleNamespace
import test_service
from test_products import doc
from catalog_core.chat import CatalogTools,ChatEngine,TOOLS
from catalog_core.service import Actor

class ToolTests(unittest.TestCase):
 def setUp(self):
  self.state={'id':'c','title':'test','version':1,'document':doc(),'submissions':[{'id':'s','title':'private','text':'秘密の原稿'}]}
  self.tools=CatalogTools(SimpleNamespace(assets_dir=Path('.')),self.state,Actor('p','販促','editor'))
 def test_price_filter_sort_and_no_mutation(self):
  before=copy.deepcopy(self.state)
  args={'query':'','min_price':None,'max_price':20000,'price_kind':'body','confirmed_only':False,'has_image':False,'sort':'price_asc','offset':0}
  r=self.tools.call('search_products',args)
  self.assertEqual(r['total_models'],1);self.assertTrue(all(p['amount']<=20000 and p['kind']=='body' and not p['confirmed'] for row in r['rows'] for p in row['prices']))
  args['confirmed_only']=True;self.assertEqual(self.tools.call('search_products',args)['rows'],[])
  self.assertEqual(self.state,before)
 def test_thread_message_text_is_returned(self):
  self.state['threads']=[{'id':'t','messages':[{'text':'質問本文'},{'text':'回答本文'}],'status':'open'}]
  result=self.tools.call('search_manuscripts',{'query':'回答本文'})
  self.assertEqual(result['rows'][0]['messages'][1]['text'],'回答本文')
 def test_readonly_allowlist_and_reader(self):
  with self.assertRaises(ValueError):self.tools.call('update_attribute',{})
  with self.assertRaises(ValueError):self.tools.call('get_product',{'model':'RX-359NB','catalog_id':'other'})
  self.tools.actor=Actor('r','閲覧','reader')
  self.assertIn('error',self.tools.call('search_manuscripts',{'query':''}))
  self.assertEqual(self.tools.call('get_product',{'model':'RX-359NB'})['total_models'],1)

class ChatTests(unittest.TestCase):
 setUp=test_service.ServiceTests.setUp
 def test_tool_loop_followup_and_session_isolation(self):
  calls=[]
  def provider(payload):
   calls.append(copy.deepcopy(payload))
   if payload['input'][-1].get('type')!='function_call_output':return {'output':[{'type':'function_call','name':'find_placements','call_id':'call','arguments':json.dumps({'query':'ERD9717WA'})}]}
   return {'output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':'掲載箇所はこちらです。[S1]'}]}]}
  engine=ChatEngine(self.service,provider)
  r=engine.answer(self.cid,self.editor,'session1',{'message':'どこにある？'})
  self.assertTrue(r['sources']);self.assertFalse(calls[0]['store'])
  engine.answer(self.cid,self.editor,'session1',{'message':'そのページは？'})
  self.assertEqual(calls[2]['input'][0]['content'],'どこにある？')
  engine.answer(self.cid,self.editor,'session2',{'message':'初めて'})
  self.assertEqual(len(calls[4]['input']),1)
  st=self.service.get_catalog(self.cid,self.editor);self.service.apply_operation(self.cid,self.editor,st['version'],{'type':'add_page','title':'new'})
  r=engine.answer(self.cid,self.editor,'session1',{'message':'最新版は？'})
  self.assertTrue(r['context_reset']);self.assertEqual(len(calls[6]['input']),1)
 def test_provider_failure_and_reset_do_not_fake_answer(self):
  def fail(payload):raise ValueError('AI unavailable')
  engine=ChatEngine(self.service,fail)
  with self.assertRaisesRegex(ValueError,'AI unavailable'):engine.answer(self.cid,self.editor,'s',{'message':'質問'})
  self.assertTrue(engine.answer(self.cid,self.editor,'s',{'reset':True})['reset'])
  with self.assertRaises(PermissionError):engine.answer(self.cid,self.reader,'s',{'message':'秘密の原稿'})
