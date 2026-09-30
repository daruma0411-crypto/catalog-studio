import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from test_importer import fixture


class ExportTests(unittest.TestCase):
    def setUp(self):
        from catalog_core.service import Service,Actor
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.service=Service(Path(self.tmp.name));self.actor=Actor('promo','販促担当','editor')
        self.state=self.service.import_catalog(fixture(),'fixture.idml',self.actor)

    def test_csv_preview_does_not_evaluate_formulas_and_download_escapes_them(self):
        from catalog_core.assets import spreadsheet_preview
        from catalog_core.exports import csv_bytes
        preview=spreadsheet_preview('型番,変更後\nERD9717WA,=1+2\n'.encode(),'input.csv')
        self.assertEqual(preview['sheets'][0]['rows'][1][1],'=1+2')
        value=csv_bytes([['=1+2','@cmd','通常']]).decode('utf-8-sig')
        self.assertIn("'=1+2",value)
        self.assertIn("'@cmd",value)

    def test_package_contains_revision_changes_and_no_html_injection(self):
        from catalog_core.exports import instruction_package
        s=self.state;eid=s['document']['pages'][0]['elements'][0]['id']
        s=self.service.apply_operation(s['id'],self.actor,s['version'],{'type':'edit_text','element_id':eid,'text':'<script>alert(1)</script>'})
        package=instruction_package(self.service,s['id'],self.actor)
        with zipfile.ZipFile(io.BytesIO(package)) as z:
            self.assertIn('instructions.html',z.namelist())
            self.assertIn('manifest.json',z.namelist())
            page=z.read('pages/edited-1.html').decode()
            self.assertNotIn('<script>alert',page)
            self.assertIn('&lt;script&gt;',page)
            self.assertIn('source/original.idml',z.namelist())

    def test_reader_cannot_download_private_attachment(self):
        from catalog_core.service import Actor
        s=self.state
        s=self.service.attach(s['id'],self.actor,s['version'],'draft.csv',b'a,b\n1,2')
        aid=s['attachments'][0]['id']
        s=self.service.apply_operation(s['id'],self.actor,s['version'],{'type':'publish'})
        with self.assertRaises(PermissionError):
            self.service.asset_path(s['id'],Actor('reader','社内','reader'),aid)

    def test_handoff_includes_submission_schedule_and_page_context(self):
        from catalog_core.exports import instruction_package
        s=self.state;pid=s['document']['pages'][0]['id']
        s=self.service.apply_operation(s['id'],self.actor,s['version'],{'type':'add_submission','title':'確認原稿','text':'依頼内容','page_id':pid})
        sid=s['submissions'][0]['id']
        s=self.service.apply_operation(s['id'],self.actor,s['version'],{'type':'submission_update','submission_id':sid,'assignee':'担当A','due_date':'2026-10-01'})
        s=self.service.apply_operation(s['id'],self.actor,s['version'],{'type':'comment','page_id':pid,'text':'このページへの指示'})
        package=instruction_package(self.service,s['id'],self.actor)
        with zipfile.ZipFile(io.BytesIO(package)) as z:
            self.assertIn('submissions.csv',z.namelist())
            csv=z.read('submissions.csv').decode('utf-8-sig')
            self.assertIn('担当A',csv);self.assertIn('2026-10-01',csv);self.assertIn('対象ページID',csv);self.assertIn(pid,csv)
            html=z.read('instructions.html').decode()
            self.assertIn('このページへの指示',html);self.assertIn('p.12',html);self.assertIn('対象ページ：掲載順 1',html)

    def test_missing_attachment_cannot_be_silently_exported(self):
        from catalog_core.exports import instruction_package
        s=self.state
        s=self.service.attach(s['id'],self.actor,s['version'],'source.csv',b'a,b\n1,2')
        (self.service.assets_dir/s['attachments'][0]['id']).unlink()
        with self.assertRaises(ValueError):instruction_package(self.service,s['id'],self.actor)


if __name__=='__main__':unittest.main()
