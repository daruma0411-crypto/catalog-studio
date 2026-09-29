import copy
import unittest
import test_service

class GroupTests(unittest.TestCase):
    setUp=test_service.ServiceTests.setUp
    def test_group_geometry_provenance_atomicity_undo(self):
        s=self.service;st=s.get_catalog(self.cid,self.editor);p=st['document']['pages'][0];eid=p['elements'][0]['id']
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'add_text','page_id':p['id'],'text':'離れた価格','bounds':[120,90,60,20]})
        second=st['changes'][-1]['element_id']
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'create_group','name':'商品A','element_ids':[eid,second]})
        gid=st['document']['groups'][0]['id'];before=copy.deepcopy(st)
        with self.assertRaises(ValueError):s.apply_operation(self.cid,self.editor,st['version'],{'type':'move_group','group_id':gid,'delta':[1000,0]})
        self.assertEqual(s.get_catalog(self.cid,self.editor)['document'],before['document'])
        with self.assertRaises(PermissionError):s.apply_operation(self.cid,self.dev,st['version'],{'type':'move_group','group_id':gid,'delta':[5,5]})
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'move_group','group_id':gid,'delta':[5,8]})
        for old,new in zip(before['document']['pages'][0]['elements'],st['document']['pages'][0]['elements']):
            self.assertEqual(new['bounds'][:2],[old['bounds'][0]+5,old['bounds'][1]+8]);self.assertEqual(new['source'],old['source'])
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'undo'})
        self.assertEqual(st['document'],before['document'])
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'add_page','title':'移動先'})
        target=st['document']['pages'][-1]['id']
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'move_group','group_id':gid,'page_id':target,'delta':[0,0]})
        self.assertEqual(len(st['document']['pages'][0]['elements']),0)
        self.assertEqual(len(st['document']['pages'][1]['elements']),2)
        st=s.apply_operation(self.cid,self.editor,st['version'],{'type':'ungroup','group_id':gid})
        self.assertEqual(st['document']['groups'],[])
