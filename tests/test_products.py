import copy
import unittest
import test_service
from catalog_core.products import extract_index,report,review_product,product_csv
from catalog_core.service import Actor

def doc():
    return {'pages':[{'id':'p','label':'1','title':'照明','elements':[
        {'id':'a','kind':'text','text':'RX-359NB 本体価格 ¥9,000','bounds':[10,10,100,30],'source':{'story_id':'s'}},
        {'id':'b','kind':'text','text':'RX-359NB セット価格 ¥27,500','bounds':[10,60,100,30],'source':{}},
        {'id':'u','kind':'text','text':'L210 1400TYPE 3000K 21.0W','bounds':[150,10,100,30],'source':{}},
        {'id':'i','kind':'image','name':'light.png','asset_id':'image','bounds':[10,100,100,30],'source':{}}
    ]}],'assets':{'image':{'name':'light.png'}},'warnings':[]}

class ProductExtractionTests(unittest.TestCase):
    def test_duplicate_placements_prices_are_candidates_not_confirmed(self):
        state={'document':doc()};index=extract_index(state['document'])
        self.assertEqual(len(index['occurrences']),2)
        r=report(state);self.assertEqual(r['model_count'],1);self.assertEqual(r['occurrence_count'],2)
        self.assertTrue(all(o['status']=='pending' for o in r['occurrences']))
        first=r['occurrences'][0];self.assertEqual(first['price_candidates'][0]['amount'],'9000')
        self.assertEqual(first['price_candidates'][0]['relation'],'same_frame')
        self.assertEqual(first['price_candidates'][0]['kind'],'body')
        self.assertEqual(first['image_candidates'][0]['asset_id'],'image')
    def test_deleted_text_and_unit_numbers_are_not_products(self):
        d=doc();d['pages'][0]['elements'][0]['deleted']=True
        self.assertEqual(len(extract_index(d)['occurrences']),1)

    def test_confirmed_price_is_not_exported_after_source_changes(self):
        state={'document':doc()};o=report(state)['occurrences'][0]
        review_product(state,Actor('p','販促','editor'),{'occurrence_id':o['id'],'fingerprint':o['fingerprint'],'status':'confirmed','price_state':'confirmed','prices':[{'id':o['price_candidates'][0]['id'],'kind':'body'}],'note':'=FORMULA()'})
        import csv,io
        rows=list(csv.reader(io.StringIO(product_csv(report(state)).decode('utf-8-sig'))))
        self.assertEqual(rows[1][6],'本体:9000');self.assertEqual(rows[1][13],"'=FORMULA()")
        state['document']['pages'][0]['elements'][0]['text']='RX-359NB 本体価格 ¥10,000'
        changed=report(state);self.assertEqual(changed['occurrences'][0]['status'],'recheck')
        rows=list(csv.reader(io.StringIO(product_csv(changed).decode('utf-8-sig'))));self.assertEqual(rows[1][6],'')
        state['document']['pages'][0]['elements'][0]['deleted']=True
        self.assertEqual(report(state)['orphan_review_count'],1)

    def test_same_model_on_another_page_keeps_independent_review(self):
        d=doc();p=copy.deepcopy(d['pages'][0]);p['id']='p2';d['pages'].append(p)
        state={'document':d};r=report(state);self.assertEqual(r['model_count'],1);self.assertEqual(r['occurrence_count'],4)
        o=r['occurrences'][0]
        review_product(state,Actor('p','販促','editor'),{'occurrence_id':o['id'],'fingerprint':o['fingerprint'],'status':'ignored'})
        d['pages'][1]['elements'][0]['text']='RX-359NB ¥99,000'
        self.assertEqual(report(state)['occurrences'][0]['status'],'ignored')

class ProductServiceTests(unittest.TestCase):
    setUp=test_service.ServiceTests.setUp
    def get(self):return self.service.products(self.cid,self.editor)
    def op(self,operation,actor=None):
        s=self.service.get_catalog(self.cid,self.editor)
        return self.service.apply_operation(self.cid,actor or self.editor,s['version'],operation)
    def test_import_candidates_confirm_and_recheck(self):
        self.assertIn('product_index',self.service.get_catalog(self.cid,self.editor))
        o=self.get()['occurrences'][0]
        self.op({'type':'product_review','occurrence_id':o['id'],'fingerprint':o['fingerprint'],'status':'confirmed','price_state':'unavailable','prices':[],'image_ids':[],'description_ids':[],'note':'円表記なし'})
        self.assertEqual(self.get()['occurrences'][0]['status'],'confirmed')
        self.op({'type':'edit_text','element_id':o['element_id'],'text':'ERD9717WA ¥19,800'})
        self.assertEqual(self.get()['occurrences'][0]['status'],'recheck')
        with self.assertRaises(ValueError):self.op({'type':'product_review','occurrence_id':o['id'],'fingerprint':o['fingerprint'],'status':'ignored'})
    def test_review_permissions_and_invalid_price_link(self):
        o=self.get()['occurrences'][0];op={'type':'product_review','occurrence_id':o['id'],'fingerprint':o['fingerprint'],'status':'confirmed','price_state':'confirmed','prices':[{'id':'fake','kind':'body'}],'image_ids':[],'description_ids':[]}
        with self.assertRaises(ValueError):self.op(op)
        with self.assertRaises(PermissionError):self.op(op,self.dev)
        with self.assertRaises(PermissionError):self.service.products(self.cid,self.reader)
        self.assertEqual(self.service.products(self.cid,self.dev)['model_count'],1)
