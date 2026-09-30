import copy
import unittest
from test_products import doc
import test_service
from catalog_core.product_images import image_resources
from catalog_core.products import report

class ImageResourcesTests(unittest.TestCase):
    def test_preview_original_candidates_and_usage_are_distinct(self):
        state={'document':doc(),'attachments':[{'id':'uploaded.tif','name':'upload.tif','preview_asset':'image'}]}
        state['document']['assets']['source.tif']={'name':'light.png','kind':'source-image'}
        state['document']['assets']['other.tif']={'name':'unrelated.tif','kind':'source-image'}
        oid=report(state)['occurrences'][0]['id']
        image=image_resources(state,oid,lambda aid:aid!='source.tif')['images'][0]
        self.assertFalse(image['product_confirmed']);self.assertTrue(image['preview']['available'])
        self.assertEqual([a['association'] for a in image['originals']],['explicit','name_candidate'])
        self.assertFalse(image['originals'][1]['available']);self.assertEqual(len(image['uses']),1)
        self.assertNotIn('other.tif',str(image))
        state['document']['pages'][0]['elements'][-1]['asset_id']='replacement'
        state['document']['assets']['replacement']={'name':'new.png','kind':'image'}
        image=image_resources(state,oid,lambda _:True)['images'][0]
        self.assertEqual(image['originals'],[])

    def test_confirmed_review_becomes_unconfirmed_after_change(self):
        state={'document':doc()};o=report(state)['occurrences'][0]
        state['product_reviews']={o['id']:{'fingerprint':o['fingerprint'],'status':'confirmed','image_ids':['i']}}
        self.assertTrue(image_resources(state,o['id'],lambda _:True)['images'][0]['product_confirmed'])
        state['document']['pages'][0]['elements'][0]['text']+=' changed'
        self.assertFalse(image_resources(state,o['id'],lambda _:True)['images'][0]['product_confirmed'])
        with self.assertRaises(ValueError):image_resources(state,'missing',lambda _:True)

class ImageResourceServiceTests(unittest.TestCase):
    setUp=test_service.ServiceTests.setUp
    def test_roles_and_missing_files(self):
        o=self.service.products(self.cid,self.editor)['occurrences'][0]
        result=self.service.product_images(self.cid,self.dev,o['id'])
        self.assertEqual(result['revision'],1);self.assertEqual(result['catalog_id'],self.cid)
        with self.assertRaises(PermissionError):self.service.product_images(self.cid,self.reader,o['id'])
