import unittest
from test_products import doc
from catalog_core.inquiry import answer

class InquiryTests(unittest.TestCase):
    def test_price_question_returns_table_not_literal_search(self):
        result=answer({'document':doc()},'全ての価格と型番が紐づいたデータを一覧化して')
        self.assertEqual(result['kind'],'prices')
        self.assertEqual(len(result['rows']),2)
        self.assertEqual(result['rows'][0]['prices'][0]['amount'],'9000')
        self.assertFalse(result['rows'][0]['confirmed'])
    def test_model_price_and_placement_question(self):
        state={'document':doc()}
        self.assertEqual(answer(state,'RX-359NBの価格を教えて')['kind'],'prices')
        r=answer(state,'RX-359NBは何か所使われていますか？')
        self.assertEqual(r['kind'],'locations');self.assertEqual(r['search']['occurrence_count'],2)
    def test_unknown_question_is_not_zero_results(self):
        self.assertEqual(answer({'document':doc()},'来年の売上はどうなりますか')['kind'],'unsupported')
    def test_reader_has_no_working_product_review_data(self):
        self.assertEqual(answer({'document':doc()},'全ての型番と価格を一覧にして',allow_products=False)['kind'],'restricted')
    def test_confirmed_filter_does_not_promote_candidates(self):
        self.assertEqual(answer({'document':doc()},'確認済みの型番と価格を一覧にして')['rows'],[])
    def test_plain_keyword_still_works(self):
        self.assertEqual(answer({'document':doc()},'RX-359NB')['search']['occurrence_count'],2)
    def test_unsupported_condition_not_silently_ignored(self):
        self.assertEqual(answer({'document':doc()},'1万円以下の型番と価格を一覧にして')['kind'],'unsupported')
        for query in ['RX-359NBを除く型番と価格を一覧にして','確認済み以外の型番と価格を一覧にして','未確認の型番と価格一覧','セット価格だけ一覧','2ページの型番と価格一覧','赤い商品の型番と価格一覧']:
            with self.subTest(query=query):self.assertEqual(answer({'document':doc()},query)['kind'],'unsupported')
    def test_csv_marks_unconfirmed_price_and_preserves_source(self):
        from catalog_core.inquiry import inquiry_csv
        r=answer({'document':doc()},'型番と価格一覧');r['revision']=3
        csv=inquiry_csv(r).decode('utf-8-sig')
        self.assertIn('9000',csv);self.assertIn('同じ文字枠・未確認',csv);self.assertIn('RX-359NB',csv)
