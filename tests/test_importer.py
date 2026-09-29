import io
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path


def fixture(story_text='ERD9717WA price 18500', linked=False):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        z.writestr('designmap.xml', '<Document xmlns:p="urn:idml"><p:Spread src="Spreads/s.xml"/></Document>')
        z.writestr('Stories/Story_st.xml', '<Package><Story Self="st"><ParagraphStyleRange><CharacterStyleRange PointSize="10"><Content>' + story_text + '</Content></CharacterStyleRange></ParagraphStyleRange></Story></Package>')
        frame = lambda name, x, prev, nxt: f'<TextFrame Self="{name}" ParentStory="st" ItemTransform="1 0 0 1 {x} 30" PreviousTextFrame="{prev}" NextTextFrame="{nxt}"><Properties><PathGeometry><GeometryPathType><PathPointArray><PathPointType Anchor="0 0"/><PathPointType Anchor="100 0"/><PathPointType Anchor="100 40"/><PathPointType Anchor="0 40"/></PathPointArray></GeometryPathType></PathGeometry></Properties></TextFrame>'
        z.writestr('Spreads/s.xml', '<Package><Spread Self="spread"><Page Self="p1" Name="12" GeometricBounds="0 0 300 200" ItemTransform="1 0 0 1 0 0"/>' + frame('f1', 10, 'n', 'f2' if linked else 'n') + (frame('f2', 10, 'f1', 'n') if linked else '') + '</Spread></Package>')
    return out.getvalue()


class ImportTests(unittest.TestCase):
    def setUp(self):
        from catalog_core.importer import parse_idml
        from catalog_core.search import find_occurrences
        self.parse, self.search = parse_idml, find_occurrences
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_coordinates_text_and_reference(self):
        doc = self.parse(fixture(), Path(self.tmp.name))
        self.assertEqual(len(doc['pages']), 1)
        p = doc['pages'][0]
        self.assertEqual(p['source_label'], '12')
        e = next(e for e in p['elements'] if e['kind'] == 'text')
        self.assertEqual(e['bounds'], [10.0, 30.0, 100.0, 40.0])
        self.assertEqual(e['source']['story_id'], 'st')
        result = self.search(doc, 'ERD9717WA')
        self.assertEqual(result['occurrence_count'], 1)
        self.assertEqual(result['page_count'], 1)
        self.assertEqual(result['results'][0]['element_id'], e['id'])

    def test_repeated_text_counts_but_linked_frame_does_not_duplicate(self):
        doc = self.parse(fixture('ERD9717WA / ERD9717WA', linked=True), Path(self.tmp.name))
        self.assertEqual(self.search(doc, 'ERD9717WA')['occurrence_count'], 2)
        self.assertTrue(doc['warnings'])

    def test_rejects_unsafe_zip_and_xml(self):
        malicious = io.BytesIO()
        with zipfile.ZipFile(malicious, 'w') as z:
            z.writestr('../outside.xml', 'bad')
        with self.assertRaises(ValueError):
            self.parse(malicious.getvalue(), Path(self.tmp.name))
        with self.assertRaises(ValueError):
            self.parse(fixture('&notDeclared;'), Path(self.tmp.name))

    def test_real_sample_search_and_table_cells(self):
        source = Path(__file__).resolve().parents[2] / 'out/design-0346/0346.idml'
        if not source.exists():
            self.skipTest('Provided sample is not present')
        doc = self.parse(source.read_bytes(), Path(self.tmp.name))
        self.assertEqual(len(doc['pages']), 1)
        results = self.search(doc, 'ERD9717WA')
        self.assertEqual(results['occurrence_count'], 2)
        self.assertEqual(len({r['element_id'] for r in results['results']}), 2)
        self.assertTrue(any(e['source'].get('cell_id') for e in doc['pages'][0]['elements'] if e['kind'] == 'text'))

    def test_rgb16_psd_composite_is_available_for_preview(self):
        from catalog_core.importer import save_image
        from PIL import Image
        header=b'8BPS'+struct.pack('>H',1)+b'\0'*6+struct.pack('>HIIHH',3,1,2,16,3)
        # Two pixels, red then green, stored as three planar 16-bit channels.
        data=header+b'\0'*12+b'\0\0'+struct.pack('>6H',65535,0,0,65535,0,0)
        asset=save_image(data,Path(self.tmp.name))
        with Image.open(Path(self.tmp.name)/asset) as image:
            self.assertEqual(image.getpixel((0,0)),(255,0,0,255))
            self.assertEqual(image.getpixel((1,0)),(0,255,0,255))

    def test_mixed_table_and_surrounding_text_remain_searchable(self):
        content='<Package><Story Self="st"><ParagraphStyleRange><CharacterStyleRange><Content>BEFORE-MODEL</Content><Table><Row SingleRowHeight="15"/><Column SingleColumnWidth="90"/><Cell Self="c" Name="0:0"><ParagraphStyleRange><CharacterStyleRange><Content>TABLE-MODEL</Content></CharacterStyleRange></ParagraphStyleRange></Cell></Table><Content>AFTER-MODEL</Content></CharacterStyleRange></ParagraphStyleRange></Story></Package>'
        out=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(fixture())) as src, zipfile.ZipFile(out,'w') as dest:
            for n in src.namelist():dest.writestr(n,content if n.startswith('Stories/') else src.read(n))
        doc=self.parse(out.getvalue(),Path(self.tmp.name))
        for term in ['BEFORE-MODEL','TABLE-MODEL','AFTER-MODEL']:
            self.assertEqual(self.search(doc,term)['occurrence_count'],1,term)

    def test_original_link_files_are_retained(self):
        doc=self.parse(fixture(),Path(self.tmp.name),{'print-original.psd':b'original-print-bytes','same-content.psd':b'original-print-bytes'})
        originals=[a for a in doc['assets'].values() if a['kind']=='source-image']
        self.assertEqual(len(originals),1)
        self.assertEqual(set(originals[0]['link_names']),{'print-original.psd','same-content.psd'})
        self.assertEqual((Path(self.tmp.name)/originals[0]['id']).read_bytes(),b'original-print-bytes')


if __name__ == '__main__':
    unittest.main()
