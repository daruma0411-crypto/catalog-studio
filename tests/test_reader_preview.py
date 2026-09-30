import unittest
import test_service
from catalog_core.service import Service

class ReaderPreviewTests(unittest.TestCase):
    setUp=test_service.ServiceTests.setUp
    def test_opt_in_preview_shares_pages_without_private_workflow(self):
        preview=Service(self.tmp.name,reader_preview=True)
        state=preview.get_catalog(self.cid,self.editor)
        state=preview.apply_operation(self.cid,self.editor,state['version'],{'type':'add_page','title':'作成途中'})
        state=preview.apply_operation(self.cid,self.dev,state['version'],{'type':'add_submission','title':'社内原稿','text':'非表示'})
        state=preview.attach(self.cid,self.dev,state['version'],'private.txt',b'private')
        self.assertEqual(len(preview.list_catalogs(self.reader)),1)
        result=preview.get_catalog(self.cid,self.reader)
        self.assertTrue(result['preview']);self.assertTrue(result['readonly'])
        self.assertEqual(len(result['document']['pages']),2)
        for key in ('submissions','threads','attachments','changes'):self.assertNotIn(key,result)
        with self.assertRaises(PermissionError):preview.asset_path(self.cid,self.reader,state['attachments'][-1]['id'])
        with self.assertRaises(PermissionError):preview.apply_operation(self.cid,self.reader,state['version'],{'type':'add_page'})
        self.assertEqual(self.service.list_catalogs(self.reader),[])
        with self.assertRaises(PermissionError):self.service.get_catalog(self.cid,self.reader)

    def test_released_download_stays_published_even_when_preview_is_enabled(self):
        import io,json,zipfile
        from catalog_core.exports import released_package
        preview=Service(self.tmp.name,reader_preview=True)
        with self.assertRaises(PermissionError):released_package(preview,self.cid,self.reader)
        state=preview.get_catalog(self.cid,self.editor)
        state=preview.apply_operation(self.cid,self.editor,state['version'],{'type':'publish'})
        state=preview.apply_operation(self.cid,self.editor,state['version'],{'type':'add_page','title':'未確定ページ'})
        self.assertEqual(len(preview.get_catalog(self.cid,self.reader)['document']['pages']),2)
        with zipfile.ZipFile(io.BytesIO(released_package(preview,self.cid,self.reader))) as z:
            saved=json.loads(z.read('catalog.json'))
            self.assertEqual(len(saved['document']['pages']),1)
            self.assertNotIn('preview',saved)
